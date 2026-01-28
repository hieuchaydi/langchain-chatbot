from typing import Dict, Any, List, Optional
"""
Chat Service Module

ChatService v4.5.0 (Token-Optimized CSKH + Summary Memory)
- Không gọi Gemini cho:
  - social
  - small talk
  - deny
  - product inquiry
  - quick reply
- Gemini chỉ là fallback classifier
- Giữ nguyên:
  - CSKH routing
  - Hidemium priority
  - query expansion
  - multi-language
  - deny + escalation
- Bổ sung:
  - Summary hội thoại cross-session
  - Auto summarize
  - Inject summary vào RAG
"""

import asyncio
import logging
import os
import re

from services.intent_registry import intent_registry
from config.quick_reply import QuickReplyHandler
from models.vector_store import VectorStoreManager, SESSION_MEMORY
from models.db import (
    save_message,
    save_conversation_summary,
    load_latest_summary,
    load_messages
)
from middleware.badword_filter import contains_swear, get_swear_response
from models.gemini_analyzer import analyze_question, translate_text


LOG_DIR = "log"
os.makedirs(LOG_DIR, exist_ok=True)

pipeline_logger = logging.getLogger("chat_pipeline")
pipeline_logger.setLevel(logging.INFO)
pipeline_logger.propagate = False

if not pipeline_logger.handlers:
    handler = logging.FileHandler(
        os.path.join(LOG_DIR, "chat_pipeline.log"),
        encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )
    handler.setFormatter(formatter)
    pipeline_logger.addHandler(handler)


def log_flow(step: str, data: Optional[Dict[str, Any]] = None):
    if data:
        pipeline_logger.info(f"[FLOW] {step} | {data}")
    else:
        pipeline_logger.info(f"[FLOW] {step}")


SUMMARY_MIN_TURNS = 10


async def summarize_session(session_id: str) -> str:
    messages = load_messages(session_id, limit=50)
    if not messages:
        return ""

    text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    summary = text.strip()

    log_flow("summary_generated_raw", {"preview": summary[:120]})
    return summary


# =========================
# SOCIAL / SMALL TALK
# =========================

SOCIAL_RESPONSES = {
    "vi": {
        "greeting": "Chào bạn 👋",
        "thanks": "Không có gì, rất vui được giúp bạn!",
        "goodbye": "Tạm biệt nhé 👋",
        "introduction": "Mình là trợ lý AI hỗ trợ khách hàng, rất vui được hỗ trợ bạn ạ.",
        "chitchat": "Chào bạn! Mình có thể hỗ trợ bạn về vấn đề gì hôm nay?",
        "who_are_you": "Mình là trợ lý AI hỗ trợ khách hàng của công ty ạ. Rất vui được gặp bạn!",
        "what_doing": "Mình đang ở đây chờ hỗ trợ bạn nè 😄 Bạn cần giúp gì hôm nay?",
    },
    "en": {
        "greeting": "Hello 👋",
        "thanks": "You're welcome!",
        "goodbye": "Goodbye 👋",
        "introduction": "I'm an AI customer support assistant designed to help you.",
        "chitchat": "Hi there! How can I help you today?",
        "who_are_you": "I'm your AI customer support assistant. Nice to meet you!",
        "what_doing": "Just here waiting to assist you 😄 What's on your mind?",
    },
    "zh": {
        "greeting": "你好 👋",
        "thanks": "不客气！",
        "goodbye": "再见 👋",
        "introduction": "我是AI客户支持助手，很高兴为您服务。",
        "chitchat": "你好！今天我能帮您什么？",
        "who_are_you": "我是您的AI客户支持助手，很高兴认识您！",
        "what_doing": "我在这里等着帮您呢 😄 您有什么需要？",
    },
    "ru": {
        "greeting": "Привет 👋",
        "thanks": "Пожалуйста!",
        "goodbye": "До свидания 👋",
        "introduction": "Я AI-ассистент поддержки клиентов, рад вам помочь.",
        "chitchat": "Привет! Чем могу помочь сегодня?",
        "who_are_you": "Я ваш AI-ассистент поддержки. Приятно познакомиться!",
        "what_doing": "Я здесь, чтобы помочь вам 😄 О чем думаете?",
    },
}

