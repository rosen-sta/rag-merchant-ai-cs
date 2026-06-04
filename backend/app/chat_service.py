import json
import logging
import time
from typing import Dict, List, Optional
from uuid import uuid4

from openai import OpenAI

from .config import get_settings
from .database import create_aftersale_ticket, get_order, insert_chat_record, insert_missed_question, list_products
from .order_service import (
    ORDER_NOT_FOUND_MESSAGE,
    aftersale_ticket_to_card,
    build_aftersale_answer,
    build_ai_suggestion,
    build_order_answer,
    extract_order_no,
    infer_issue_type,
    is_aftersale_request,
    is_order_query,
    order_context,
    order_to_card,
    ticket_context,
)
from .product_guide import (
    format_product_list,
    match_products_for_comparison,
    parse_product_conditions,
    product_source,
    product_to_card,
    select_product_candidates,
)
from .rag import classify_question, search, summarize_content


NO_INFO_MESSAGE = "目前店铺资料中没有找到相关信息，建议联系人工客服确认"
PRODUCT_NO_MATCH_MESSAGE = "目前店铺资料中暂时没有找到完全符合条件的商品，建议联系人工客服确认。"
HUMAN_HANDOFF_MESSAGE = "这个问题建议转人工客服进一步确认，我已经帮您记录。"
HUMAN_KEYWORDS = ["人工", "客服", "转人工", "投诉", "退款失败", "急", "没解决"]
DEEPSEEK_MAX_ATTEMPTS = 3
logger = logging.getLogger(__name__)


def _client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


def _context_excerpt(source: Dict) -> str:
    metadata = source.get("metadata") or {}
    source_type = metadata.get("source_type")
    if source_type == "product":
        return summarize_content(source.get("content", ""), limit=260)
    return source.get("summary") or summarize_content(source.get("content", ""), limit=120)


def _source_context(sources: List[Dict]) -> str:
    lines = []
    for index, source in enumerate(sources, start=1):
        metadata = source.get("metadata") or {}
        title = metadata.get("title", "未知来源")
        source_type = "商品资料" if metadata.get("source_type") == "product" else "店铺规则"
        lines.append(f"[{index}] {source_type}｜{title}\n{_context_excerpt(source)}")
    return "\n\n".join(lines)


def _fallback_answer(question: str, sources: List[Dict]) -> str:
    if not sources:
        return NO_INFO_MESSAGE

    intent = classify_question(question)
    snippets = []
    for source in sources[:3]:
        summary = source.get("summary") or source.get("content", "")
        snippets.append(summary.rstrip("。；; "))
    if intent == "product":
        joined = "；".join(snippets[:2])
        return f"给您推荐：{joined}。需要更准确尺码或库存的话，可以再联系人工客服确认。"
    joined = snippets[0] if intent == "policy" else "；".join(snippets)
    return f"{joined}。如需确认订单细节，建议联系人工客服。"


