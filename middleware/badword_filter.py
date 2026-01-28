# middleware/badword_filter.py
import random
import re
from pathlib import Path

BADWORDS_FILE = Path("data/intents/badwords.md")

# từ ngữ tồi tệ , tránh spam từ ngữ thô tục
class BadWordFilter:
    def __init__(self):
        self.pattern = self._load_pattern()

    def _load_pattern(self):
        words = {"đm", "dm", "cặc", "lồn", "vl", "ngu", "fuck", "shit"}
        if BADWORDS_FILE.exists():
            text = BADWORDS_FILE.read_text(encoding="utf-8").lower()
            words.update(
                line.strip()
                for line in text.splitlines()
                if line.strip() and not line.startswith("#")
            )
        pattern = r'\b(' + '|'.join(map(re.escape, words)) + r')\b'
        return re.compile(pattern, re.IGNORECASE)

    def contains_swear(self, message: str) -> bool:
        return bool(self.pattern.search(message.lower()))

    def get_swear_response(self) -> str:
        responses = [
            "Ủa đại ca chửi em hả? Em buồn 5 giây thôi nha",
            "Trời ơi đại ca nóng tính quá, em sợ á",
            "Đại ca ơi bình tĩnh sống lâu trăm tuổi nè",
            "Má ơi em bị chửi rồi, đau lòng quá đi mất",
        ]
        return random.choice(responses)


_filter = BadWordFilter()

def contains_swear(message: str) -> bool:
    return _filter.contains_swear(message)

def get_swear_response() -> str:
    return _filter.get_swear_response()
