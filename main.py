# main.py
# • FastAPI + Jinja2 + SQLite + Gemini-2.5-flash
# • Hybrid RAG: ChromaDB (all-MiniLM-L6-v2) + BM25 + Cache
# • Tự động chunk Markdown theo heading, hỗ trợ upload/re-ingest
# • CSKH live chuyển tiếp WebSocket (cskh_system)
# • Tự động ép file khi người dùng nhắc tên file (không cần chọn tay)
# • Lọc chửi thề, câu chào/cảm ơn, câu hỏi 5W1H nguy hiểm
# • Quick reply + Intent engine + Badword filter
# • Quản lý vector (/vector-manager), config prompt, lịch sử chat
# • Re-ingest tự động khi thay đổi chunk_size/overlap
# • CSRF protection + Session + Reset vectorstore đầy đủ
# • Route chính:
#       GET  /           → trang chủ
#       GET  /chat       → giao diện chat
#       POST /chat       → xử lý tin nhắn + RAG + Gemini
#       POST /upload     → upload .md/.txt → tự add vào Chroma
#       GET  /vector-manager → xem/xóa chunk theo file
#       GET  /config     → chỉnh system prompt + chunk size
#       GET  /history    → xem toàn bộ lịch sử chat
import secrets
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import json
import shutil
from datetime import datetime
from pathlib import Path

# ====================== IMPORT CÁC MODULE CỦA BẠN ======================
from cskh_system import (
    register_cskh_routes,
    is_customer_support_intent,
    handle_cskh_transfer
)
from vector_store import (
    add_documents, query_documents, reset_vectorstore,
    get_collection, get_all_documents
)
from quick_reply import is_greeting_or_thanks, get_quick_response
from config import settings
from db import (
    get_chat_history, get_config, set_config, save_message, get_uploaded_files,
    add_uploaded_file, delete_uploaded_file, get_system_prompt, save_system_prompt, clear_uploaded_files
)
from starlette.middleware.sessions import SessionMiddleware
from badword_filter import contains_swear, get_swear_response
from gemini_client import chat_with_gemini, model
from utils import split_text
from intent_engine import detect_intent, get_intent_response

# ====================== KHOI TAO APP ======================
app = FastAPI(title="Tu Tiên Shop AI + CSKH Live 2025")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))
# Đăng ký route CSKH ngay khi khởi động
@app.on_event("startup")
async def startup_event():
    await register_cskh_routes(app, templates)
    print("CSKH WebSocket routes đã được đăng ký thành công!")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

# ====================== KIỂM TRA CÂU HỎI NGHIÊM TÚC ======================
def is_serious_question(message: str) -> bool:
    prompt = f"""Chỉ trả lời đúng 1 chữ: Y hoặc N
Câu hỏi này có phải đang hỏi về nội dung trong tài liệu kỹ thuật, hệ thống RAG, chunk, vector, gemini, chroma, metadata, heading, upload, file, luồng dữ liệu, cấu trúc, v.v. không?
Câu hỏi: {message}
Trả lời ngay:"""
    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.0, "max_output_tokens": 5}
        )
        return response.text.strip().upper() == "Y"
    except Exception as e:
        print(f"[Gemini Intent Error] {e}")
        return True  # an toàn thì đi RAG