def _product_fallback_answer(question: str, products: List[Dict], conditions: Dict) -> str:
    if not products:
        return PRODUCT_NO_MATCH_MESSAGE

    if conditions.get("is_compare") and len(products) >= 2:
        first, second = products[0], products[1]
        return (
            f"这两款适合的场景不太一样。{first.get('name', '')}价格是{first.get('price', '')}元，"
            f"更偏向{first.get('audience', '') or first.get('category', '')}，卖点是{first.get('selling_points', '')}。"
            f"{second.get('name', '')}价格是{second.get('price', '')}元，更偏向{second.get('audience', '') or second.get('category', '')}，"
            f"卖点是{second.get('selling_points', '')}。如果主要看穿搭或功能场景，选更贴近您用途的那款。"
        )

    product = products[0]
    if len(products) == 1 and any(term in question for term in ["尺码", "尺寸", "材质", "面料", "库存", "价格", "适合什么人", "适合哪些人"]):
        parts = [f"{product.get('name', '')}"]
        if any(term in question for term in ["适合什么人", "适合哪些人", "适合"]):
            parts.append(f"适合{product.get('audience', '') or '商品资料中标注的人群'}")
        if any(term in question for term in ["尺码", "尺寸"]):
            parts.append(f"尺码有{product.get('sizes', '') or '暂无尺码信息'}")
        if any(term in question for term in ["材质", "面料"]):
            parts.append(f"材质是{product.get('material', '') or '暂无材质信息'}")
        if "库存" in question:
            parts.append(f"库存为{product.get('stock', '') or '暂无库存信息'}")
        if "价格" in question:
            parts.append(f"价格是{product.get('price', '') or '暂无价格信息'}元")
        return "，".join(parts) + "。"

    names = []
    for product in products[:3]:
        names.append(
            f"{product.get('name', '')}（{product.get('price', '')}元，适合{product.get('audience', '') or '相关人群'}）"
        )
    return f"可以给您优先推荐：{'；'.join(names)}。您可以结合预算、用途和库存再选。"


def _needs_human(question: str, has_sources: bool) -> bool:
    return (not has_sources) or any(keyword in question for keyword in HUMAN_KEYWORDS)


def _append_handoff(answer: str, needs_human: bool) -> str:
    if not needs_human or HUMAN_HANDOFF_MESSAGE in answer:
        return answer
    if PRODUCT_NO_MATCH_MESSAGE in answer:
        return answer
    if ORDER_NOT_FOUND_MESSAGE in answer:
        return answer
    if "已经帮您记录" in answer and "人工客服" in answer:
        return answer
    if not answer:
        return HUMAN_HANDOFF_MESSAGE
    return f"{answer}\n{HUMAN_HANDOFF_MESSAGE}"


def _miss_reason(sources: List[Dict], answer: str) -> str:
    if ORDER_NOT_FOUND_MESSAGE in answer:
        return "order_not_found"
    if NO_INFO_MESSAGE in answer:
        return "answer_no_info"
    if PRODUCT_NO_MATCH_MESSAGE in answer:
        return "product_no_match"
    if not sources:
        return "rag_no_source"
    return ""


def _is_fallback(mode: str) -> bool:
    return mode != "deepseek_openai_compatible"


def _chat_with_deepseek(system_prompt: str, user_prompt: str) -> str:
    settings = get_settings()
    last_exc: Optional[Exception] = None
    for attempt in range(1, DEEPSEEK_MAX_ATTEMPTS + 1):
        try:
            response = _client().chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=360,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            last_exc = exc
            if attempt < DEEPSEEK_MAX_ATTEMPTS:
                time.sleep(0.7 * attempt)
    raise last_exc or RuntimeError("DeepSeek chat 调用失败")


def _persist_chat(result: Dict) -> Dict:
    record = insert_chat_record(
        {
            "session_id": result["session_id"],
            "user_type": result["user_type"],
            "question": result["question"],
            "answer": result["answer"],
            "sources_json": json.dumps(result["sources"], ensure_ascii=False),
            "mode": result["mode"],
            "is_fallback": result["is_fallback"],
            "needs_human": result["needs_human"],
            "order_card_json": json.dumps(result.get("order_card"), ensure_ascii=False) if result.get("order_card") else "",
            "aftersale_ticket_json": json.dumps(result.get("aftersale_ticket"), ensure_ascii=False)
            if result.get("aftersale_ticket")
            else "",
        }
    )
    result["record_id"] = record["id"]
    result["created_at"] = record["created_at"]

    if result["mode"] == "human_handoff" or result.get("order_card") or result.get("aftersale_ticket"):
        reason = ""
    else:
        reason = _miss_reason(result["sources"], result["answer"])
    if reason:
        insert_missed_question(result["question"], result["session_id"], reason)
    return result


