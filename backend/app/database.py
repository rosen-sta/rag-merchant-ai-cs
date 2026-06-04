import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

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

DEFAULT_ORDERS = [
    {
        "order_no": "10001",
        "customer_name": "小林",
        "product_name": "轻薄防晒衬衫",
        "product_id": 1,
        "order_status": "已发货",
        "shipping_status": "运输中",
        "tracking_no": "ZT123456789",
        "express_company": "中通快递",
        "paid_amount": "159",
        "created_at": "2026-06-01T10:20:00",
        "shipped_at": "2026-06-02T14:30:00",
        "aftersale_status": "无售后",
    },
    {
        "order_no": "10002",
        "customer_name": "小陈",
        "product_name": "通勤托特包",
        "product_id": 2,
        "order_status": "已付款",
        "shipping_status": "待发货",
        "tracking_no": "",
        "express_company": "",
        "paid_amount": "189",
        "created_at": "2026-06-03T18:05:00",
        "shipped_at": "",
        "aftersale_status": "无售后",
    },
    {
        "order_no": "10003",
        "customer_name": "阿敏",
        "product_name": "轻薄防晒衬衫",
        "product_id": 1,
        "order_status": "已完成",
        "shipping_status": "已签收",
        "tracking_no": "SF987654321",
        "express_company": "顺丰速运",
        "paid_amount": "159",
        "created_at": "2026-05-28T09:16:00",
        "shipped_at": "2026-05-29T11:35:00",
        "aftersale_status": "无售后",
    },
    {
        "order_no": "10004",
        "customer_name": "小周",
        "product_name": "通勤托特包",
        "product_id": 2,
        "order_status": "已完成",
        "shipping_status": "已签收",
        "tracking_no": "YD456789123",
        "express_company": "韵达快递",
        "paid_amount": "189",
        "created_at": "2026-05-25T15:48:00",
        "shipped_at": "2026-05-26T10:10:00",
        "aftersale_status": "申请中",
    },
    {
        "order_no": "10005",
        "customer_name": "橙子",
        "product_name": "其他商品",
        "product_id": None,
        "order_status": "已取消",
        "shipping_status": "未发货",
        "tracking_no": "",
        "express_company": "",
        "paid_amount": "0",
        "created_at": "2026-05-20T12:00:00",
        "shipped_at": "",
        "aftersale_status": "无售后",
    },
]


