from config import config,settings

def split_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> list[str]:
    """Chia văn bản thành chunks theo số từ, có overlap"""
    words = text.split()
    size = chunk_size or config.settings.CHUNK_SIZE
    overlap = chunk_overlap or config.settings.CHUNK_OVERLAP
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + size])
        chunks.append(chunk)
        i += size - overlap
        if i >= len(words):
            break
    return chunks or [""]

def assign_level(word_count: int) -> int:
    """Phân level chunk theo số từ"""
    if word_count < 100: return 1
    if word_count < 300: return 2
    if word_count < 600: return 3
    if word_count < 1000: return 4
    return 5
#curl -X POST "http://127.0.0.1:8000/api/v1/chat" -H "Content-Type: application/json" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NjYxNjQ2NzgsInN1YiI6InBhcnRuZXIifQ.cEPj6jO59AX_26iieoDTAk7gi-UL-QdJloXhwmwvZo4" -d "{\"message\":\"Xin chào\",\"session_id\":\"test\"}"
