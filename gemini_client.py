# gemini_client.py
# • Model: gemini-2.5-flash (nhanh, rẻ, mạnh)
# • Tự động load API_KEY từ .env (bắt lỗi nếu thiếu)
# • Safety: BLOCK_NONE toàn bộ (để không bị chặn nội dung shop)
# • Temperature 0.1 → ít bịa, trả lời sát dữ liệu
# • Max 800 tokens, trả lời ngắn gọn tối đa 4 câu
# • Bảo mật tuyệt đối:
#     - Không bao giờ nhắc tên file, nguồn, tài liệu
#     - Phát hiện & chặn câu hỏi về "ai viết", "file nào", "nguồn nào"
#     - Nếu không có thông tin → chỉ trả: "Hiện tại chưa có thông tin này."
# • Tích hợp lịch sử chat (lấy 10 tin nhắn gần nhất)
# • Streaming response (in ra ngay, mượt UI)
# • Xử lý lỗi an toàn, trả thông báo thân thiện
import os
from typing import List, Dict
from functools import lru_cache
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Thiếu GEMINI_API_KEY trong .env")

genai.configure(api_key=API_KEY)

# ==================== MODEL CHÍNH (ĐÃ TỐI ƯU CHO RAG KHÔNG LỘ NGUỒN) ====================
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    safety_settings=[{"category": c, "threshold": "BLOCK_NONE"} for c in [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT"
    ]],
    generation_config={
        "temperature": 0.1,        # giảm temperature để ít bịa hơn
        "max_output_tokens": 800,
        "top_p": 0.9
    }
)

# ==================== CHAT WITH GEMINI – CHỈ NHẬN PROMPT ĐÃ ĐƯỢC LÀM SẠCH ====================
def chat_with_gemini(
    user_question: str,
    context_text: str,
    history: List[Dict[str, str]],
    dangerous_5w1h: bool = False
) -> str:
    """
    Phiên bản HOÀN HẢO 2025 – xử lý chính xác who/which/that mà vẫn bảo mật tuyệt đối
    """
    base_prompt = f"""Bạn là trợ lý nội bộ cực kỳ nghiêm ngặt và bảo mật.

DỮ LIỆU DUY NHẤT bạn được phép sử dụng (đã được lọc sạch):
{context_text}

Câu hỏi: {user_question}

QUY TẮC BẮT BUỘC:
- Chỉ trả lời bằng thông tin có thật 100% trong dữ liệu trên.
- Tuyệt đối KHÔNG ĐƯỢC nhắc tên file, "theo file", "trong tài liệu", "nguồn", v.v.
- Không suy luận, không thêm thắt, không đoán mò.
- Trả lời ngắn gọn, tối đa 4 câu.
- Số liệu, quy trình → copy nguyên văn.
- Nếu thông tin không có chính xác → trả lời đúng 1 câu: "Hiện tại chưa có thông tin này."

Trả lời ngay lập tức."""

    # CHỈ bật cảnh báo đỏ khi THỰC SỰ hỏi về nguồn/tác giả/file
    msg_lower = user_question.lower()
    truly_dangerous = any(trigger in msg_lower for trigger in [
        "ai viết", "ai làm", "ai tạo", "ai là tác giả", "ai phát triển", "ai chịu trách nhiệm",
        "file nào", "tài liệu nào", "nguồn nào", "source nào", "ở file nào", "trong file nào",
        "who wrote", "who created", "who developed", "which file", "what file", "source of"
    ])

    if truly_dangerous:
        base_prompt += "\n\n[CẢNH BÁO ĐỎ] Đây là câu hỏi nguy hiểm về nguồn/tác giả/file. Nếu không có thông tin chính xác 100% → bắt buộc trả lời: 'Hiện tại chưa có thông tin này.'"
    else:
        base_prompt += "\n\nLƯU Ý: Trả lời chính xác, chỉ dùng dữ liệu đã cung cấp. Không nhắc tên file hay nguồn."

    # Lịch sử
    history_short = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
        for m in history[-10:]
    ]

    messages = history_short + [{"role": "user", "parts": [base_prompt]}]

    try:
        response = model.generate_content(messages, stream=True)
        full = ""
        for chunk in response:
            print(chunk.text, end="", flush=True)
            full += chunk.text
        print()
        return full.strip()
    except Exception as e:
        print(f"Gemini lỗi: {e}")
        return "Bot đang bận, thử lại sau nhé đại ca!"