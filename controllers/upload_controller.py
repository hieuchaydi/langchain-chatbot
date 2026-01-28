# controllers/upload_controller.py
# Controller xử lý upload dữ liệu (admin / data loader)
# Chức năng:
# - Hiển thị trang upload tài liệu
# - Nhận file từ client và chuyển cho UploadService xử lý

from fastapi import File, Request, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse
from .base_controller import BaseController
from config.config import settings  
from services.upload_service import UploadService


class UploadController(BaseController):
    # Controller upload dữ liệu
    # Chức năng:
    # - Kết nối giao diện upload với service xử lý backend
    def __init__(self, app, templates):
        super().__init__(app, templates)
        self.service = UploadService()

    # Đăng ký route cho controller
    # Chức năng:
    # - Gán URL với handler tương ứng
    def register(self):
        self.router.get("/data-loader", response_class=HTMLResponse)(self.data_loader_page)
        self.router.post("/upload")(self.upload_files)
        super().register()

    # Trang giao diện upload dữ liệu
    # Chức năng:
    # - Hiển thị chunk size và overlap hiện tại
    # - Cho phép người dùng upload tài liệu
    async def data_loader_page(self, request: Request):
        return self.templates.TemplateResponse(
            "data_loader.html",
            {
                "request": request,
                "chunk_size": settings.CHUNK_SIZE,
                "chunk_overlap": settings.CHUNK_OVERLAP,
            },
        )

    # API nhận file upload
    # Chức năng:
    # - Validate dữ liệu đầu vào
    # - Chuyển file cho UploadService xử lý
    async def upload_files(
        self,
        files: list[UploadFile] = File(...),
        client_start_time: float | None = Form(default=None),
        client_total_size: int | None = Form(default=None),
    ):
        if not files:
            raise HTTPException(status_code=400, detail="No files were uploaded.")

        return await self.service.process(
            files=files,
            client_start_time=client_start_time,
            client_total_size=client_total_size,
        )