# ====================== CHAT CHÍNH ======================
@app.post("/chat")
async def chat(message: str = Form(...), session_id: str = Form("default")):
    save_message("user", message, session_id=session_id)

    # === 1. Lọc nhanh các trường hợp đặc biệt ===
    if contains_swear(message):
        resp = get_swear_response()
        save_message("bot", resp, session_id=session_id)
        return {"response": resp}

    if is_customer_support_intent(message):
        save_message("bot", "Đang kết nối với nhân viên CSKH...", session_id=session_id)
        result = await handle_cskh_transfer(message=message, customer_name="đạo hữu", force=True)
        return result

    if len(message.strip()) <= 12 or not is_serious_question(message):
        resp = get_quick_response()
        save_message("bot", resp, session_id=session_id)
        return {"response": resp}

    # === 2. Chuẩn bị ===
    history = get_chat_history(session_id=session_id)
    coll = get_collection()
    msg_lower = message.lower().strip()

    # === 3. TỰ ĐỘNG ÉP FILE – KHÔNG CẦN SỬA CODE NỮA! ===
    # Lấy tất cả file đang có trong ChromaDB
    all_sources = {
        m.get("source", "") for m in coll.get(include=["metadatas"])["metadatas"] 
        if m.get("source")
    }

    # Tự động sinh từ khóa thông minh từ tên file
    file_keywords = {}
    for src in all_sources:
        clean_name = src.lower().replace(".md", "").replace(".markdown", "")
        keywords = [
            clean_name.replace("-", " ").replace("_", " "),
            clean_name.replace("-", "").replace("_", ""),
            clean_name.replace(" ", ""),
            src.replace(".md", "").replace(".markdown", ""),
            "file " + clean_name.replace("-", " "),
            "trong " + clean_name.replace("-", " "),
        ]
        file_keywords[src] = [k for k in keywords if len(k) > 2]

    # Tìm file phù hợp nhất (ưu tiên khớp chính xác)
    target_file = None
    for file_name, keywords in file_keywords.items():
        if any(kw in msg_lower for kw in keywords):
            target_file = file_name
            print(f"TỰ ĐỘNG ÉP FILE → {target_file}")
            break

    # === 4. Lấy chunks ===
    if target_file:
        data = coll.get(where={"source": target_file}, include=["documents", "metadatas"])
        chunks = list(zip(data["documents"], data["metadatas"]))
    else:
        docs, metas = query_documents(message, n_results=40)
        chunks = list(zip(docs, metas))

    # === 5. Làm sạch context – không để lại dấu vết file ===
    clean_parts = []
    for doc, meta in chunks[:15]:
        title = meta.get("title", "").strip()
        text = doc.strip().replace("\n", " ")[:1300]
        if title:
            clean_parts.append(f"{title}\n{text}")
        else:
            clean_parts.append(text)
    context_text = "\n\n".join(clean_parts) if clean_parts else "Không có dữ liệu liên quan."

    # === 6. Phát hiện câu hỏi nguy hiểm (ai, file nào, ở đâu, khi nào…) ===
    dangerous_patterns = [
        "ai ", " ai?", "người nào", "team nào", "đội nào",
        "khi nào", "năm nào", "tháng nào", "ngày nào",
        "ở đâu", "file nào", "tài liệu nào", "phần nào", "source nào",
        "who ", "when ", "where ", "which file", "what file", "source"
    ]
    dangerous_5w1h = any(pat in msg_lower for pat in dangerous_patterns)

    # === 7. Gọi Gemini – chỉ 1 dòng! ===
    response = chat_with_gemini(
        user_question=message,
        context_text=context_text,
        history=history,
        dangerous_5w1h=dangerous_5w1h
    )

    # === 8. Lưu & trả kết quả ===
    save_message("bot", response, session_id=session_id)
    return {"response": response}

@app.post("/delete-file")
async def delete_file(request: Request, filename: str = Form(...), csrf_token: str = Form(...)):
    if request.session.get("csrf_token") != csrf_token:
        return HTMLResponse("CSRF Invalid!", status_code=403)
    
    (settings.UPLOAD_DIR / filename).unlink(missing_ok=True)
    delete_uploaded_file(filename)
    get_collection().delete(where={"source": filename})
    
    # Tạo token mới sau khi dùng
    request.session["csrf_token"] = secrets.token_hex(16)
    return RedirectResponse("/vector-manager", status_code=303)

@app.get("/get-current-prompt")
async def get_current_prompt():
    return PlainTextResponse(get_system_prompt())

