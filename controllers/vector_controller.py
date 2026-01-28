# controllers/vector_controller.py
# Controller quản lý vector store (admin / dashboard)
# Chức năng:
# - Quản lý file đã ingest vào vector store
# - Reset toàn bộ vector store
# - Hiển thị danh sách chunk theo từng file
# - Cho phép xoá file hoặc từng chunk riêng lẻ

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from collections import defaultdict
import secrets
import shutil
from pathlib import Path
from models.vector_store import vector_store_manager
from requests import request

from config import config

from .base_controller import BaseController
from models.vector_store import VectorStoreManager, get_stats
from models.db import DatabaseManager
from config.config import Settings


class VectorController(BaseController):
    # Controller quản lý vector store
    # Chức năng:
    # - Kết nối UI quản trị với vector store và database
    def __init__(self, app, templates):
        super().__init__(app, templates)
        self.vector = VectorStoreManager()
        self.db = DatabaseManager()

    # Đăng ký các route cho controller
    # Chức năng:
    # - Map URL với handler tương ứng
    def register(self):
        self.router.post("/delete-file")(self.delete_file)
        self.router.post("/reset-vectorstore")(self.reset_vs)
        self.router.get("/vector-manager", response_class=HTMLResponse)(self.vector_manager)
        self.router.post("/delete-chunk")(self.delete_chunk)

        super().register()

    # Xoá toàn bộ file và chunk tương ứng
    # Chức năng:
    # - Kiểm tra CSRF token
    # - Không cho phép xoá BOT RULE
    # - Xoá file vật lý, DB và vector store
    async def delete_file(
        self,
        request: Request,
        filename: str = Form(...),
        csrf_token: str = Form(...)
    ):
        if request.session.get("csrf_token") != csrf_token:
            return HTMLResponse("CSRF Invalid!", status_code=403)

        # Không bao giờ xoá BOT RULE
        if filename == "bot-rule.md":
            return RedirectResponse("/vector-manager", status_code=303)

        # Xoá file vật lý trong thư mục upload
        file_path = config.settings.UPLOAD_DIR / filename
        file_path.unlink(missing_ok=True)

        # Xoá record trong database
        self.db.delete_uploaded_file(filename)

        # Xoá toàn bộ chunk tương ứng trong vector store
        self.vector.get_collection().delete(where={"source": filename})

        return RedirectResponse("/vector-manager", status_code=303)

    # Reset toàn bộ vector store
    # Chức năng:
    # - Kiểm tra CSRF
    # - Reset vector store + inject lại BOT RULE
    # - Xoá toàn bộ file upload
    # - Clear database liên quan
    async def reset_vs(
        self,
        request: Request,
        csrf_token: str = Form(...)
    ):
        if request.session.get("csrf_token") != csrf_token:
            return HTMLResponse("Unauthorized", status_code=403)

        # Reset vector store
        self.vector.reset_vectorstore()

        # Xoá toàn bộ file upload
        if config.settings.UPLOAD_DIR.exists():
            shutil.rmtree(config.settings.UPLOAD_DIR)
            config.settings.UPLOAD_DIR.mkdir(parents=True)

        # Xoá danh sách file trong database
        self.db.clear_uploaded_files()

        # Sinh lại CSRF token
        request.session["csrf_token"] = secrets.token_hex(16)

        return RedirectResponse("/vector-manager", status_code=303)

    # Trang quản lý vector store
    # Chức năng:
    # - Hiển thị danh sách file và chunk
    # - Thống kê tổng số file, chunk
    async def vector_manager(
        self,
        request: Request,
        limit_per_file: int = 50
    ):
        # Tạo CSRF token cho session
        request.session["csrf_token"] = secrets.token_hex(16)

        coll = vector_store_manager.get_collection()
        data = coll.get(include=["documents", "metadatas"])

        chunks_by_file = defaultdict(list)

        # Gom các chunk theo source file
        for doc_id, doc, meta in zip(
            data.get("ids", []),
            data.get("documents", []),
            data.get("metadatas", [])
        ):
            if meta.get("source") == "BOT_RULE":
                continue

            source = meta.get("source", "unknown.md")

            # Tạo preview ngắn cho mỗi chunk
            preview = " ".join(doc.split()[:30])
            if len(doc.split()) > 30:
                preview += " ..."

            chunks_by_file[source].append({
                "id": doc_id,
                "preview": preview,
                "title": meta.get("title", "Không có tiêu đề"),
                "word_count": len(doc.split()),
                "chunk_type": meta.get("chunk_type", "text"),
                "token_count": meta.get("token_count", 0)
            })

        # Tổng số chunk (trước khi giới hạn hiển thị)
        total_chunks = sum(len(chunks) for chunks in chunks_by_file.values())

        # Giới hạn số chunk hiển thị trên mỗi file
        for source in chunks_by_file:
            chunks_by_file[source] = chunks_by_file[source][:limit_per_file]

        total_files = len(chunks_by_file)

        # Render giao diện quản lý vector
        return self.templates.TemplateResponse(
            "vector_manager.html",
            {
                "request": request,
                "chunks_by_file": dict(chunks_by_file),
                "total_chunks": total_chunks,
                "total_files": total_files,
                "stats": get_stats(),
                "csrf_token": request.session["csrf_token"]
            }
        )

    # Xoá một chunk riêng lẻ
    # Chức năng:
    # - Kiểm tra CSRF
    # - Xoá chunk theo id trong vector store
    async def delete_chunk(
        self,
        chunk_id: str = Form(...),
        csrf_token: str = Form(...)
    ):
        if "csrf_token" not in request.session or request.session["csrf_token"] != csrf_token:
            return JSONResponse(
                {"status": "error", "message": "CSRF invalid"},
                status_code=403
            )

        try:
            self.vector.get_collection().delete(ids=[chunk_id])
            return JSONResponse({"status": "ok"})
        except Exception as e:
            print(f"[VectorController] Delete chunk error: {e}")
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=500
            )
