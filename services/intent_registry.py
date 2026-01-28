# services/intent_registry.py
# Registry quản lý intent và handler tương ứng
# Chức năng:
# - Cho phép đăng ký handler theo (intent_type, intent)
# - Tra cứu handler khi hệ thống xác định được intent
# - Dùng decorator để việc đăng ký gọn và rõ ràng
# - Ghi log toàn bộ quá trình register / get / list

from typing import Dict, Tuple, Type
import logging

# Logger riêng cho intent registry để dễ trace
logger = logging.getLogger("intent_registry")


class IntentRegistry:
    # Khởi tạo registry
    # Chức năng:
    # - Lưu mapping giữa (intent_type, intent) và handler class
    def __init__(self):
        self._registry: Dict[Tuple[str, str], Type] = {}

    # Decorator dùng để đăng ký handler cho một intent
    # Chức năng:
    # - Gắn class handler với cặp (intent_type, intent)
    # - Lưu vào registry trung tâm
    # - Ghi log khi đăng ký thành công
    def register(self, intent_type: str, intent: str):
        def wrapper(cls):
            key = (intent_type, intent)
            self._registry[key] = cls
            logger.info(
                f"[INTENT_REGISTRY] registered {key} -> {cls.__name__}"
            )
            return cls
        return wrapper

    # Lấy handler tương ứng với intent
    # Chức năng:
    # - Tra cứu handler từ registry
    # - Trả về class handler (hoặc None nếu không tồn tại)
    # - Ghi log để debug routing intent
    def get(self, intent_type: str, intent: str):
        key = (intent_type, intent)
        handler = self._registry.get(key)
        logger.info(
            f"[INTENT_REGISTRY] get {key} -> "
            f"{handler.__name__ if handler else None}"
        )
        return handler

    # Lấy toàn bộ danh sách intent đã đăng ký
    # Chức năng:
    # - Phục vụ debug / introspection
    # - Trả về bản copy để tránh sửa trực tiếp registry gốc
    def all(self):
        logger.info(
            f"[INTENT_REGISTRY] all keys = {list(self._registry.keys())}"
        )
        return self._registry.copy()


# Instance dùng chung cho toàn bộ hệ thống
# Các handler sẽ import và đăng ký vào instance này
intent_registry = IntentRegistry()
