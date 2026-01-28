# services/upload_service.py
# Service xử lý upload file tài liệu
# Chức năng:
# - Nhận và validate file upload
# - Ghi nội dung vào vector store để tìm kiếm
# - Lưu file vật lý và metadata
# - Tính tốc độ upload thực tế (nếu client gửi lên)
# - Trả kết quả tổng hợp cho client

import time
from fastapi.responses import JSONResponse
from models.vector_store import vector_store_manager
from config.config import settings
from services.base_service import BaseService
from config import config


class UploadService(BaseService):
    # Hàm xử lý upload chính
    # Chức năng:
    # - Duyệt danh sách file upload
    # - Phân loại file thêm mới / cập nhật / lỗi
    # - Thực hiện lưu vector, lưu file, ghi DB
    # - Tổng hợp kết quả và trả response
    async def process(self, files, client_start_time=None, client_total_size=None):
        t0 = time.time()

        # Tổng dung lượng thực tế của các file đọc được
        total_size = 0

        # Danh sách kết quả theo từng trạng thái
        success, updated, failed = [], [], []

        # Tốc độ upload thực tế (MB/s), chỉ tính nếu client cung cấp đủ thông tin
        real_speed = None

        # Tính tốc độ upload phía client gửi lên
        if client_start_time and client_total_size:
            duration = t0 - (client_start_time / 1000)
            if duration > 0:
                real_speed = client_total_size / duration / 1024 / 1024

        # Lấy collection hiện tại từ vector store
        coll = vector_store_manager.get_collection()

        # Lấy danh sách file đã tồn tại trong vector store (theo metadata source)
        existing = {
            m.get("source")
            for m in coll.get(include=["metadatas"])["metadatas"]
            if m
        }

        # Xử lý từng file upload
        for file in files:
            # Kiểm tra định dạng file được hỗ trợ
            if not file.filename.lower().endswith((".md", ".markdown", ".txt")):
                failed.append(f"{file.filename} → chỉ hỗ trợ .md/.txt")
                continue

            try:
                # Đọc nội dung file
                content = await file.read()
                total_size += len(content)

                # Decode nội dung sang text để đưa vào vector store
                text = content.decode("utf-8", errors="ignore")

                filename = file.filename

                # Nếu file đã tồn tại → xóa vector cũ và đánh dấu là cập nhật
                if filename in existing:
                    coll.delete(where={"source": filename})
                    updated.append(filename)
                else:
                    success.append(filename)

                # Thêm nội dung file vào vector store
                vector_store_manager.add_documents(text, filename)

                # Lưu file vật lý xuống thư mục upload
                path = config.settings.UPLOAD_DIR / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

                # Ghi thông tin file vào database
                self.db.add_uploaded_file(filename)

                # Ghi log upload thành công
                self.log_info("Upload thành công", file_name=filename, size=len(content))

            except Exception as e:
                # Bắt lỗi trong quá trình xử lý từng file
                error_msg = f"{file.filename} → lỗi: {str(e)}"
                failed.append(error_msg)
                self.log_error(
                    "Upload thất bại",
                    filename=file.filename,
                    error=str(e)
                )

        # Trả kết quả tổng hợp cho client
        return JSONResponse({
            "status": "done",
            "added": len(success),
            "updated": len(updated),
            "failed": len(failed),
            "msg": f"HOÀN TẤT! Thêm: {len(success)} • Cập nhật: {len(updated)} • Lỗi: {len(failed)}",
            "real_speed": f"{real_speed:.2f}" if real_speed else None,
            "detail": {
                "added": success,
                "updated": updated,
                "failed": failed
            }
        })