def _build_result(
    *,
    session_id: str,
    user_type: str,
    question: str,
    answer: str,
    sources: List[Dict],
    mode: str,
    needs_human: bool,
    product_cards: Optional[List[Dict]] = None,
    order_card: Optional[Dict] = None,
    aftersale_ticket: Optional[Dict] = None,
) -> Dict:
    final_answer = _append_handoff(answer, needs_human)
    return {
        "session_id": session_id,
        "user_type": user_type,
        "question": question,
        "answer": final_answer,
        "sources": sources,
        "product_cards": product_cards or [],
        "order_card": order_card,
        "aftersale_ticket": aftersale_ticket,
        "mode": mode,
        "is_fallback": _is_fallback(mode),
        "needs_human": needs_human,
    }


def _answer_with_order(question: str, order: Dict) -> Dict:
    settings = get_settings()
    fallback = build_order_answer(order, question)
    if not settings.has_deepseek_chat:
        return {"answer": fallback, "mode": "local_fallback_no_deepseek_key"}

    system_prompt = (
        "你是网店里的真实客服。只能根据给出的模拟订单信息回答，不能编造订单状态、物流、快递单号或时间。"
        "回答要自然、简洁、礼貌，控制在 2 到 4 句。"
    )
    user_prompt = f"顾客问题：{question}\n\n订单信息：\n{order_context(order)}\n\n请直接给顾客回复。"
    try:
        answer = _chat_with_deepseek(system_prompt, user_prompt)
        return {"answer": answer or fallback, "mode": "deepseek_openai_compatible"}
    except Exception as exc:
        logger.warning("DeepSeek 订单查询调用失败：%s: %s", type(exc).__name__, str(exc)[:240])
        return {"answer": fallback, "mode": "local_fallback_after_deepseek_error"}


def _answer_with_aftersale(question: str, ticket: Dict) -> Dict:
    settings = get_settings()
    fallback = build_aftersale_answer(ticket)
    if not settings.has_deepseek_chat:
        return {"answer": fallback, "mode": "local_fallback_no_deepseek_key"}

    system_prompt = (
        "你是网店里的真实售后客服。售后、退款、投诉类问题必须提示已记录并建议人工客服继续核实。"
        "只能根据给出的工单信息回答，不要编造处理结果或承诺赔付。回答控制在 2 到 4 句。"
    )
    user_prompt = f"顾客问题：{question}\n\n售后工单：\n{ticket_context(ticket)}\n\n请直接给顾客回复。"
    try:
        answer = _chat_with_deepseek(system_prompt, user_prompt)
        return {"answer": answer or fallback, "mode": "deepseek_openai_compatible"}
    except Exception as exc:
        logger.warning("DeepSeek 售后工单调用失败：%s: %s", type(exc).__name__, str(exc)[:240])
        return {"answer": fallback, "mode": "local_fallback_after_deepseek_error"}


def _try_order_query(*, session_id: str, user_type: str, question: str) -> Optional[Dict]:
    if not is_order_query(question):
        return None
    order_no = extract_order_no(question)
    order = get_order(order_no) if order_no else None
    if not order:
        return _build_result(
            session_id=session_id,
            user_type=user_type,
            question=question,
            answer=ORDER_NOT_FOUND_MESSAGE,
            sources=[],
            product_cards=[],
            order_card=None,
            aftersale_ticket=None,
            mode="no_context",
            needs_human=True,
        )
    answer_data = _answer_with_order(question, order)
    return _build_result(
        session_id=session_id,
        user_type=user_type,
        question=question,
        answer=answer_data["answer"],
        sources=[],
        product_cards=[],
        order_card=order_to_card(order),
        aftersale_ticket=None,
        mode=answer_data["mode"],
        needs_human=False,
    )


