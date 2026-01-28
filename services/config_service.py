# services/config_service.py
# Service quản lý cấu hình hệ thống
# Chức năng:
# - Cập nhật các tham số xử lý văn bản (chunk size, overlap)
# - Lưu system prompt (bot rules)
# - Quyết định có cần re-ingest dữ liệu hay không
# - Thực hiện re-ingest toàn bộ tài liệu khi cần

from fastapi.responses import JSONResponse

from config import config
from services.base_service import BaseService
from services.utils import split_text


class ConfigService(BaseService):
    # Cập nhật cấu hình hệ thống
    # Chức năng:
    # - Nhận cấu hình mới từ client
    # - Lưu vào settings và database
    # - Trigger re-ingest dữ liệu nếu cấu hình thay đổi
    async def update(
        self,
        chunk_size: int,
        chunk_overlap: int,
        bot_rules: str,
        reingest: bool = False
    ):
        # Lưu lại cấu hình cũ để so sánh
        old_chunk = config.settings.CHUNK_SIZE
        old_overlap = config.settings.CHUNK_OVERLAP

        # Cập nhật cấu hình mới trong runtime settings
        config.settings.CHUNK_SIZE = chunk_size
        config.settings.CHUNK_OVERLAP = chunk_overlap

        # Lưu cấu hình vào database để persist
        self.db.set_config("chunk_size", str(chunk_size))
        self.db.set_config("chunk_overlap", str(chunk_overlap))

        # Cập nhật system prompt cho chatbot
        self.db.set_system_prompt(bot_rules)

        # Xác định có cần re-ingest hay không
        need_reingest = (
            old_chunk != chunk_size
            or old_overlap != chunk_overlap
        ) or reingest

        msg = "Lưu cấu hình thành công!"

        # Thực hiện re-ingest nếu cần và có dữ liệu upload
        if need_reingest and list(config.settings.UPLOAD_DIR.glob("*.md")):
            self.log_info("Bắt đầu re-ingest do thay đổi chunk size/overlap")

            # Reset toàn bộ vector store trước khi ingest lại
            self.vector.reset_vectorstore()

            total_files = 0
            total_chunks = 0

            # Duyệt lại toàn bộ file đã upload
            for fp in config.settings.UPLOAD_DIR.glob("*.md"):
                text = fp.read_text(encoding="utf-8")

                # Chia nhỏ nội dung theo chunk size và overlap mới
                chunks = split_text(text, chunk_size, chunk_overlap)

                if chunks:
                    # Đưa các chunk mới vào vector store
                    self.vector.query_documents(
                        "\n\n".join(chunks),
                        fp.name
                    )
                    total_files += 1
                    total_chunks += len(chunks)

            msg = f"RE-INGEST HOÀN TẤT! {total_files} file → {total_chunks} chunks"
            self.log_info(
                "Re-ingest hoàn tất",
                files=total_files,
                chunks=total_chunks
            )

        # Trả kết quả cập nhật cấu hình cho client
        return JSONResponse({
            "msg": msg,
            "reingested": need_reingest
        })
