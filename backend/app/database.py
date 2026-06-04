import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from .config import get_settings


PRODUCT_FIELDS = [
    "name",
    "category",
    "price",
    "sizes",
    "material",
    "audience",
    "selling_points",
    "stock",
    "product_url",
]


def _row_to_dict(row: sqlite3.Row) -> Dict:
    return {key: row[key] for key in row.keys()}


@contextmanager
def get_connection():
    settings = get_settings()
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                price TEXT DEFAULT '',
                sizes TEXT DEFAULT '',
                material TEXT DEFAULT '',
                audience TEXT DEFAULT '',
                selling_points TEXT DEFAULT '',
                stock TEXT DEFAULT '',
                product_url TEXT DEFAULT '',
                source_file TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def insert_products(products: Iterable[Dict], source_file: str) -> List[Dict]:
    now = datetime.utcnow().isoformat()
    inserted: List[Dict] = []
    with get_connection() as conn:
        for product in products:
            values = {field: str(product.get(field, "") or "").strip() for field in PRODUCT_FIELDS}
            if not values["name"]:
                continue
            cursor = conn.execute(
                """
                INSERT INTO products (
                    name, category, price, sizes, material, audience,
                    selling_points, stock, product_url, source_file, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    values["name"],
                    values["category"],
                    values["price"],
                    values["sizes"],
                    values["material"],
                    values["audience"],
                    values["selling_points"],
                    values["stock"],
                    values["product_url"],
                    source_file,
                    now,
                ),
            )
            inserted.append({**values, "id": cursor.lastrowid, "source_file": source_file, "created_at": now})
    return inserted


def list_products() -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, category, price, sizes, material, audience,
                   selling_points, stock, product_url, source_file, created_at
            FROM products
            ORDER BY id DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def insert_knowledge_file(filename: str, content: str, chunk_count: int) -> Dict:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO knowledge_files (filename, content, chunk_count, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (filename, content, chunk_count, now),
        )
        file_id = cursor.lastrowid
    return {
        "id": file_id,
        "filename": filename,
        "content": content,
        "chunk_count": chunk_count,
        "created_at": now,
    }


def list_knowledge_files() -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, content, chunk_count, created_at
            FROM knowledge_files
            ORDER BY id DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def save_upload(filename: str, content: bytes) -> Path:
    uploads_dir = get_settings().resolve_path("data/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    target = uploads_dir / safe_name
    suffix = 1
    while target.exists():
        stem = Path(safe_name).stem
        ext = Path(safe_name).suffix
        target = uploads_dir / f"{stem}-{suffix}{ext}"
        suffix += 1
    target.write_bytes(content)
    return target