def _try_aftersale(*, session_id: str, user_type: str, question: str) -> Optional[Dict]:
    if not is_aftersale_request(question):
        return None
    order_no = extract_order_no(question)
    order = get_order(order_no) if order_no else None
    issue_type = infer_issue_type(question)
    ticket = create_aftersale_ticket(
        {
            "order_no": order_no if order else order_no,
            "customer_name": order.get("customer_name", "") if order else "",
            "issue_type": issue_type,
            "issue_description": question,
            "ai_suggestion": build_ai_suggestion(issue_type, order),
            "status": "pending",
            "needs_human": True,
        }
    )
    answer_data = _answer_with_aftersale(question, ticket)
    return _build_result(
        session_id=session_id,
        user_type=user_type,
        question=question,
        answer=answer_data["answer"],
        sources=[],
        product_cards=[],
        order_card=order_to_card(order) if order else None,
        aftersale_ticket=aftersale_ticket_to_card(ticket),
        mode=answer_data["mode"],
        needs_human=True,
    )


def _answer_with_products(question: str, products: List[Dict], conditions: Dict) -> Dict:
    settings = get_settings()
    if not settings.has_deepseek_chat:
        return {
            "answer": _product_fallback_answer(question, products, conditions),
            "mode": "local_fallback_no_deepseek_key",
        }

    system_prompt = (
        "你是网店里的真实客服导购。只能根据给出的候选商品回答，不能编造商品、价格、库存、材质或链接。"
        "回答要自然、简洁、礼貌，控制在 2 到 6 句话，不要大段拼接商品字段。"
        "商品推荐最多推荐 3 个。若是商品对比，要围绕价格、类目、适用场景、材质、卖点和适合人群说明差异，最后给购买建议。"
        "不要混入发货、退货、售后等无关规则。"
    )
    user_prompt = (
        f"顾客问题：{question}\n\n"
        f"候选商品：\n{format_product_list(products)}\n\n"
        "请直接给顾客回复。"
    )
    try:
        answer = _chat_with_deepseek(system_prompt, user_prompt)
        if not answer:
            answer = _product_fallback_answer(question, products, conditions)
        return {"answer": answer, "mode": "deepseek_openai_compatible"}
    except Exception as exc:
        logger.warning("DeepSeek 商品导购调用失败：%s: %s", type(exc).__name__, str(exc)[:240])
        return {
            "answer": _product_fallback_answer(question, products, conditions),
            "mode": "local_fallback_after_deepseek_error",
        }


def _product_result(
    *,
    session_id: str,
    user_type: str,
    question: str,
    products: List[Dict],
    conditions: Dict,
) -> Dict:
    answer_data = _answer_with_products(question, products, conditions)
    sources = [product_source(product) for product in products[:3]]
    cards = [product_to_card(product) for product in products[:3]]
    return _build_result(
        session_id=session_id,
        user_type=user_type,
        question=question,
        answer=answer_data["answer"],
        sources=sources,
        product_cards=cards,
        mode=answer_data["mode"],
        needs_human=False,
    )


def _product_no_match_result(session_id: str, user_type: str, question: str) -> Dict:
    return _build_result(
        session_id=session_id,
        user_type=user_type,
        question=question,
        answer=PRODUCT_NO_MATCH_MESSAGE,
        sources=[],
        product_cards=[],
        mode="no_context",
        needs_human=True,
    )


def _try_product_guide(
    *,
    session_id: str,
    user_type: str,
    question: str,
) -> Optional[Dict]:
    if classify_question(question) == "policy":
        return None

    conditions = parse_product_conditions(question)
    if not conditions.get("is_product_guide"):
        return None

    products = list_products()
    if not products:
        return _product_no_match_result(session_id, user_type, question)

    if conditions.get("is_compare"):
        compared = match_products_for_comparison(question, products)
        if compared:
            return _product_result(
                session_id=session_id,
                user_type=user_type,
                question=question,
                products=compared,
                conditions=conditions,
            )
        return None

    candidates = select_product_candidates(question, products, conditions, limit=3)
    if candidates:
        return _product_result(
            session_id=session_id,
            user_type=user_type,
            question=question,
            products=candidates,
            conditions=conditions,
        )
    return _product_no_match_result(session_id, user_type, question)


