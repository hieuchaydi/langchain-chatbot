from fastapi import Request
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
from .base_controller import BaseController
from models.db import DatabaseManager

class HistoryController(BaseController):
    def __init__(self, app, templates):
        super().__init__(app, templates)
        self.db = DatabaseManager()

    def register(self):
        self.router.get("/history", response_class=HTMLResponse)(self.history_page)
        super().register()

    async def history_page(self, request: Request, page: int = 1):
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
        return self.templates.TemplateResponse("history.html", {
            "request": request, "history": history, "uploaded_files": self.db.get_uploaded_files(),
            "page": page, "total_pages": total_pages,
            "has_prev": page > 1, "has_next": page < total_pages
        })