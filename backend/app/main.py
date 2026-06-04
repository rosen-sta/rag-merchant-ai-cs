from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .chat_service import answer_question
from .config import PROJECT_ROOT, get_settings
from .database import (
    create_aftersale_ticket,
    get_aftersale_ticket,
    get_order,
    init_db,
    get_product,
    insert_knowledge_file,
    insert_products,
    list_aftersale_tickets,
    list_chat_history,
    list_chat_records,
    list_chat_sessions,
    list_knowledge_files,
    list_missed_questions,
    list_orders,
    list_products,
    resolve_missed_question,
    save_upload,
    search_orders,
    search_products,
    update_aftersale_status,
)
from .file_parser import chunk_text, parse_product_file, parse_text_file, product_to_document
from .rag import build_knowledge_documents, build_product_documents, get_collection, upsert_documents
from .schemas import AftersaleCreateRequest, AftersaleStatusUpdate, ChatRequest, LoginRequest


app = FastAPI(title="RAG 电商商家 AI 客服导购系统", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    settings = get_settings()
    settings.warn_if_incomplete()
    init_db()
    get_collection()


@app.get("/api/health")
def health():
    settings = get_settings()
    collection = get_collection()
    return {
        "status": "ok",
        "sqlite_db_path": str(settings.sqlite_path),
        "chroma_db_path": str(settings.chroma_path),
        "vector_count": collection.count(),
        "deepseek_chat_configured": settings.has_deepseek_chat,
        "deepseek_base_url": settings.deepseek_base_url,
        "chat_model": settings.chat_model,
        "embedding_provider": "local",
        "embedding_model": settings.embedding_model,
    }


@app.post("/api/login")
def login(payload: LoginRequest):
    if payload.username == "admin" and payload.password == "123456":
        return {"token": "local-demo-admin-token", "username": "admin"}
    raise HTTPException(status_code=401, detail="账号或密码错误")


@app.post("/api/products/upload")
async def upload_products(file: UploadFile = File(...)):
    content = await file.read()
    try:
        products = parse_product_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not products:
        raise HTTPException(status_code=400, detail="没有解析到有效商品数据")

    saved_path = save_upload(file.filename, content)
    inserted = insert_products(products, source_file=saved_path.name)
    documents = build_product_documents(inserted, product_to_document)
    indexed_count = upsert_documents(documents)
    return {
        "filename": saved_path.name,
        "parsed_count": len(products),
        "saved_count": len(inserted),
        "indexed_count": indexed_count,
        "products": inserted,
    }


@app.get("/api/products")
def products():
    return {"items": list_products()}


@app.get("/api/products/search")
def product_search(
    keyword: str = "",
    category: str = "",
    max_price: Optional[float] = Query(default=None, ge=0),
    target_user: str = "",
):
    return {
        "items": search_products(
            keyword=keyword,
            category=category,
            max_price=max_price,
            target_user=target_user,
        )
    }


@app.get("/api/products/{product_id}")
def product_detail(product_id: int):
    item = get_product(product_id)
    if not item:
        raise HTTPException(status_code=404, detail="未找到该商品")
    return item


@app.get("/api/orders")
def orders():
    return {"items": list_orders()}


@app.get("/api/orders/search")
def order_search(keyword: str = ""):
    return {"items": search_orders(keyword)}


@app.get("/api/orders/{order_no}")
def order_detail(order_no: str):
    item = get_order(order_no)
    if not item:
        raise HTTPException(status_code=404, detail="未找到该订单")
    return item


@app.get("/api/aftersales")
def aftersales(status: str = ""):
    if status and status not in {"pending", "processing", "resolved", "rejected"}:
        raise HTTPException(status_code=400, detail="status 仅支持 pending、processing、resolved、rejected")
    return {"items": list_aftersale_tickets(status)}


@app.get("/api/aftersales/{ticket_id}")
def aftersale_detail(ticket_id: int):
    item = get_aftersale_ticket(ticket_id)
    if not item:
        raise HTTPException(status_code=404, detail="未找到该售后工单")
    return item


@app.post("/api/aftersales")
def create_aftersale(payload: AftersaleCreateRequest):
    return create_aftersale_ticket(payload.model_dump())


@app.patch("/api/aftersales/{ticket_id}/status")
def patch_aftersale_status(ticket_id: int, payload: AftersaleStatusUpdate):
    item = update_aftersale_status(ticket_id, payload.status)
    if not item:
        raise HTTPException(status_code=404, detail="未找到该售后工单")
    return item


@app.post("/api/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text = parse_text_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not text:
        raise HTTPException(status_code=400, detail="知识文件内容为空")

    saved_path = save_upload(file.filename, content)
    chunks = chunk_text(text)
    file_record = insert_knowledge_file(saved_path.name, text, len(chunks))
    documents = build_knowledge_documents(file_record, chunks)
    indexed_count = upsert_documents(documents)
    return {
        "file": {
            "id": file_record["id"],
            "filename": file_record["filename"],
            "chunk_count": file_record["chunk_count"],
            "created_at": file_record["created_at"],
        },
        "indexed_count": indexed_count,
    }


@app.get("/api/knowledge")
def knowledge():
    items = []
    for item in list_knowledge_files():
        preview = " ".join(item["content"].split())[:220]
        items.append(
            {
                "id": item["id"],
                "filename": item["filename"],
                "chunk_count": item["chunk_count"],
                "created_at": item["created_at"],
                "preview": preview,
            }
        )
    return {"items": items}


@app.post("/api/chat")
def chat(payload: ChatRequest):
    return answer_question(
        payload.question,
        top_k=payload.top_k or 5,
        session_id=payload.session_id or "",
        user_type=payload.user_type,
    )


@app.get("/api/chat/sessions")
def chat_sessions():
    return {"items": list_chat_sessions()}


@app.get("/api/chat/history")
def chat_history(session_id: str):
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id 不能为空")
    return {"items": list_chat_history(session_id)}


@app.get("/api/chat/records")
def chat_records(filter: str = "all"):
    if filter not in {"all", "human", "deepseek", "fallback"}:
        raise HTTPException(status_code=400, detail="filter 仅支持 all、human、deepseek、fallback")
    return {"items": list_chat_records(filter)}


@app.get("/api/missed-questions")
def missed_questions(status: str = ""):
    if status and status not in {"pending", "resolved"}:
        raise HTTPException(status_code=400, detail="status 仅支持 pending 或 resolved")
    return {"items": list_missed_questions(status or None)}


@app.patch("/api/missed-questions/{missed_id}/resolve")
def resolve_missed(missed_id: int):
    item = resolve_missed_question(missed_id)
    if not item:
        raise HTTPException(status_code=404, detail="未找到该未命中问题")
    return item


@app.exception_handler(Exception)
async def unexpected_error_handler(_, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"服务器内部错误：{exc}"})


frontend_dir = PROJECT_ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
