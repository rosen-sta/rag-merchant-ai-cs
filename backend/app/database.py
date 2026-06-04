import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_type TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                mode TEXT NOT NULL,
                is_fallback INTEGER NOT NULL DEFAULT 0,
                needs_human INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_records_session ON chat_records(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_records_created ON chat_records(created_at)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS missed_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                session_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missed_questions_status ON missed_questions(status)")


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


def get_product(product_id: int) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, category, price, sizes, material, audience,
                   selling_points, stock, product_url, source_file, created_at
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def search_products(
    keyword: str = "",
    category: str = "",
    max_price: Optional[float] = None,
    target_user: str = "",
) -> List[Dict]:
    items = list_products()
    keyword = keyword.strip()
    category = category.strip()
    target_user = target_user.strip()
    matched: List[Dict] = []
    for item in items:
        text = " ".join(
            str(item.get(field, "") or "")
            for field in ("name", "category", "price", "sizes", "material", "audience", "selling_points", "stock")
        )
        if keyword and keyword not in text:
            continue
        if category and category not in str(item.get("category", "")) and category not in str(item.get("name", "")):
            continue
        if target_user and target_user not in str(item.get("audience", "")) and target_user not in text:
            continue
        if max_price is not None:
            price_text = str(item.get("price", "") or "")
            price_match = re.search(r"\d+(?:\.\d+)?", price_text)
            if not price_match or float(price_match.group(0)) > max_price:
                continue
        matched.append(item)
    return matched


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


def insert_chat_record(record: Dict) -> Dict:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_records (
                session_id, user_type, question, answer, sources_json,
                mode, is_fallback, needs_human, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["session_id"],
                record["user_type"],
                record["question"],
                record["answer"],
                record["sources_json"],
                record["mode"],
                1 if record.get("is_fallback") else 0,
                1 if record.get("needs_human") else 0,
                now,
            ),
        )
        record_id = cursor.lastrowid
    return {**record, "id": record_id, "created_at": now}


def list_chat_records(filter_name: str = "all") -> List[Dict]:
    conditions = []
    params: List = []
    if filter_name == "human":
        conditions.append("needs_human = 1")
    elif filter_name == "deepseek":
        conditions.append("mode = ?")
        params.append("deepseek_openai_compatible")
    elif filter_name == "fallback":
        conditions.append("is_fallback = 1")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, session_id, user_type, question, answer, sources_json,
                   mode, is_fallback, needs_human, created_at
            FROM chat_records
            {where}
            ORDER BY id DESC
            LIMIT 300
            """,
            params,
        ).fetchall()
    return [_coerce_chat_record(row) for row in rows]


def list_chat_history(session_id: str) -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, user_type, question, answer, sources_json,
                   mode, is_fallback, needs_human, created_at
            FROM chat_records
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [_coerce_chat_record(row) for row in rows]


def list_chat_sessions() -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                session_id,
                MAX(user_type) AS user_type,
                COUNT(*) AS record_count,
                SUM(needs_human) AS needs_human_count,
                SUM(is_fallback) AS fallback_count,
                MAX(created_at) AS last_created_at,
                (
                    SELECT question FROM chat_records c2
                    WHERE c2.session_id = c1.session_id
                    ORDER BY c2.id DESC
                    LIMIT 1
                ) AS last_question
            FROM chat_records c1
            GROUP BY session_id
            ORDER BY last_created_at DESC
            LIMIT 200
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _coerce_chat_record(row: sqlite3.Row) -> Dict:
    item = _row_to_dict(row)
    item["is_fallback"] = bool(item["is_fallback"])
    item["needs_human"] = bool(item["needs_human"])
    return item


def insert_missed_question(question: str, session_id: str, reason: str) -> Dict:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO missed_questions (question, session_id, reason, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (question, session_id, reason, now),
        )
        missed_id = cursor.lastrowid
    return {
        "id": missed_id,
        "question": question,
        "session_id": session_id,
        "reason": reason,
        "status": "pending",
        "created_at": now,
    }


def list_missed_questions(status: Optional[str] = None) -> List[Dict]:
    params: List = []
    where = ""
    if status:
        where = "WHERE status = ?"
        params.append(status)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, question, session_id, reason, status, created_at
            FROM missed_questions
            {where}
            ORDER BY id DESC
            LIMIT 300
            """,
            params,
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def resolve_missed_question(missed_id: int) -> Optional[Dict]:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE missed_questions
            SET status = 'resolved'
            WHERE id = ?
            """,
            (missed_id,),
        )
        row = conn.execute(
            """
            SELECT id, question, session_id, reason, status, created_at
            FROM missed_questions
            WHERE id = ?
            """,
            (missed_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


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
