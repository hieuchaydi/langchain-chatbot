# config/intent_engine.py
"""
Intent Engine – ONLY for social / small-talk
NOT for knowledge questions
"""

import random
from pathlib import Path
from typing import Optional

INTENTS_DIR = Path("data/intents")

# =========================
# LOAD WORD LIST (cached)
# =========================
_cache = {}
_cache_mtime = {}

def _load_words(filename: str) -> set:
    path = INTENTS_DIR / filename
    if not path.exists():
        return set()

    mtime = path.stat().st_mtime
    if filename in _cache and _cache_mtime.get(filename) == mtime:
        return _cache[filename]

    words = set()
    text = path.read_text(encoding="utf-8").lower()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for w in line.replace(",", " ").split():
            words.add(w)

    _cache[filename] = words
    _cache_mtime[filename] = mtime
    return words


# =========================
# KEYWORDS
# =========================
GREETINGS     = _load_words("greetings.md")
CHITCHAT      = _load_words("chitchat.md")
LIGHT_INSULTS = _load_words("light_insults.md")
HEAVY_INSULTS = _load_words("heavy_insults.md")

GOODBYE_WORDS = {"bye", "tạm biệt", "goodbye", "see you", "ngủ ngon"}
THANK_WORDS   = {"cảm ơn", "cám ơn", "thanks", "thank you"}

INTRODUCTION_PATTERNS = {
    "bạn là ai",
    "bot là ai",
    "who are you",
    "what are you",
    "bạn làm gì",
    "bạn giúp gì được",
}

BOT_REFERENCES = {"bạn", "bot", "assistant", "ai", "you"}


# =========================
# RESPONSES
# =========================
RESPONSES_VI = {
    "introduction": [
        "Mình là trợ lý AI, hỗ trợ bạn tra cứu và trả lời câu hỏi.",
    ],
    "greeting": [
        "Chào bạn 👋",
    ],
    "goodbye": [
        "Tạm biệt nhé 👋",
    ],
    "thanks": [
        "Không có gì, rất vui được giúp bạn!",
    ],
    "light_insult": [
        "Mình sẽ cố gắng tốt hơn nhé.",
    ],
    "heavy_insult": [
        "Mình xin lỗi nếu làm bạn khó chịu.",
    ],
    "chitchat": [
        "Hôm nay bạn thế nào?",
    ],
}

RESPONSES_EN = {
    "introduction": [
        "I'm an AI assistant designed to help you.",
    ],
    "greeting": [
        "Hello!",
    ],
    "goodbye": [
        "Goodbye!",
    ],
    "thanks": [
        "You're welcome!",
    ],
    "light_insult": [
        "I'll try to do better.",
    ],
    "heavy_insult": [
        "I'm sorry if I upset you.",
    ],
    "chitchat": [
        "How are you today?",
    ],
}


# =========================
# LANGUAGE DETECTION
# =========================
def detect_language(text: str) -> str:
    try:
        text.encode("ascii")
        return "en"
    except UnicodeEncodeError:
        return "vi"


# =========================
# INTENT DETECTION
# =========================
def detect_intent(message: str) -> Optional[str]:
    msg = message.lower().strip()

    # ❗ social intent thường ngắn, nhưng EN có thể dài hơn
    if len(msg.split()) > 8:
        return None

    if any(w in msg for w in HEAVY_INSULTS):
        return "heavy_insult"
    if any(w in msg for w in LIGHT_INSULTS):
        return "light_insult"

    if any(p in msg for p in INTRODUCTION_PATTERNS) and any(
        r in msg for r in BOT_REFERENCES
    ):
        return "introduction"

    if any(w in msg for w in THANK_WORDS):
        return "thanks"
    if any(w in msg for w in GOODBYE_WORDS):
        return "goodbye"
    if any(w in msg for w in GREETINGS):
        return "greeting"
    if any(w in msg for w in CHITCHAT):
        return "chitchat"

    return None


class IntentEngine:
    @staticmethod
    def detect_intent(message: str):
        return detect_intent(message)

    @staticmethod
    def get_intent_response(message: str, lang: Optional[str] = None):
        intent = detect_intent(message)
        if not intent:
            return None

        if not lang:
            lang = detect_language(message)

        responses = RESPONSES_VI if lang == "vi" else RESPONSES_EN
        candidates = responses.get(intent)

        if not candidates:
            return None

        return random.choice(candidates)
