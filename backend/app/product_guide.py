import re
from typing import Dict, List, Optional, Tuple


PRODUCT_GUIDE_KEYWORDS = [
    "推荐",
    "适合",
    "学生党",
    "通勤",
    "夏天",
    "夏季",
    "防晒",
    "送礼",
    "便宜",
    "预算",
    "以内",
    "不超过",
    "低于",
    "包",
    "衣服",
    "衬衫",
    "鞋",
    "配饰",
    "尺码",
    "尺寸",
    "材质",
    "面料",
    "库存",
    "价格",
    "商品",
]
COMPARE_KEYWORDS = ["区别", "对比", "哪个", "哪款", "怎么选", "更适合", "差别"]
ATTRIBUTE_KEYWORDS = ["尺码", "尺寸", "材质", "面料", "库存", "价格", "适合什么人", "适合哪些人"]

CATEGORY_ALIASES = {
    "bag": ["包", "女包", "托特包", "箱包"],
    "clothes": ["衣服", "服装", "女装", "男装", "童装", "T恤", "短裤"],
    "shirt": ["衬衫"],
    "shoes": ["鞋", "鞋子"],
    "accessory": ["配饰", "饰品"],
}

AUDIENCE_ALIASES = {
    "学生党": ["学生党", "学生", "上课"],
    "上班族": ["上班族", "上班"],
    "通勤": ["通勤"],
    "女生": ["女生", "女士", "女装", "女包"],
    "男生": ["男生", "男士", "男装"],
}

SCENE_ALIASES = {
    "夏天": ["夏天", "夏季", "夏日"],
    "防晒": ["防晒"],
    "送礼": ["送礼", "礼物"],
    "日常": ["日常", "休闲"],
    "户外": ["户外", "出游"],
}


def parse_price_number(value: str) -> Optional[float]:
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group(0)) if match else None


def _text(product: Dict) -> str:
    return " ".join(
        str(product.get(field, "") or "")
        for field in ("name", "category", "price", "sizes", "material", "audience", "selling_points", "stock")
    )


def _contains_any(text: str, terms: List[str]) -> bool:
    return any(term and term in text for term in terms)


def parse_product_conditions(question: str) -> Dict:
    normalized = question.strip()
    conditions: Dict = {
        "is_product_guide": any(keyword in normalized for keyword in PRODUCT_GUIDE_KEYWORDS),
        "is_compare": any(keyword in normalized for keyword in COMPARE_KEYWORDS),
        "max_price": None,
        "min_price": None,
        "category_keys": [],
        "audience_terms": [],
        "scene_terms": [],
        "attribute_terms": [],
        "prefer_low_price": any(keyword in normalized for keyword in ["便宜", "价格低", "实惠", "划算"]),
    }

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:到|至|-|~|—)\s*(\d+(?:\.\d+)?)\s*元?", normalized)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        conditions["min_price"] = min(low, high)
        conditions["max_price"] = max(low, high)
    else:
        max_patterns = [
            r"(\d+(?:\.\d+)?)\s*元?\s*以内",
            r"不超过\s*(\d+(?:\.\d+)?)",
            r"低于\s*(\d+(?:\.\d+)?)",
        ]
        for pattern in max_patterns:
            match = re.search(pattern, normalized)
            if match:
                conditions["max_price"] = float(match.group(1))
                break

    for key, aliases in CATEGORY_ALIASES.items():
        if _contains_any(normalized, aliases):
            conditions["category_keys"].append(key)

    for term, aliases in AUDIENCE_ALIASES.items():
        if _contains_any(normalized, aliases):
            conditions["audience_terms"].append(term)

    for term, aliases in SCENE_ALIASES.items():
        if _contains_any(normalized, aliases):
            conditions["scene_terms"].append(term)

    for term in ATTRIBUTE_KEYWORDS:
        if term in normalized:
            conditions["attribute_terms"].append(term)

    if conditions["is_compare"]:
        conditions["is_product_guide"] = True
    if any(
        conditions[key]
        for key in ("max_price", "min_price", "category_keys", "audience_terms", "scene_terms", "attribute_terms")
    ):
        conditions["is_product_guide"] = True
    return conditions


def product_to_card(product: Dict) -> Dict:
    return {
        "id": product.get("id"),
        "name": product.get("name", ""),
        "category": product.get("category", ""),
        "price": product.get("price", ""),
        "size": product.get("sizes", ""),
        "material": product.get("material", ""),
        "target_user": product.get("audience", ""),
        "selling_points": product.get("selling_points", ""),
        "stock": product.get("stock", ""),
        "link": product.get("product_url", ""),
    }


def product_source(product: Dict) -> Dict:
    content = (
        f"商品名称：{product.get('name', '')}\n"
        f"类目：{product.get('category', '')}\n"
        f"价格：{product.get('price', '')}\n"
        f"尺码：{product.get('sizes', '')}\n"
        f"材质：{product.get('material', '')}\n"
        f"适用人群：{product.get('audience', '')}\n"
        f"商品卖点：{product.get('selling_points', '')}\n"
        f"库存：{product.get('stock', '')}\n"
        f"商品链接：{product.get('product_url', '')}"
    )
    summary_parts = [product.get("name", "")]
    if product.get("price"):
        summary_parts.append(f"{product.get('price')}元")
    if product.get("audience"):
        summary_parts.append(f"适合{product.get('audience')}")
    return {
        "content": content,
        "metadata": {
            "source_type": "product",
            "source_id": str(product.get("id", "")),
            "title": product.get("name", ""),
            "category": product.get("category", ""),
        },
        "distance": None,
        "score": 1.0,
        "summary": "，".join(part for part in summary_parts if part)[:80],
    }