@app.get("/data-loader", response_class=HTMLResponse)
async def data_loader_page(request: Request):
    return templates.TemplateResponse("data_loader.html", {
        "request": request,
        "chunk_size": settings.CHUNK_SIZE,
        "chunk_overlap": settings.CHUNK_OVERLAP
    })

@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    success_files = []
    updated_files = []
    failed_files = []

    # Lấy danh sách file đã tồn tại trong Chroma
    coll = get_collection()
    existing = coll.get(include=["metadatas"])
    existing_sources = {m.get("source") for m in existing.get("metadatas", [])}

    for file in files:
        filename = file.filename
        if not filename.lower().endswith((".md", ".markdown", ".txt")):
            failed_files.append(f"{filename} → chỉ hỗ trợ .md/.txt")
            continue

        try:
            # Đọc nội dung
            content = await file.read()
            text = content.decode("utf-8", errors="ignore")

            # Nếu file đã tồn tại → XÓA TOÀN BỘ chunk cũ trước
            if filename in existing_sources:
                coll.delete(where={"source": filename})
                updated_files.append(filename)
            else:
                success_files.append(filename)

            # Add chunk mới
            add_documents(text, filename)

            # Lưu file vật lý
            file_path = settings.UPLOAD_DIR / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)

            # Cập nhật DB danh sách file
            if filename not in get_uploaded_files():
                add_uploaded_file(filename)

        except Exception as e:
            failed_files.append(f"{filename} → lỗi: {e}")

    # Tạo thông báo đẹp
    msg_parts = []
    if success_files:
        msg_parts.append(f"Thêm mới: {len(success_files)} file")
    if updated_files:
        msg_parts.append(f"Cập nhật: {len(updated_files)} file (đã thay thế phiên bản cũ)")
    if failed_files:
        msg_parts.append(f"Thất bại: {len(failed_files)} file")

    msg = "<br>".join(msg_parts) if msg_parts else "Không có gì xảy ra"

    return JSONResponse({
        "status": "done",
        "added": len(success_files),
        "updated": len(updated_files),
        "failed": len(failed_files),
        "msg": f"<strong>HOÀN TẤT!</strong><br>{msg}",
        "detail": {
            "added": success_files,
            "updated": updated_files,
            "failed": failed_files
        }
    })

@app.post("/reset-vectorstore")
async def reset_vs(request: Request, csrf_token: str = Form(...)):
    if request.session.get("csrf_token") != csrf_token:
        return HTMLResponse("Unauthorized", status_code=403)
    
    reset_vectorstore()
    if settings.UPLOAD_DIR.exists():
        shutil.rmtree(settings.UPLOAD_DIR)
        settings.UPLOAD_DIR.mkdir(parents=True)
    clear_uploaded_files()
    
    request.session["csrf_token"] = secrets.token_hex(16)
    return RedirectResponse("/vector-manager", status_code=303)

@app.get("/vector-manager", response_class=HTMLResponse)
async def vector_manager(request: Request):
    # Tạo CSRF token nếu chưa có
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(16)

    data = get_all_documents()
    
    chunks_by_file = {}
    for doc_id, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        source = meta.get("source", "unknown.md")
        chunks_by_file.setdefault(source, []).append({
            "id": doc_id,
            "content": doc.strip(),
            "preview": doc.strip().replace("\n", " ")[:150] + ("..." if len(doc.strip()) > 150 else ""),
            "title": meta.get("title", "Không có tiêu đề"),
            "level": meta.get("level", 1),
            "word_count": len(doc.split())
        })

    for source in chunks_by_file:
        chunks_by_file[source].sort(key=lambda x: x["level"], reverse=True)

    total_chunks = len(data["ids"])

    return templates.TemplateResponse("vector_manager.html", {
        "request": request,
        "chunks_by_file": chunks_by_file,
        "total_chunks": total_chunks,
        "total_files": len(chunks_by_file),
        "csrf_token": request.session["csrf_token"]  
    })

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    prompt_path = Path("data/systemprompt.md")
    
    # Đọc file prompt
    if prompt_path.exists():
        raw_prompt = prompt_path.read_text(encoding="utf-8")
    else:
        raw_prompt = "# Chưa có file systemprompt.md – vui lòng tạo tại thư mục data/"

    # SIÊU PHÉP LÀM ĐẸP PROMPT (chỉ 5 dòng mà đẹp vĩnh viễn)
    clean_lines = []
    for line in raw_prompt.splitlines():
        stripped = line.rstrip()                  # bỏ space/tab thừa cuối dòng
        if stripped == "" or stripped.startswith("#"):  # giữ nguyên dòng trống và heading
            clean_lines.append(stripped)
        else:
            clean_lines.append(stripped)           # các dòng nội dung vẫn giữ nguyên thụt nếu có
    beautiful_prompt = "\n".join(clean_lines).strip() + "\n"  # thêm 1 dòng trống cuối cho đẹp

    return templates.TemplateResponse("config.html", {
        "request": request,
        "chunk_size": settings.CHUNK_SIZE,
        "chunk_overlap": settings.CHUNK_OVERLAP,
        "bot_rules": beautiful_prompt,        
        "model_name": "gemini-2.5-flash"
    })