SOCIAL_STARTERS = {
    "vi": [
        "hi", "hello", "hey", "xin chào", "chào", "chào bạn", "chào anh", "chào chị",
        "bạn là ai", "bạn tên gì", "ai vậy",
        "đang làm gì", "làm gì đấy", "đang làm gì thế",
        "chào buổi sáng", "chào buổi chiều", "chào buổi tối",
    ],
    "en": [
        "hi", "hello", "hey",
        "who are you", "what's your name",
        "what are you doing", "how are you",
        "good morning", "good afternoon", "good evening",
    ],
    "zh": [
        "你好", "嗨", "你是谁", "你叫什么名字",
        "你在做什么", "你好吗",
    ],
    "ru": [
        "привет", "кто ты", "как тебя зовут",
        "чем занимаешься", "как дела",
    ],
}

SMALL_TALK_PATTERNS = {
    "vi": {
        r"(bạn|em|mình).*(khỏe|ổn|thế nào)": "Mình khỏe lắm ạ, cảm ơn bạn hỏi! Còn bạn thì sao? 😊",
        r"(đang làm gì|đang làm)": "Đang chờ hỗ trợ bạn đây ạ 😄 Bạn cần giúp gì nào?",
    },
    "en": {
        r"(you).*(good|fine|how)": "I'm doing great, thanks! How about you? 😊",
        r"(what.*doing)": "Just here to help you out 😄 What's up?",
    },
    "zh": {
        r"(你).*(好|怎么样)": "我很好，谢谢！您呢？ 😊",
        r"(在做什么)": "就在这里帮您 😄 您需要什么帮助？",
    },
    "ru": {
        r"(ты).*(хорошо|как)": "У меня все хорошо, спасибо! А у вас? 😊",
        r"(чем.*занимаешься)": "Просто здесь, чтобы помочь вам 😄 Что у вас?",
    },
}

DENY_KEYWORDS = {
    "vi": ["sai rồi", "không đúng", "không phải", "tôi không muốn", "không phải vậy", "lại sai"],
    "en": ["not correct", "wrong", "that's wrong", "incorrect", "not right", "not what i want", "nope", "that's not it"],
    "zh": ["不对", "错了", "不是这样"],
    "ru": ["неправильно", "не то", "ошибка"],
}

PRODUCT_KEYWORDS = {
    "vi": [
        "hidemium", "api hidemium", "hidemium api", "hidemium là gì",
        "dịch vụ hidemium", "hidemium proxy", "ẩn danh hidemium",
    ],
    "en": [
        "hidemium", "hidemium api", "what is hidemium",
        "hidemium proxy", "tell me about hidemium",
    ],
    "zh": ["hidemium", "hidemium api"],
    "ru": ["hidemium", "hidemium api"],
}


def detect_language(text: str) -> str:
    if re.search(r'[\u4e00-\u9fff]', text):
        return "zh"
    if re.search(r'[\u0400-\u04ff]', text):
        return "ru"
    try:
        text.encode("ascii")
        return "en"
    except UnicodeEncodeError:
        return "vi"



def translate_to_vi(text: str, src_lang: str) -> str:
    if src_lang == "vi":
        return text
    return text

def detect_anchor_reference(message: str) -> Optional[int]:
    msg = message.lower()

    # match: "câu 2", "câu hỏi 3", "quay lại câu 4"
    m = re.search(r"câu(?:\s+hỏi)?\s*(\d+)", msg)
    if m:
        return int(m.group(1)) - 1

    return None



def translate_from_vi(text: str, target_lang: str) -> str:
    if target_lang == "vi":
        return text
    return text


def is_valid_chunk(text: str) -> bool:
    text = text.strip()
    if not text or text in {"--", "-", "..."}:
        return False
    if len(text) < 15:
        return False
    return True


