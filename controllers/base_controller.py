from fastapi import APIRouter

class BaseController:
    def __init__(self, app, templates):
        self.router = APIRouter()
        self.templates = templates
        self.app = app

    def register(self):
        self.app.include_router(self.router)