@app.post("/update-config")
async def update_config(
    chunk_size: int = Form(...),
    chunk_overlap: int = Form(...),
    bot_rules: str = Form(...),
    reingest: bool = Form(False)
):
    old_chunk = settings.CHUNK_SIZE
    old_overlap = settings.CHUNK_OVERLAP

    settings.CHUNK_SIZE = chunk_size
    settings.CHUNK_OVERLAP = chunk_overlap
    set_config("chunk_size", str(chunk_size))
    set_config("chunk_overlap", str(chunk_overlap))
    save_system_prompt(bot_rules)

    need_reingest = (old_chunk != chunk_size or old_overlap != chunk_overlap) or reingest
    msg = "Lưu cấu hình thành công!"

    if need_reingest and list(settings.UPLOAD_DIR.glob("*.md")):
        reset_vectorstore()
        total_files = total_chunks = 0
        for fp in settings.UPLOAD_DIR.glob("*.md"):
            try:
                text = fp.read_text(encoding="utf-8")
                chunks = split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                if chunks:
                    ids = [f"{fp.name}_{i}" for i in range(len(chunks))]
                    metas = [{"source": fp.name} for _ in chunks]
                    add_documents(chunks, metas, ids)
                    total_files += 1
                    total_chunks += len(chunks)
            except Exception as e:
                print(f"Re-ingest lỗi {fp.name}: {e}")
        msg = f"RE-INGEST HOÀN TẤT! {total_files} file → {total_chunks} chunks"

    return JSONResponse({"msg": msg, "reingested": need_reingest})

@app.post("/delete-chunk")
async def delete_chunk(chunk_id: str = Form(...)):
    try:
        get_collection().delete(ids=[chunk_id])
        return {"status": "ok"}
    except:
        return {"status": "error"}

# Jinja2 filter escape JS
def escapejs_filter(value):
    return json.dumps(value)[1:-1]
templates.env.filters['escapejs'] = escapejs_filter

# ====================== LỊCH SỬ CHAT ======================
@app.get("/history")
async def history_page(request: Request, page: int = 1):
    per_page = 50
    offset = (page - 1) * per_page
    conn = sqlite3.connect("data/bot_config.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM chat_history")
    total = c.fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    c.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT ? OFFSET ?", (per_page, offset))
    rows = c.fetchall()
    conn.close()

    history = []
    for role, content, ts in rows:
        try:
            time_str = datetime.strptime(ts.split('.')[0], "%Y-%m-%d %H:%M:%S").strftime("%d/%m %H:%M")
        except:
            time_str = "Vừa xong"
        history.append({"role": role, "content": content, "time": time_str})

    return templates.TemplateResponse("history.html", {
        "request": request,
        "history": history,
        "uploaded_files": get_uploaded_files(),
        "page": page,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    })