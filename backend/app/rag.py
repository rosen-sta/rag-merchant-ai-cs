import re
import threading
from functools import lru_cache
from typing import Dict, Iterable, List, Sequence, Tuple

import chromadb
from sentence_transformers import SentenceTransformer

from .config import get_settings


COLLECTION_PREFIX = "merchant_rag"
_EMBEDDING_LOCK = threading.RLock()
STOP_TOKENS = {"可以", "能否", "是否", "怎么", "什么", "这件", "这款", "你们", "我们", "店铺", "有没有", "有无"}
POLICY_KEYWORDS = {
    "发货",
    "物流",
    "快递",
    "到货",
    "多久",
    "包邮",
    "运费",
    "退货",
    "换货",
    "退换",
    "售后",
    "质量",
    "破损",
    "污渍",
    "开线",
    "缺失",
    "损坏",
}
PRODUCT_KEYWORDS = {
    "商品",
    "推荐",
    "适合",
    "学生",
    "学生党",
    "通勤",
    "包",
    "衬衫",
    "防晒",
    "尺码",
    "尺寸",
    "材质",
    "面料",
    "价格",
    "预算",
    "库存",
    "元",
}
OVERSEAS_DELIVERY_TERMS = ["海外配送", "海外发货", "国外配送", "国外发货", "国际配送", "国际发货"]


def _safe_collection_part(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())[:42].strip("_")
    return clean or "default"


def _collection_name() -> str:
    settings = get_settings()
    provider = "local"
    model = settings.embedding_model or "BAAI/bge-small-zh-v1.5"
    return f"{COLLECTION_PREFIX}_{provider}_{_safe_collection_part(model)}"


@lru_cache
def _embedding_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def _tokenize(text: str) -> List[str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", lowered)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    for size in (2, 3):
        tokens.extend("".join(chinese_chars[index : index + size]) for index in range(max(0, len(chinese_chars) - size + 1)))
    return [token for token in tokens if token.strip() and token not in STOP_TOKENS]


def classify_question(question: str) -> str:
    normalized = question.lower()
    if any(keyword in normalized for keyword in POLICY_KEYWORDS):
        return "policy"
    if any(keyword in normalized for keyword in PRODUCT_KEYWORDS):
        return "product"
    return "general"


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    settings = get_settings()
    if not texts:
        return []
    with _EMBEDDING_LOCK:
        model = _embedding_model(settings.embedding_model)
        embeddings = model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    return [embedding.astype(float).tolist() for embedding in embeddings]


def get_collection():
    settings = get_settings()
    client = chromadb.PersistentClient(path=str(settings.chroma_path))
    return client.get_or_create_collection(
        name=_collection_name(),
        metadata={"description": "Merchant product and policy chunks for RAG customer service"},
    )


def upsert_documents(documents: Iterable[Dict]) -> int:
    records = [document for document in documents if document.get("text")]
    if not records:
        return 0
    texts = [record["text"] for record in records]
    embeddings = embed_texts(texts)
    collection = get_collection()
    collection.upsert(
        ids=[record["id"] for record in records],
        documents=texts,
        metadatas=[record["metadata"] for record in records],
        embeddings=embeddings,
    )
    return len(records)


def _lexical_score(question: str, document: str) -> float:
    question_tokens = set(_tokenize(question))
    document_tokens = set(_tokenize(document))
    if not question_tokens or not document_tokens:
        return 0.0
    overlap = question_tokens & document_tokens
    strong_overlap = [token for token in overlap if len(token) >= 2]
    strong_question_tokens = [token for token in question_tokens if len(token) >= 2]
    if not strong_overlap:
        return 0.0
    strong_base = max(1, len(strong_question_tokens))
    return len(strong_overlap) / strong_base + len(strong_overlap) * 0.18 + len(overlap) * 0.02


def _dedupe_key(source: Dict) -> str:
    metadata = source.get("metadata") or {}
    source_type = metadata.get("source_type", "")
    if source_type == "product":
        return f"product:{metadata.get('title') or metadata.get('source_id', '')}"
    return f"knowledge:{metadata.get('title') or metadata.get('source_id', '')}"


def _dedupe_sources(sources: Sequence[Dict]) -> List[Dict]:
    best_by_key: Dict[str, Dict] = {}
    for source in sources:
        key = _dedupe_key(source)
        current = best_by_key.get(key)
        if current is None or source.get("score", 0) > current.get("score", 0):
            best_by_key[key] = source
    deduped = list(best_by_key.values())
    deduped.sort(key=lambda item: (item.get("score", 0), -float(item.get("distance") or 0)), reverse=True)
    return deduped


def _apply_intent_policy(question: str, sources: Sequence[Dict], limit: int) -> List[Dict]:
    intent = classify_question(question)
    deduped = _dedupe_sources(sources)
    if not deduped:
        return []

    products = [source for source in deduped if (source.get("metadata") or {}).get("source_type") == "product"]
    knowledge = [source for source in deduped if (source.get("metadata") or {}).get("source_type") != "product"]

    if intent == "policy" and knowledge:
        return knowledge[:limit]
    if intent == "product" and products:
        return products[: min(2, limit)]
    return deduped[:limit]


def _is_unanswered_overseas_delivery(question: str, sources: Sequence[Dict]) -> bool:
    if not any(term in question for term in OVERSEAS_DELIVERY_TERMS):
        return False
    joined = "\n".join(source.get("content", "") for source in sources)
    return not any(term in joined for term in OVERSEAS_DELIVERY_TERMS)


def search(question: str, top_k: int = 5) -> List[Dict]:
    collection = get_collection()
    try:
        count = collection.count()
    except Exception:
        count = 0
    if count == 0:
        return []

    query_embedding = embed_texts([question])[0]
    source_limit = min(max(top_k, 1), 3)
    n_results = max(top_k * 6, 20)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, count),
        include=["documents", "metadatas", "distances"],
    )
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    ranked: List[Dict] = []
    for index, document in enumerate(documents):
        score = _lexical_score(question, document)
        distance = distances[index] if index < len(distances) else None
        metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
        if score <= 0.05 and len(document) > 40:
            continue
        source_type = metadata.get("source_type")
        summary = (
            summarize_product_content(document, limit=80)
            if source_type == "product"
            else summarize_relevant_content(question, document, limit=80)
        )
        ranked.append(
            {
                "content": document,
                "metadata": metadata,
                "distance": distance,
                "score": score,
                "summary": summary,
            }
        )
    ranked.sort(key=lambda item: (item["score"], -float(item["distance"] or 0)), reverse=True)
    if ranked:
        best_score = ranked[0]["score"]
        minimum_score = max(0.3, best_score * 0.35)
        ranked = [item for item in ranked if item["score"] >= minimum_score]
    if _is_unanswered_overseas_delivery(question, ranked):
        return []
    return _apply_intent_policy(question, ranked, source_limit)