def _category_match(product: Dict, category_key: str) -> bool:
    text = _text(product)
    aliases = CATEGORY_ALIASES.get(category_key, [])
    if category_key == "clothes":
        return any(term in text for term in aliases) or any(term in text for term in ["装", "T 恤", "T恤"])
    return _contains_any(text, aliases)


def _condition_score(product: Dict, conditions: Dict, question: str) -> Tuple[float, bool]:
    text = _text(product)
    score = 0.0
    has_soft_match = False

    price = parse_price_number(product.get("price", ""))
    min_price = conditions.get("min_price")
    max_price = conditions.get("max_price")
    if min_price is not None and (price is None or price < min_price):
        return 0.0, False
    if max_price is not None and (price is None or price > max_price):
        return 0.0, False
    if min_price is not None or max_price is not None:
        score += 2.0
        has_soft_match = True

    category_keys = conditions.get("category_keys") or []
    if category_keys:
        if not any(_category_match(product, key) for key in category_keys):
            return 0.0, False
        score += 3.0
        has_soft_match = True

    audience_terms = conditions.get("audience_terms") or []
    if audience_terms:
        audience_matched = False
        for term in audience_terms:
            aliases = AUDIENCE_ALIASES.get(term, [term])
            if _contains_any(text, aliases):
                score += 2.2
                has_soft_match = True
                audience_matched = True
        if not audience_matched:
            return 0.0, False

    scene_terms = conditions.get("scene_terms") or []
    if scene_terms:
        scene_matched = False
        for term in scene_terms:
            aliases = SCENE_ALIASES.get(term, [term])
            if _contains_any(text, aliases):
                score += 2.0
                has_soft_match = True
                scene_matched = True
        if not scene_matched:
            return 0.0, False

    name = str(product.get("name", ""))
    if name and name in question:
        score += 8.0
        has_soft_match = True
    else:
        for piece in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]+", name):
            if len(piece) >= 2 and piece in question:
                score += 1.2
                has_soft_match = True

    for term in ["防晒", "托特包", "衬衫", "T恤", "短裤", "运动"]:
        if term in question and term in text:
            score += 1.8
            has_soft_match = True

    product_price = product.get("price", "")
    if product_price and str(product_price) in question:
        score += 4.0
        has_soft_match = True

    return score, has_soft_match


def _has_strict_conditions(conditions: Dict) -> bool:
    return bool(conditions.get("category_keys") or conditions.get("max_price") is not None or conditions.get("min_price") is not None)


def select_product_candidates(question: str, products: List[Dict], conditions: Dict, limit: int = 3) -> List[Dict]:
    scored: List[Tuple[float, float, Dict]] = []
    for product in products:
        score, has_match = _condition_score(product, conditions, question)
        if score <= 0:
            continue
        price = parse_price_number(product.get("price", "")) or 999999
        scored.append((score, price, product))

    if not scored and not _has_strict_conditions(conditions):
        for product in products:
            score, has_match = _condition_score(product, conditions, question)
            if has_match:
                price = parse_price_number(product.get("price", "")) or 999999
                scored.append((score, price, product))

    if not scored and conditions.get("is_product_guide") and not _has_strict_conditions(conditions):
        for product in products:
            price = parse_price_number(product.get("price", "")) or 999999
            scored.append((0.1, price, product))

    if conditions.get("prefer_low_price"):
        scored.sort(key=lambda item: (item[1], -item[0]))
    else:
        scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return [item[2] for item in scored[:limit]]


def match_products_for_comparison(question: str, products: List[Dict]) -> List[Dict]:
    scored: List[Tuple[float, Dict]] = []
    for product in products:
        text = _text(product)
        score = 0.0
        name = str(product.get("name", ""))
        if name and name in question:
            score += 10.0
        for term in ["防晒", "衬衫", "通勤", "托特包", "包", "T恤", "短裤", "运动"]:
            if term in question and term in text:
                score += 2.0
        price = product.get("price", "")
        if price and str(price) in question:
            score += 4.0
        if score > 0:
            scored.append((score, product))
    scored.sort(key=lambda item: item[0], reverse=True)

    matched: List[Dict] = []
    seen = set()
    for _, product in scored:
        product_id = product.get("id")
        if product_id in seen:
            continue
        matched.append(product)
        seen.add(product_id)
        if len(matched) == 2:
            break
    return matched if len(matched) >= 2 else []


def format_product_list(products: List[Dict]) -> str:
    lines = []
    for product in products:
        lines.append(
            "；".join(
                [
                    f"商品：{product.get('name', '')}",
                    f"类目：{product.get('category', '')}",
                    f"价格：{product.get('price', '')}",
                    f"尺码：{product.get('sizes', '')}",
                    f"材质：{product.get('material', '')}",
                    f"适用人群：{product.get('audience', '')}",
                    f"卖点：{product.get('selling_points', '')}",
                    f"库存：{product.get('stock', '')}",
                ]
            )
        )
    return "\n".join(lines)
