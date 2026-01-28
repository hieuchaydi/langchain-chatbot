# controllers/chat_controller.py

from fastapi import Form, Request
from fastapi.responses import HTMLResponse

from .base_controller import BaseController
from services.chat_service import ChatService
from models.db import get_chat_history
from models.db import _db


class ChatController(BaseController):
    def __init__(self, app, templates):
        super().__init__(app, templates)
        self.chat_service = ChatService()

    def register(self):
        self.router.get("/", response_class=HTMLResponse)(self.home)
        self.router.get("/chat", response_class=HTMLResponse)(self.chat_page)
        self.router.post("/chat")(self.chat_web)

        # ===== API cho UI history panel =====
        self.router.get("/sessions")(self.list_sessions)
        self.router.get("/session/{session_id}")(self.load_session)

        # Đăng ký router vào app chính
        self.app.include_router(self.router)

    async def home(self, request: Request):
        return self.templates.TemplateResponse("index.html", {"request": request})

    async def chat_page(self, request: Request):
        return self.templates.TemplateResponse("chat.html", {"request": request})

    async def chat_web(
        self,
        message: str = Form(...),
        session_id: str = Form("default")
    ):
        result = await self.chat_service.process_chat_message(message, session_id)
        return result

    # =========================
    # API: LIST SESSIONS
    # =========================
    async def list_sessions(self):
        conn = _db._get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT session_id, MIN(timestamp) as created_at
            FROM chat_history
            GROUP BY session_id
            ORDER BY created_at DESC
        """)
        rows = c.fetchall()
        conn.close()

        return [
            {"session_id": r[0], "created_at": r[1]}
            for r in rows
        ]

    # =========================
    # API: LOAD 1 SESSION
    # =========================
    async def load_session(self, session_id: str):
        history = get_chat_history(session_id)
        return {"history": history}
