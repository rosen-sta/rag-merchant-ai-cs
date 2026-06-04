import re
from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, List

import pandas as pd


COLUMN_ALIASES = {
    "name": ["商品名称", "商品名", "名称", "name", "product_name", "title"],
    "category": ["类目", "分类", "品类", "category"],
    "price": ["价格", "售价", "price"],
    "sizes": ["尺码", "尺寸", "规格", "sizes", "size"],
    "material": ["材质", "面料", "material"],
    "audience": ["适用人群", "人群", "适合人群", "audience"],
    "selling_points": ["商品卖点", "卖点", "亮点", "selling_points", "features"],
    "stock": ["库存", "stock"],
    "product_url": ["商品链接", "链接", "product_url", "url", "link"],
}


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _normalize_columns(columns: List[str]) -> Dict[str, str]:
    lowered = {str(column).strip().lower(): str(column) for column in columns}
    mapping: Dict[str, str] = {}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = alias.strip().lower()
            if key in lowered:
                mapping[target] = lowered[key]
                break
    return mapping


def parse_product_file(filename: str, content: bytes) -> List[Dict]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        text = _decode_text(content)
        dataframe = pd.read_csv(StringIO(text)).fillna("")
    elif suffix in {".xlsx", ".xls"}:
        dataframe = pd.read_excel(BytesIO(content)).fillna("")
    else:
        raise ValueError("仅支持 CSV、XLSX 或 XLS 商品文件")

    if dataframe.empty:
        return []

    mapping = _normalize_columns([str(column) for column in dataframe.columns])
    if "name" not in mapping:
        raise ValueError("商品文件必须包含“商品名称”列")

    products: List[Dict] = []
    for _, row in dataframe.iterrows():
        product = {}
        for field in COLUMN_ALIASES:
            source_column = mapping.get(field)
            product[field] = str(row[source_column]).strip() if source_column else ""
        if product["name"]:
            products.append(product)
    return products


def parse_text_file(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".md", ".markdown"}:
        raise ValueError("仅支持 TXT、Markdown 知识文件")
    text = _decode_text(content)
    return text.strip()


def product_to_document(product: Dict) -> str:
    return "\n".join(
        [
            f"商品名称：{product.get('name', '')}",
            f"类目：{product.get('category', '')}",
            f"价格：{product.get('price', '')}",
            f"尺码：{product.get('sizes', '')}",
            f"材质：{product.get('material', '')}",
            f"适用人群：{product.get('audience', '')}",
            f"商品卖点：{product.get('selling_points', '')}",
            f"库存：{product.get('stock', '')}",
            f"商品链接：{product.get('product_url', '')}",
        ]
    )


def _split_long_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    chunks: List[str] = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        candidate = text[start:end]
        split_at = max(candidate.rfind("\n"), candidate.rfind("。"), candidate.rfind("；"))
        if split_at > chunk_size * 0.55 and end < text_length:
            end = start + split_at + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start = max(0, end - overlap)
    return chunks


def chunk_text(text: str, chunk_size: int = 520, overlap: int = 80) -> List[str]:
    raw_blocks = re.split(r"\n\s*\n", text.strip())
    blocks = ["\n".join(line.strip() for line in block.splitlines() if line.strip()) for block in raw_blocks]
    blocks = [block for block in blocks if block]
    if not blocks:
        return []

    chunks: List[str] = []
    for block in blocks:
        if len(block) <= chunk_size:
            chunks.append(block)
            continue
        chunks.extend(_split_long_text(block, chunk_size=chunk_size, overlap=overlap))
    return chunks