def answer_question(question: str, top_k: int = 5, session_id: str = "", user_type: str = "customer") -> Dict:
    normalized_question = question.strip()
    normalized_session_id = session_id.strip() if session_id else f"session-{uuid4().hex[:16]}"
    normalized_user_type = user_type if user_type in {"customer", "merchant_test"} else "customer"

    aftersale_result = _try_aftersale(
        session_id=normalized_session_id,
        user_type=normalized_user_type,
        question=normalized_question,
    )
    if aftersale_result:
        return _persist_chat(aftersale_result)

    order_result = _try_order_query(
        session_id=normalized_session_id,
        user_type=normalized_user_type,
        question=normalized_question,
    )
    if order_result:
        return _persist_chat(order_result)

    if any(keyword in normalized_question for keyword in HUMAN_KEYWORDS):
        return _persist_chat(
            _build_result(
                session_id=normalized_session_id,
                user_type=normalized_user_type,
                question=normalized_question,
                answer="",
                sources=[],
                product_cards=[],
                mode="human_handoff",
                needs_human=True,
            )
        )

    product_result = _try_product_guide(
        session_id=normalized_session_id,
        user_type=normalized_user_type,
        question=normalized_question,
    )
    if product_result:
        return _persist_chat(product_result)

    sources = search(normalized_question, top_k=top_k)
    settings = get_settings()
    needs_human = _needs_human(normalized_question, has_sources=bool(sources))

    if not sources:
        return _persist_chat(
            _build_result(
                session_id=normalized_session_id,
                user_type=normalized_user_type,
                question=normalized_question,
                answer=NO_INFO_MESSAGE,
                sources=[],
                product_cards=[],
                mode="no_context",
                needs_human=needs_human,
            )
        )

    intent = classify_question(normalized_question)

    if not settings.has_deepseek_chat:
        return _persist_chat(
            _build_result(
                session_id=normalized_session_id,
                user_type=normalized_user_type,
                question=normalized_question,
                answer=_fallback_answer(normalized_question, sources),
                sources=sources,
                product_cards=[],
                mode="local_fallback_no_deepseek_key",
                needs_human=needs_human,
            )
        )

    system_prompt = (
        "你是网店里的真实客服导购。回答必须简洁、自然、礼貌，像聊天窗口里的客服。"
        "只能根据商家上传资料回答；没有依据时，只能说“目前店铺资料中没有找到相关信息，建议联系人工客服确认”。"
        "不要编造商品、价格、库存、政策、承诺或链接。不要大段复述资料原文，不要输出引用编号。"
        "商品推荐最多推荐 3 个商品；售后、发货、退换货问题只回答规则，不要混入商品推荐；"
        "商品咨询优先回答商品信息，不要混入无关规则。回答控制在 2 到 4 句。"
    )
    user_prompt = (
        f"顾客问题：{normalized_question}\n\n"
        f"问题类型：{intent}\n\n"
        f"可用资料：\n{_source_context(sources)}\n\n"
        "请直接给顾客回复。"
    )

    try:
        answer = _chat_with_deepseek(system_prompt, user_prompt)
        if not answer:
            answer = _fallback_answer(normalized_question, sources)
        mode = "deepseek_openai_compatible"
    except Exception as exc:
        logger.warning("DeepSeek chat 调用失败：%s: %s", type(exc).__name__, str(exc)[:240])
        answer = _fallback_answer(normalized_question, sources)
        mode = "local_fallback_after_deepseek_error"

    needs_human = needs_human or NO_INFO_MESSAGE in answer
    return _persist_chat(
        _build_result(
            session_id=normalized_session_id,
            user_type=normalized_user_type,
            question=normalized_question,
            answer=answer,
            sources=sources,
            product_cards=[],
            mode=mode,
            needs_human=needs_human,
        )
    )
