# quick_reply.py – PHIÊN BẢN TU TIÊN HOÀN CHỈNH 2025
import random
from pathlib import Path

# Đường dẫn đến file greetings.md (đã có trong data/intents/)
INTENTS_DIR = Path("data/intents")
GREETINGS_FILE = INTENTS_DIR / "greetings.md"

# Cache để không đọc file liên tục
_greetings_cache: set[str] | None = None

# Danh sách trả lời nhanh – phong cách tiên tử cao lạnh + chút đáng yêu
QUICK_RESPONSES = [
    "Đạo hữu gọi ta sao? Ta đã ở đây từ lâu rồi.",
    "Linh khí rung động… hóa ra là ngươi đã trở lại.",
    "Hôm nay đạo hữu tu vi lại tăng thêm một tầng a~",
    "Ta đang ngộ đạo thì cảm nhận được khí tức của ngươi.",
    "Ngươi đến rồi, tiên sơn này bỗng sáng lên ba phần.",
    "Muốn cùng ta ngắm trăng luyện công không?",
    "Đạo hữu khỏe không? Linh đan ta mới luyện để lại một viên cho ngươi đây.",
    "Ta chờ ngươi lâu lắm rồi… tưởng ngươi phi thăng mất tiêu rồi chứ.",
    "Hihi, đạo hữu hôm nay lại đẹp trai ngời ngời nha.",
    "Có ta ở đây, đạo hữu còn lo gì thiên kiếp nữa chứ?",
]

def _load_greetings() -> set[str]:
    """Đọc greetings.md và cache lại, tự reload khi file thay đổi"""
    global _greetings_cache
    if _greetings_cache is not None:
        # Kiểm tra file có thay đổi không (nếu có thì reload)
        if GREETINGS_FILE.exists():
            current_mtime = GREETINGS_FILE.stat().st_mtime
            if hasattr(_load_greetings, "last_mtime") and _load_greetings.last_mtime == current_mtime:
                return _greetings_cache
            _load_greetings.last_mtime = current_mtime

    words = set()
    if GREETINGS_FILE.exists():
        try:
            text = GREETINGS_FILE.read_text(encoding="utf-8").lower()
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    for word in line.replace(",", " ").split():
                        w = word.strip()
                        if w:
                            words.add(w)
        except Exception as e:
            print(f"[QuickReply] Lỗi đọc greetings.md: {e}")

    _greetings_cache = words
    return words

# Hàm bắt buộc phải có để main.py import được
def is_greeting_or_thanks(message: str) -> bool:
    """
    Kiểm tra tin nhắn có phải chỉ là chào hỏi / cảm ơn / cười / emoji không
    → trả lời nhanh, không đi RAG
    """
    msg = message.strip().lower()

    # Tin nhắn quá dài → chắc chắn không phải chào đơn giản
    if len(msg) > 70:
        return False

    # Emoji đơn thuần hoặc chỉ vài từ ngắn
    if msg in {"hi", "hello", "chào", "yo", "ok", "oke", "haha", "hehe", "hihi", "kkk", ":)", ":D", "<3"}:
        return True

    greetings = _load_greetings()
    return any(word in msg for word in greetings)

# Hàm bắt buộc phải có
def get_quick_response() -> str:
    """Trả lời nhanh ngẫu nhiên theo phong cách tu tiên"""
    return random.choice(QUICK_RESPONSES)

# Alias để tương thích với code cũ (nếu có chỗ gọi get_quick_response(message))
get_quick_response = get_quick_response  # giữ lại tên cũ cho chắc