def summarize_content(content: str, limit: int = 80) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    if len(compact) <= limit:
        return compact
    if limit <= 3:
        return compact[:limit]
    return compact[: limit - 3].rstrip() + "..."


def _field_value(content: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}：([^\n]+)", content)
    return match.group(1).strip() if match else ""


def summarize_product_content(content: str, limit: int = 80) -> str:
    name = _field_value(content, "商品名称")
    price = _field_value(content, "价格")
    audience = _field_value(content, "适用人群")
    selling_points = _field_value(content, "商品卖点")
    parts = []
    if name:
        parts.append(name)
    if price:
        parts.append(f"{price}元" if price.isdigit() else price)
    if audience:
        parts.append(f"适合{audience}")
    elif selling_points:
        parts.append(selling_points)
    return summarize_content("，".join(parts) or content, limit=limit)


def summarize_relevant_content(question: str, content: str, limit: int = 80) -> str:
    parts = [part.strip() for part in re.split(r"(?<=[。！？；])|\n+", content) if part.strip()]
    if not parts:
        return summarize_content(content, limit=limit)

    scored: List[Tuple[int, float, str]] = []
    for index, part in enumerate(parts):
        scored.append((index, _lexical_score(question, part), part))

    ordered_by_score = [item for item in sorted(scored, key=lambda value: value[1], reverse=True) if item[1] > 0]
    if ordered_by_score:
        best_score = ordered_by_score[0][1]
        selected = [item for item in ordered_by_score if item[1] >= best_score * 0.55][:3]
    else:
        selected = []
    if not selected:
        selected = scored[:2]
    selected.sort(key=lambda value: value[0])
    summary = " ".join(item[2] for item in selected)
    return summarize_content(summary, limit=limit)


def build_product_documents(products: Iterable[Dict], product_to_document) -> List[Dict]:
    records = []
    for product in products:
        text = product_to_document(product)
        records.append(
            {
                "id": f"product:{product['id']}",
                "text": text,
                "metadata": {
                    "source_type": "product",
                    "source_id": str(product["id"]),
                    "title": product.get("name", ""),
                    "source_file": product.get("source_file", ""),
                    "category": product.get("category", ""),
                },
            }
        )
    return records


def build_knowledge_documents(file_record: Dict, chunks: Sequence[str]) -> List[Dict]:
    records = []
    for index, chunk in enumerate(chunks):
        records.append(
            {
                "id": f"knowledge:{file_record['id']}:{index}",
                "text": chunk,
                "metadata": {
                    "source_type": "knowledge",
                    "source_id": str(file_record["id"]),
                    "title": file_record["filename"],
                    "chunk_index": index,
                },
            }
        )
    return records
