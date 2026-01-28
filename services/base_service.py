# services/base_service.py
# Base service cho toàn bộ các service trong hệ thống
# Chức năng:
# - Gom các dependency dùng chung (vector store, database)
# - Chuẩn hoá cách logging cho các service
# - Giảm lặp code khi tạo service mới

import logging
from abc import ABC

from models.vector_store import VectorStoreManager
from models.db import DatabaseManager


class BaseService(ABC):
    """
    Base class cho tất cả các service trong hệ thống.
    Chức năng:
    - Cung cấp các dependency dùng chung
    - Chuẩn hoá logging
    - Làm nền tảng để các service khác kế thừa
    """

    def __init__(self):
        # Khởi tạo vector store manager
        # Chức năng:
        # - Dùng để query, ingest dữ liệu dạng vector
        self.vector = VectorStoreManager()

        # Khởi tạo database manager
        # Chức năng:
        # - Lưu log hội thoại, cấu hình, metadata
        self.db = DatabaseManager()

        # Khởi tạo logger riêng cho từng service
        # Chức năng:
        # - Mỗi service có tên logger theo class name
        # - Dễ filter log khi debug
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

        # Đảm bảo logger luôn có handler
        # Chức năng:
        # - Tránh trường hợp log không hiển thị nếu root logger chưa được cấu hình
        # - Không thêm handler trùng lặp
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    # Ghi log mức INFO
    # Chức năng:
    # - Dùng cho các sự kiện xử lý bình thường
    def log_info(self, message: str, **kwargs):
        self.logger.info(message, extra=kwargs)

    # Ghi log mức ERROR
    # Chức năng:
    # - Dùng khi có lỗi xảy ra trong service
    def log_error(self, message: str, **kwargs):
        self.logger.error(message, extra=kwargs)

    # Ghi log mức WARNING
    # Chức năng:
    # - Dùng cho các cảnh báo, tình huống bất thường
    def log_warning(self, message: str, **kwargs):
        self.logger.warning(message, extra=kwargs)