def build_answer_from_chunks(
    docs: List[str],
    query: Optional[str] = None,
    max_chars: int = 800
) -> str:
    valid_docs = []
    for d in docs:
        if not d:
            continue
        d = d.strip()
        if len(d) < 15:
            continue
        if d in {"--", "-", "...", "---"}:
            continue
        valid_docs.append(d)

    if not valid_docs:
        return ""

    best_docs = valid_docs

    if query:
        q = query.lower()
        q = re.sub(r"[^\w\sÀ-ỹ]", " ", q)
        q = re.sub(r"\s+", " ", q).strip()

        tokens = [t for t in q.split() if len(t) > 2]

        def soft_match(doc: str) -> bool:
            dl = doc.lower()
            hit = sum(1 for t in tokens if t in dl)
            return hit >= max(1, len(tokens) // 3)

        matched = [d for d in valid_docs if soft_match(d)]
        if matched:
            best_docs = matched

    text = best_docs[0]

    match = re.search(r"\*\*?A:\*\*?\s*(.+)", text, re.DOTALL | re.IGNORECASE)
    extracted = match.group(1).strip() if match else text.strip()

    extracted = re.sub(r"^#+\s*", "", extracted)
    extracted = re.sub(r"(?m)^\s*#+\s*", "", extracted)
    extracted = re.sub(r"###\s*MỤC:.*", "", extracted, flags=re.IGNORECASE)
    extracted = re.sub(r"MỤC:\s*[^\n]+", "", extracted, flags=re.IGNORECASE)
    extracted = re.sub(r"\*\*?Q:\*\*?\s*.*", "", extracted, flags=re.IGNORECASE)
    extracted = re.sub(r"\*\*(.*?)\*\*", r"\1", extracted)
    extracted = re.sub(r"(?m)^\s*-{3,}\s*$", "", extracted)
    extracted = re.sub(r"(?m)^\s*-\s*", "• ", extracted)
    extracted = re.sub(r"\n{3,}", "\n\n", extracted)
    extracted = extracted.strip()

    return extracted[:max_chars].strip()


def wrap_cskh_answer(answer: str, lang: str) -> str:
    if not answer:
        return answer

    suffixes = {
        "vi": "Bạn cần hỗ trợ thêm gì không ạ? 😊",
        "en": "Anything else I can help with? 😊",
        "zh": "还有什么我能帮您的吗？ 😊",
        "ru": "Чем еще могу помочь? 😊",
    }

    return f"{answer} {suffixes.get(lang, suffixes['en'])}"


def build_alternative_answer(docs: List[str], lang: str) -> str:
    prefixes = {
        "vi": "Có thể mình đã hiểu chưa đúng trường hợp của bạn.\nTrong tài liệu hiện có, mình thấy các thông tin sau:\n",
        "en": "Maybe I didn't understand your case correctly.\nIn the current documentation, I found the following:\n",
        "zh": "可能我没完全理解您的情况。\n在现有文档中，我找到以下信息：\n",
        "ru": "Возможно, я не совсем понял ваш случай.\nВ документации я нашел следующее:\n",
    }

    text = prefixes.get(lang, prefixes["en"])

    for i, d in enumerate(docs[:3]):
        summary_vi = build_answer_from_chunks([d])
        summary = translate_from_vi(summary_vi, lang)
        label = chr(65 + i)
        text += f"• Trường hợp {label}: {summary}\n" if lang == "vi" else f"• Case {label}: {summary}\n"

    questions = {
        "vi": "\nBạn đang quan tâm trường hợp nào để mình hỗ trợ chính xác hơn nhé?",
        "en": "\nWhich case are you referring to so I can assist more accurately?",
        "zh": "\n您关心哪个情况，让我更准确地帮助您？",
        "ru": "\nКакой случай вас интересует, чтобы я мог помочь точнее?",
    }

    text += questions.get(lang, questions["en"])
    return text


# =========================
# CHAT SERVICE
# =========================

class ChatService:

    def __init__(self):
        self.vector = VectorStoreManager()
        self.quick_reply = QuickReplyHandler()

    async def process_chat_message(
        self,
        message: str,
        session_id: str = "default"
    ) -> Dict[str, Any]:

        pipeline_logger.info("=" * 80)
        pipeline_logger.info(f"[INPUT] {message}")

        message = message.strip()
        if not message:
            return {"response": "Please say something 😅"}

        # =========================
        # LOAD SESSION + SUMMARY
        # =========================
        session = SESSION_MEMORY.setdefault(session_id, {})

        user_id = session_id  # tạm thời dùng session_id

        if "summary" not in session:
            old_summary = load_latest_summary(user_id,session_id)
            session["summary"] = old_summary or ""
            if old_summary:
                log_flow("summary_loaded", {"preview": old_summary[:120]})

        save_message("user", message, session_id=session_id)

        # =========================
        # AUTO SUMMARY TRIGGER
        # =========================
        messages = load_messages(session_id, limit=SUMMARY_MIN_TURNS * 2)
        if len(messages) >= SUMMARY_MIN_TURNS * 2:
            summary = await summarize_session(session_id)
            if summary:
                save_conversation_summary(user_id,session_id, summary)
                session["summary"] = summary
                log_flow("summary_saved", {"preview": summary[:120]})

        user_lang = detect_language(message)

        support_state = session.setdefault("support_state", {
            "phase": "idle",
            "last_query": None,
            "last_answer": None,
            "deny_count": 0,
            "language": user_lang,
            "escalated": False,
            "summary": session.get("summary", ""),
            "query_history": [],
            "context_anchors": {}
        })

        support_state["language"] = user_lang
        support_state["summary"] = session.get("summary", "")

        msg_lc = message.lower()

        deny_list = DENY_KEYWORDS.get(user_lang, [])
        if support_state["deny_count"] > 0 and not any(x in msg_lc for x in deny_list):
            support_state["deny_count"] = 0

        # 1) DENY
        if any(x in msg_lc for x in deny_list):
            resp = await self.handle_deny(support_state)
            if support_state["deny_count"] >= 3:
                support_state["escalated"] = True
            save_message("bot", resp, session_id)
            log_flow("handling_deny", {"deny_count": support_state["deny_count"]})
            return {"response": resp, "mode": "cskh_deny"}

        # 2) PRODUCT PRIORITY
        product_keywords_all = PRODUCT_KEYWORDS.get(user_lang, []) + PRODUCT_KEYWORDS.get("en", [])
        if any(kw in msg_lc for kw in product_keywords_all) and support_state["deny_count"] == 0:
            log_flow("route_product_inquiry", {"query": message, "lang": user_lang})
            return await self.handle_knowledge_flow(message, support_state, session_id)

        # 3) SMALL TALK
        for pattern, reply in SMALL_TALK_PATTERNS.get(user_lang, {}).items():
            if re.search(pattern, msg_lc):
                save_message("bot", reply, session_id)
                log_flow("small_talk_hit", {"pattern": pattern})
                return {"response": reply, "mode": "small_talk"}

        # 4) SOCIAL
        starters = SOCIAL_STARTERS.get(user_lang, [])
        for x in starters:
            pattern = r"\b" + re.escape(x) + r"\b"
            if re.search(pattern, msg_lc):
                responses = SOCIAL_RESPONSES.get(user_lang, SOCIAL_RESPONSES["en"])
                if any(y in msg_lc for y in ["là ai", "who are you"]):
                    answer = responses["who_are_you"]
                elif any(y in msg_lc for y in ["làm gì", "doing"]):
                    answer = responses["what_doing"]
                else:
                    answer = responses["chitchat"]

                save_message("bot", answer, session_id)
                log_flow("route_cskh_social_hard", {"answer": answer})
                return {"response": answer, "mode": "social"}

        # 5) BAD WORD
        if contains_swear(message):
            resp = get_swear_response()
            save_message("bot", resp, session_id)
            return {"response": resp}

        # 6) QUICK REPLY
        if len(message) <= 8:
            qr = self.quick_reply.get_quick_response(message)
            if qr:
                save_message("bot", qr, session_id)
                return {"response": qr, "mode": "quick_reply"}

        # 7) GEMINI FALLBACK CLASSIFIER
        intent_type = "knowledge"
        intent = "unknown"

        log_flow("intent_llm_probe", {"message": message})

        try:
            analysis = await asyncio.to_thread(analyze_question, message)
            intent_type = analysis.get("type", "knowledge")
            intent = analysis.get("intent", "unknown")
            log_flow("intent_detected", {"type": intent_type, "intent": intent})
        except Exception as e:
            log_flow("intent_llm_error", {"error": str(e)})

        # 8) SOCIAL FALLBACK
        if intent_type == "social":
            responses = SOCIAL_RESPONSES.get(user_lang, SOCIAL_RESPONSES["en"])
            answer = responses.get("chitchat", responses["chitchat"])
            save_message("bot", answer, session_id)
            return {"response": answer, "mode": "social"}

        # 9) ACTION INTENT
        handler_cls = intent_registry.get(intent_type, intent)
        if handler_cls:
            handler = handler_cls()
            resp = await handler.handle(session)
            return resp

        # 10) DEFAULT KNOWLEDGE
        return await self.handle_knowledge_flow(message, support_state, session_id)

    async def handle_knowledge_flow(
        self,
        message: str,
        support_state: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:

        support_state["phase"] = "answering"

        user_lang = support_state["language"]
        query_vi = translate_to_vi(message, user_lang)
        anchor_idx = detect_anchor_reference(message)
        log_flow("anchor_detected", {
            "raw_message": message,
            "anchor_idx": anchor_idx
        })

        if anchor_idx is not None:
            anchors = support_state.get("context_anchors", {})
            base_ctx = anchors.get(anchor_idx)

            if base_ctx:
                query_vi = f"{base_ctx}\n{query_vi}"
                log_flow("anchor_context_injected", {
                    "anchor_idx": anchor_idx,
                    "anchor_preview": base_ctx[:120]
                })

# =========================
# INJECT SUMMARY CONTEXT (SAFE)
# =========================
        summary_ctx = support_state.get("summary") or ""

        def same_topic(summary: str, query: str) -> bool:
            s = summary.lower()
            q = query.lower()

            # rule tối thiểu: cùng nhắc Hidemium thì mới inject
            if "hidemium" in s and "hidemium" in q:
                return True

            # sau này mở rộng thêm topic khác ở đây
            return False

        if summary_ctx and same_topic(summary_ctx, query_vi):
            query_vi = f"{summary_ctx}\n{query_vi}"
            log_flow("summary_injected", {"len": len(summary_ctx)})
        else:
            if summary_ctx:
                log_flow("summary_skipped_topic_mismatch", {
                    "summary_preview": summary_ctx[:120],
                    "query": query_vi
                })


        # =========================
        # NORMALIZE QUERY
        # =========================
        query_vi = re.sub(r"[^\w\sÀ-ỹ]", " ", query_vi)
        query_vi = re.sub(r"\s+", " ", query_vi).strip()
        log_flow("query_normalized", {
            "query_vi": query_vi
        })

        qh = support_state.setdefault("query_history", [])
        anchors = support_state.setdefault("context_anchors", {})
        if anchor_idx is None:
            qh.append(query_vi)
            idx = len(qh) - 1
            anchors[idx] = query_vi
            log_flow("anchor_saved", {
                "idx": idx,
                "query_preview": query_vi[:120]
            })
        else:
            log_flow("anchor_skipped_save", {
                "anchor_idx": anchor_idx,
                "query_preview": query_vi[:120]
            })

        if support_state.get("last_query") and support_state["last_query"] != query_vi:
            support_state["deny_count"] = 0
            log_flow("deny_reset_check", {
            "last_query": support_state.get("last_query"),
            "current_query": query_vi,
            "deny_count_after": support_state["deny_count"]
        })

        # nếu user đang quay lại câu cũ → last_query = base_ctx
        if anchor_idx is not None and base_ctx:
            support_state["last_query"] = base_ctx
            log_flow("last_query_set_from_anchor", {
                "last_query_preview": base_ctx[:120]
            })
        else:
            support_state["last_query"] = query_vi
            log_flow("last_query_set_from_current", {
                    "last_query_preview": query_vi[:120]
                })


        docs = []
        metas = []

        if "hidemium" in query_vi.lower():
            expanded_queries = [
                query_vi,
                "Hidemium API là gì",
                "Hidemium là gì",
                "dịch vụ Hidemium API",
                "tính năng Hidemium API",
                "cách sử dụng Hidemium",
            ]

            all_docs = []
            all_metas = []

            for q in expanded_queries:
                d, m, _ = self.vector.query_documents(
                    query=q, user_id=session_id, n_results=15
                )
                all_docs.extend(d)
                all_metas.extend(m)

            seen = set()
            docs = []
            metas = []

            for d, m in zip(all_docs, all_metas):
                key = d[:120]
                if key in seen:
                    continue
                seen.add(key)
                docs.append(d)
                metas.append(m)

            docs = docs[:40]
            metas = metas[:40]

            log_flow("query_expansion", {
                "original": query_vi,
                "expanded_count": len(expanded_queries)
            })
        else:
            docs, metas, _ = self.vector.query_documents(
                query=query_vi, user_id=session_id, n_results=20
            )

        log_flow("rag_docs_debug", {
            "query": query_vi,
            "doc_count": len(docs),
            "sources": list({
                m.get("source") for m in metas if m and m.get("source")
            }),
            "doc_previews": [d[:120] for d in docs[:5]]
        })

        answer_vi = build_answer_from_chunks(docs, query_vi)

        if not answer_vi or len(answer_vi.strip()) < 30:
            if "hidemium" in query_vi.lower():
                answer_vi = (
                    "Hidemium API là bộ API cho phép bạn tạo, quản lý và khởi chạy "
                    "các browser profile Hidemium từ tool bên ngoài. "
                    "API thường dùng để tích hợp với Puppeteer, Playwright "
                    "hoặc automation framework riêng.\n\n"
                    "Bạn đang muốn:\n"
                    "• Điều khiển profile qua API?\n"
                    "• Kết nối với Puppeteer/Playwright?\n"
                    "• Hay build tool riêng dùng profile Hidemium?"
                )
            else:
                answer_vi = (
                    "Mình chưa tìm thấy thông tin phù hợp trong tài liệu hiện tại. "
                    "Bạn có thể mô tả chi tiết hơn được không ạ? 😊"
                )

        support_state["last_answer"] = answer_vi

        answer = answer_vi
        if user_lang != "vi":
            log_flow("translate_output_llm", {"lang": user_lang})
            answer = await asyncio.to_thread(
                translate_text, answer_vi, user_lang
            )

        answer = wrap_cskh_answer(answer, user_lang)

        log_flow("rag_response", {"answer_preview": answer[:150]})
        save_message("bot", answer, session_id)

        return {"response": answer, "mode": "knowledge"}

    async def handle_deny(self, support_state: Dict[str, Any]) -> str:

        support_state["phase"] = "handling_deny"
        support_state["deny_count"] += 1

        last_query_vi = support_state.get("last_query")
        log_flow("deny_using_last_query", {
            "last_query_preview": (last_query_vi or "")[:120],
            "deny_count": support_state["deny_count"]
        })

        lang = support_state["language"]

        if support_state["deny_count"] >= 3:
            escalations = {
                "vi": (
                    "Mình xin lỗi vì chưa hỗ trợ đúng. "
                    "Mình sẽ chuyển bạn sang bộ phận CSKH nhé. "
                    "Bạn để lại thông tin để bên mình liên hệ hỗ trợ ạ 😊"
                ),
                "en": (
                    "Sorry I couldn't get it right yet. "
                    "I'll escalate to our support team. "
                    "Please leave your details 😊"
                ),
                "zh": (
                    "很抱歉目前还没能正确帮助您。"
                    "我会将您的问题转交给我们的支持团队。"
                    "请留下您的联系方式 😊"
                ),
                "ru": (
                    "Извините, мне пока не удалось помочь правильно. "
                    "Я передам ваш вопрос нашей службе поддержки. "
                    "Пожалуйста, оставьте свои контактные данные 😊"
                ),
            }
            return escalations.get(lang, escalations["en"])

        if support_state["deny_count"] == 2 and last_query_vi:
            rephrased = last_query_vi + " các trường hợp"
            docs, _, _ = self.vector.query_documents(
                query=rephrased, user_id="deny", n_results=50
                
            )
            
            
            

            if not docs:
                hard_cases = {
                    "vi": [
                        "Điều khiển profile từ tool khác qua API",
                        "Kết nối profile với Puppeteer / Playwright",
                        "Xây tool riêng để quản lý profile",
                    ],
                    "en": [
                        "Control profile from another tool via API",
                        "Connect profile with Puppeteer / Playwright",
                        "Build your own tool to manage profiles",
                    ],
                    "zh": [
                        "通过 API 从其他工具控制配置文件",
                        "将配置文件连接到 Puppeteer / Playwright",
                        "构建自己的工具来管理配置文件",
                    ],
                    "ru": [
                        "Управление профилем из другого инструмента через API",
                        "Подключение профиля к Puppeteer / Playwright",
                        "Создание собственного инструмента для управления профилями",
                    ],
                }

                cases = hard_cases.get(lang, hard_cases["en"])

                intro = {
                    "vi": "Có thể bạn đang nói tới một trong các trường hợp sau:\n",
                    "en": "You might be referring to one of these cases:\n",
                    "zh": "您可能指的是以下情况之一：\n",
                    "ru": "Возможно, вы имеете в виду один из следующих случаев:\n",
                }.get(lang, "You might be referring to one of these cases:\n")

                text = intro

                for i, c in enumerate(cases):
                    label = chr(65 + i)
                    if lang == "vi":
                        text += f"• Trường hợp {label}: {c}\n"
                    else:
                        text += f"• Case {label}: {c}\n"

                question = {
                    "vi": "\nBạn đang quan tâm hướng trả lời nào?",
                    "en": "\nWhich case are you referring to?",
                    "zh": "\n您关心的是哪一种情况？",
                    "ru": "\nКакой вариант вас интересует?",
                }.get(lang, "\nWhich case are you referring to?")

                return text + question

            return build_alternative_answer(docs, lang)

        if not last_query_vi:
            return {
                "vi": "Mình chưa rõ bạn đang phủ định phần nào. Bạn có thể nói rõ hơn không ạ? 😊",
                "en": "I'm not sure what part you're disagreeing with. Could you clarify? 😊",
                "zh": "我不太确定您不同意哪一部分。您能再说明一下吗？ 😊",
                "ru": "Я не совсем понял, с чем именно вы не согласны. Не могли бы вы уточнить? 😊",
            }.get(lang, "I'm not sure what part you're disagreeing with. Could you clarify? 😊")

        return {
            "vi": "Có thể mình chưa hiểu đúng. Bạn có thể nói rõ hơn không ạ? 😊",
            "en": "Maybe I misunderstood. Could you clarify? 😊",
            "zh": "可能我没有理解清楚。您能再说明一下吗？ 😊",
            "ru": "Возможно, я неправильно понял. Не могли бы вы уточнить? 😊",
        }.get(lang, "Maybe I misunderstood. Could you clarify? 😊")


_chat_service = ChatService()


async def process_chat_message(message: str, session_id: str = "default"):
    return await _chat_service.process_chat_message(message, session_id)
