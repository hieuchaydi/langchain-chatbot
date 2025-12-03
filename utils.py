# utils.py 
# • split_text(text, chunk_size=None, chunk_overlap=None)
#       → Chia văn bản thành các chunk theo số từ (word-based)
#       → Tự lấy CHUNK_SIZE & CHUNK_OVERLAP từ config.settings
#       → Có overlap thông minh, luôn trả về ít nhất [""] nếu rỗng
#
# • assign_level(word_count: int) → int (1–5)
#       → Phân cấp độ dài chunk/content để dễ xử lý sau:
#           <100 từ  → level 1
#           <300 từ  → level 2  
#           <600 từ  → level 3
#           <1000 từ → level 4
#           ≥1000 từ → level 5
#       (Dùng để ưu tiên trả lời, tính độ chi tiết, hoặc lọc kết quả)
from config import settings

def split_text(text: str, chunk_size=None, chunk_overlap=None):
    words = text.split()
    size = chunk_size or settings.CHUNK_SIZE
    overlap = chunk_overlap or settings.CHUNK_OVERLAP
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + size])
        chunks.append(chunk)
        i += size - overlap
    return chunks or [""]

# SỬA CHỖ NÀY: nhận word_count thay vì length 
def assign_level(word_count: int) -> int:
    if word_count < 100:   return 1
    if word_count < 300:   return 2
    if word_count < 600:   return 3
    if word_count < 1000:  return 4
    return 5  