import logging
from typing import Dict, List

from openai import OpenAI

from .config import get_settings
from .rag import classify_question, search, summarize_content


NO_INFO_MESSAGE = "目前店铺资料中没有找到相关信息，建议联系人工客服确认"
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


def answer_question(question: str, top_k: int = 5) -> Dict:
    normalized_question = question.strip()
    sources = search(normalized_question, top_k=top_k)
    settings = get_settings()

    if not sources:
        return {
            "question": normalized_question,
            "answer": NO_INFO_MESSAGE,
            "sources": [],
            "mode": "no_context",
        }

    intent = classify_question(normalized_question)

    if not settings.has_deepseek_chat:
        return {
            "question": normalized_question,
            "answer": _fallback_answer(normalized_question, sources),
            "sources": sources,
            "mode": "local_fallback_no_deepseek_key",
        }

    system_prompt = (
        "你是网店里的真实客服导购。回答必须简洁、自然、礼貌，像聊天窗口里的客服。"
        "只能根据商家上传资料回答；没有依据时，只能说“目前店铺资料中没有找到相关信息，建议联系人工客服确认”。"
        "不要编造商品、价格、库存、政策、承诺或链接。不要大段复述资料原文，不要输出引用编号。"
        "商品推荐最多推荐 2 个商品；售后、发货、退换货问题只回答规则，不要混入商品推荐；"
        "商品咨询优先回答商品信息，不要混入无关规则。回答控制在 2 到 4 句。"
    )
    user_prompt = (
        f"顾客问题：{normalized_question}\n\n"
        f"问题类型：{intent}\n\n"
        f"可用资料：\n{_source_context(sources)}\n\n"
        "请直接给顾客回复。"
    )

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
        answer = response.choices[0].message.content.strip()
        if not answer:
            answer = _fallback_answer(normalized_question, sources)
        mode = "deepseek_openai_compatible"
    except Exception as exc:
        logger.warning("DeepSeek chat 调用失败：%s: %s", type(exc).__name__, str(exc)[:240])
        answer = _fallback_answer(normalized_question, sources)
        mode = "local_fallback_after_deepseek_error"

    return {
        "question": normalized_question,
        "answer": answer,
        "sources": sources,
        "mode": mode,
    }
