from fastapi import Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pathlib import Path
from .base_controller import BaseController
from models.db import DatabaseManager
from config.config import settings

class ConfigController(BaseController):
    def __init__(self, app, templates):
        super().__init__(app, templates)
        self.db = DatabaseManager()

    def register(self):
        self.router.get("/get-current-prompt")(self.get_prompt)
        self.router.get("/config", response_class=HTMLResponse)(self.config_page)
        self.router.post("/update-config")(self.update_config)
        super().register()

    async def get_prompt(self):
        return PlainTextResponse(self.db.get_system_prompt())

    async def config_page(self, request: Request):
        prompt_path = Path("data/systemprompt.md")
        raw = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "# Chưa có file systemprompt.md"
        beautiful = "\n".join(line.rstrip() for line in raw.splitlines()).strip() + "\n"
        return self.templates.TemplateResponse("config.html", {
            "request": request, "chunk_size": settings.CHUNK_SIZE,
            "chunk_overlap": settings.CHUNK_OVERLAP, "bot_rules": beautiful,
            "model_name": "gemini-2.5-flash"
        })

    async def update_config(self, chunk_size: int = Form(...), chunk_overlap: int = Form(...),
                            bot_rules: str = Form(...), reingest: bool = Form(False)):
        from services.config_service import ConfigService
        service = ConfigService()
        return await service.update(chunk_size, chunk_overlap, bot_rules, reingest)