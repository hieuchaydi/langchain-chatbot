from typing import Dict, Any, List, Tuple
from datetime import datetime
from collections import defaultdict
import asyncio

from models.vector_store import VectorStoreManager
from models.db import DatabaseManager
from middleware.badword_filter import BadWordFilter
from models.multilingual_handler import MultilingualHandler
from config.intent_engine import IntentEngine
from config.quick_reply import QuickReplyHandler
from config.cskh_system import CSKHSystem
from models.gemini_client import chat_with_gemini


# Controller xử lý chat theo kiến trúc cũ (all-in-one)
# Chức năng:
# - Điều phối toàn bộ pipeline chat (badword, CSKH, intent, RAG, LLM)
# - Kết hợp vector search + Gemini
# - Lưu lịch sử hội thoại và session memory
class MainController:
    def __init__(self):
        # Vector store để truy vấn dữ liệu
        self.vector_store = VectorStoreManager()

        # Database lưu chat history
        self.db = DatabaseManager()

        # Bộ lọc từ ngữ không phù hợp
        self.badword = BadWordFilter()

        # Handler đa ngôn ngữ
        self.multilingual = MultilingualHandler()

        # Engine phát hiện intent đơn giản
        self.intent = IntentEngine()

        # Quick reply cho chào hỏi / cảm ơn
        self.quick_reply = QuickReplyHandler()

        # Hệ thống chăm sóc khách hàng
        self.cskh = CSKHSystem()

        # Session memory tạm thời (in-memory)
        self.session_memory: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # Hàm xử lý chat chính
    # Chức năng:
    # - Nhận message từ user
    # - Chạy qua các bước lọc & xử lý
    # - Gọi RAG + Gemini để tạo câu trả lời
    async def process_chat_message(
        self,
        message: str,
        session_id: str = "default"
    ) -> Dict[str, Any]:

        message = message.strip()
        if not message:
            return {"response": "Bạn gửi gì đó đi chứ"}

        # Lưu message người dùng
        self.db.save_message("user", message, session_id)

        # Kiểm tra badword
        # Chức năng:
        # - Chặn và phản hồi các nội dung không phù hợp
        if self.badword.contains_swear(message):
            resp = self.badword.get_swear_response()
            self.db.save_message("bot", resp, session_id)
            return {"response": resp}

        # Kiểm tra intent CSKH
        # Chức năng:
        # - Chuyển sang luồng chăm sóc khách hàng nếu cần
        if self.cskh.is_customer_support_intent(message):
            resp = await self.cskh.handle_cskh_transfer(message)
            self.db.save_message("bot", resp, session_id)
            return {"response": resp}

        # Phát hiện intent đặc biệt
        # Chức năng:
        # - Trả lời sẵn nếu match intent
        intent_type = self.intent.detect_intent(message)
        if intent_type:
            resp = self.intent.get_intent_response(intent_type)
            self.db.save_message("bot", resp, session_id)
            return {"response": resp}

        # Quick reply cho chào hỏi / cảm ơn
        if self.quick_reply.is_greeting_or_thanks(message):
            lang = self.multilingual.get_current_language(session_id)
            resp = self.quick_reply.get_quick_response(message, lang)
            self.db.save_message("bot", resp, session_id)
            return {"response": resp, "language": lang}

        # ================= RAG PIPELINE =================
        # Lấy collection từ vector store
        coll = self.vector_store.get_collection()
        raw = coll.get(include=["metadatas"]) or {}
        metadatas = raw.get("metadatas", [])

        # Lấy danh sách source file hiện có
        all_sources = {
            m.get("source", "")
            for m in metadatas
            if isinstance(m, dict)
        }

        # Kiểm tra user có hỏi đích danh 1 file không
        target_file = None
        msg_lower = message.lower()
        for src in all_sources:
            name = src.lower().replace(".md", "")
            if name and name in msg_lower:
                target_file = src
                break

        # Lấy lịch sử session để build query
        history = self.session_memory[session_id]
        query = f"{history[-1]['query']} {message}" if history else message

        chunks: List[Tuple[str, Dict[str, Any]]] = []

        # Nếu chỉ định file → chỉ search trong file đó
        if target_file:
            data = coll.get(
                where={"source": target_file},
                include=["documents", "metadatas"]
            ) or {}
            chunks = list(zip(
                data.get("documents", []),
                data.get("metadatas", [])
            ))
        else:
            # Hybrid search (vector + BM25)
            result = self.vector_store.query_documents(
                query,
                session_id,
                n_results=100,
                alpha=0.7
            ) or ([], [], [])

            docs, metas, _ = result
            chunks = list(zip(docs, metas))

        # Build context cho LLM
        context_parts = []
        for doc, meta in chunks[:25]:
            if not doc:
                continue
            title = (meta or {}).get("title", "")
            text = doc.replace("\n", " ")[:2000]
            context_parts.append(
                f"[{title}]\n{text}" if title else text
            )

        context_text = (
            "\n\n".join(context_parts)
            if context_parts
            else "Hiện tại chưa có thông tin này."
        )

        # Inject BOT RULE đầy đủ trước khi gọi LLM
        self.vector_store.inject_bot_rule(force_full=True)

        # Chuẩn bị history cho Gemini
        history_for_llm: List[Dict[str, str]] = []
        for h in self.session_memory[session_id][-10:]:
            if "query" in h:
                history_for_llm.append({
                    "role": "user",
                    "content": h["query"]
                })
            if "answer" in h:
                history_for_llm.append({
                    "role": "model",
                    "content": h["answer"]
                })

        # Gọi Gemini (chạy thread + timeout)
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    chat_with_gemini,
                    user_question=message,
                    context_text=context_text,
                    history=history_for_llm
                ),
                timeout=30
            )
        except asyncio.TimeoutError:
            response = "Hệ thống đang bận, vui lòng thử lại sau."

        # Lưu phản hồi của bot
        self.db.save_message("bot", response, session_id)

        # Xác định nguồn dữ liệu đã dùng
        sources = (
            [target_file]
            if target_file
            else [
                m.get("source", "")
                for _, m in chunks[:25]
                if isinstance(m, dict)
            ]
        )

        # Cập nhật session memory
        self.session_memory[session_id].append({
            "query": message,
            "answer": response,
            "timestamp": datetime.now().isoformat(),
            "sources": sources
        })

        return {
            "response": response,
            "sources": sources,
            "mode": "forced_file" if target_file else "hybrid_search",
            "chunks_used": len(chunks[:25]),
            "language": self.multilingual.get_current_language(session_id)
        }