def _row_to_dict(row: sqlite3.Row) -> Dict:
    return {key: row[key] for key in row.keys()}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
                order_card_json TEXT NOT NULL DEFAULT '',
                aftersale_ticket_json TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "chat_records", "order_card_json", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "chat_records", "aftersale_ticket_json", "TEXT NOT NULL DEFAULT ''")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT NOT NULL UNIQUE,
                customer_name TEXT DEFAULT '',
                product_name TEXT NOT NULL,
                product_id INTEGER,
                order_status TEXT DEFAULT '',
                shipping_status TEXT DEFAULT '',
                tracking_no TEXT DEFAULT '',
                express_company TEXT DEFAULT '',
                paid_amount TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                shipped_at TEXT DEFAULT '',
                aftersale_status TEXT DEFAULT '无售后'
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_no ON orders(order_no)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS aftersale_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_no TEXT NOT NULL UNIQUE,
                order_no TEXT DEFAULT '',
                customer_name TEXT DEFAULT '',
                issue_type TEXT NOT NULL,
                issue_description TEXT NOT NULL,
                ai_suggestion TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                needs_human INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_aftersale_tickets_status ON aftersale_tickets(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_aftersale_tickets_order_no ON aftersale_tickets(order_no)")
        _seed_default_orders(conn)


def _seed_default_orders(conn: sqlite3.Connection) -> None:
    for order in DEFAULT_ORDERS:
        conn.execute(
            """
            INSERT OR IGNORE INTO orders (
                order_no, customer_name, product_name, product_id, order_status,
                shipping_status, tracking_no, express_company, paid_amount,
                created_at, shipped_at, aftersale_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order["order_no"],
                order["customer_name"],
                order["product_name"],
                order["product_id"],
                order["order_status"],
                order["shipping_status"],
                order["tracking_no"],
                order["express_company"],
                order["paid_amount"],
                order["created_at"],
                order["shipped_at"],
                order["aftersale_status"],
            ),
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


def list_orders() -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, order_no, customer_name, product_name, product_id,
                   order_status, shipping_status, tracking_no, express_company,
                   paid_amount, created_at, shipped_at, aftersale_status
            FROM orders
            ORDER BY id DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_order(order_no: str) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, order_no, customer_name, product_name, product_id,
                   order_status, shipping_status, tracking_no, express_company,
                   paid_amount, created_at, shipped_at, aftersale_status
            FROM orders
            WHERE order_no = ?
            """,
            (order_no.strip(),),
        ).fetchone()
    return _row_to_dict(row) if row else None


def search_orders(keyword: str = "") -> List[Dict]:
    keyword = keyword.strip()
    if not keyword:
        return list_orders()
    with get_connection() as conn:
        like_value = f"%{keyword}%"
        rows = conn.execute(
            """
            SELECT id, order_no, customer_name, product_name, product_id,
                   order_status, shipping_status, tracking_no, express_company,
                   paid_amount, created_at, shipped_at, aftersale_status
            FROM orders
            WHERE order_no LIKE ?
               OR customer_name LIKE ?
               OR product_name LIKE ?
               OR tracking_no LIKE ?
               OR express_company LIKE ?
            ORDER BY id DESC
            """,
            (like_value, like_value, like_value, like_value, like_value),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _ticket_no() -> str:
    return f"AS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:4].upper()}"


def create_aftersale_ticket(payload: Dict) -> Dict:
    now = datetime.utcnow().isoformat()
    order_no = str(payload.get("order_no", "") or "").strip()
    customer_name = str(payload.get("customer_name", "") or "").strip()
    if order_no and not customer_name:
        order = get_order(order_no)
        if order:
            customer_name = order.get("customer_name", "")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO aftersale_tickets (
                ticket_no, order_no, customer_name, issue_type, issue_description,
                ai_suggestion, status, needs_human, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _ticket_no(),
                order_no,
                customer_name,
                str(payload.get("issue_type", "其他") or "其他"),
                str(payload.get("issue_description", "") or ""),
                str(payload.get("ai_suggestion", "") or ""),
                str(payload.get("status", "pending") or "pending"),
                1 if payload.get("needs_human", True) else 0,
                now,
                now,
            ),
        )
        ticket_id = cursor.lastrowid
        if order_no:
            conn.execute(
                "UPDATE orders SET aftersale_status = '申请中' WHERE order_no = ?",
                (order_no,),
            )
        row = conn.execute(
            """
            SELECT id, ticket_no, order_no, customer_name, issue_type,
                   issue_description, ai_suggestion, status, needs_human,
                   created_at, updated_at
            FROM aftersale_tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()
    return _coerce_aftersale_ticket(row)


def list_aftersale_tickets(status: str = "") -> List[Dict]:
    params: List = []
    where = ""
    if status:
        where = "WHERE status = ?"
        params.append(status)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, ticket_no, order_no, customer_name, issue_type,
                   issue_description, ai_suggestion, status, needs_human,
                   created_at, updated_at
            FROM aftersale_tickets
            {where}
            ORDER BY id DESC
            LIMIT 500
            """,
            params,
        ).fetchall()
    return [_coerce_aftersale_ticket(row) for row in rows]


def get_aftersale_ticket(ticket_id: int) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, ticket_no, order_no, customer_name, issue_type,
                   issue_description, ai_suggestion, status, needs_human,
                   created_at, updated_at
            FROM aftersale_tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()
    return _coerce_aftersale_ticket(row) if row else None


def update_aftersale_status(ticket_id: int, status: str) -> Optional[Dict]:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE aftersale_tickets
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, now, ticket_id),
        )
        row = conn.execute(
            """
            SELECT id, ticket_no, order_no, customer_name, issue_type,
                   issue_description, ai_suggestion, status, needs_human,
                   created_at, updated_at
            FROM aftersale_tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()
        if row and status in {"resolved", "rejected"} and row["order_no"]:
            conn.execute(
                "UPDATE orders SET aftersale_status = ? WHERE order_no = ?",
                ("已处理" if status == "resolved" else "无售后", row["order_no"]),
            )
    return _coerce_aftersale_ticket(row) if row else None


def _coerce_aftersale_ticket(row: sqlite3.Row) -> Dict:
    item = _row_to_dict(row)
    item["needs_human"] = bool(item["needs_human"])
    return item


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
                mode, is_fallback, needs_human, order_card_json,
                aftersale_ticket_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                record.get("order_card_json", ""),
                record.get("aftersale_ticket_json", ""),
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
                   mode, is_fallback, needs_human, order_card_json,
                   aftersale_ticket_json, created_at
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
                   mode, is_fallback, needs_human, order_card_json,
                   aftersale_ticket_json, created_at
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
