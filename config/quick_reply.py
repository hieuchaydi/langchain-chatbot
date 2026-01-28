import random
from pathlib import Path

INTENTS_DIR = Path("data/intents")
GREETINGS_FILE = INTENTS_DIR / "greetings.md"


class QuickReplyHandler:
    def __init__(self):
        self._greetings = self._load_greetings()

        self.identity_keywords = {
            "bạn là ai","bot là ai","giới thiệu bản thân",
            "who are you","what are you","introduce yourself",
        }

        self.thanks_keywords = {
            "cảm ơn","cám ơn","thanks","thank you","tks"
        }

        self.responses = {
            "vi": [
                "Chào bạn! Mình có thể hỗ trợ gì?",
                "Xin chào! Rất vui được trò chuyện cùng bạn.",
            ],
            "en": [
                "Hello! How can I help you?",
                "Hi there! I'm here to help.",
            ],
        }

        self.who_am_i = {
            "vi": "Mình là trợ lý AI được thiết kế để hỗ trợ bạn tra cứu và giải đáp thông tin.",
            "en": "I'm an AI assistant designed to help you find information and answers.",
        }

    def _load_greetings(self) -> set[str]:
        words = {"hi", "hello", "chào", "alo", "hey"}
        if GREETINGS_FILE.exists():
            try:
                for line in GREETINGS_FILE.read_text(encoding="utf-8").splitlines():
                    line = line.strip().lower()
                    if line and not line.startswith("#"):
                        words.add(line)
            except Exception as e:
                print(f"[QuickReply] load greetings error: {e}")
        return words

    def is_greeting_or_thanks(self, message: str) -> bool:
        msg = message.lower().strip()
        if len(msg) > 150:
            return False

        if any(k in msg for k in self.identity_keywords):
            return True
        if any(k in msg for k in self.thanks_keywords):
            return True
        return any(w in msg for w in self._greetings)

    def get_quick_response(self, message: str = "", lang: str = "vi") -> str:
        msg = message.lower()
        if any(k in msg for k in self.identity_keywords):
            return self.who_am_i.get(lang, self.who_am_i["vi"])
        return random.choice(self.responses.get(lang, self.responses["vi"]))


_quick_reply_handler = QuickReplyHandler()

def is_greeting_or_thanks(message: str) -> bool:
    return _quick_reply_handler.is_greeting_or_thanks(message)

def get_quick_response(message: str = "", target_lang: str = "vi") -> str:
    return _quick_reply_handler.get_quick_response(message, target_lang)