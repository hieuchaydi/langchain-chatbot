from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict
import jwt
from datetime import datetime, timedelta
from config.config import settings
from middleware.limiter import limiter
from services.chat_service import process_chat_message
from models.db import load_latest_summary
from models.vector_store import SESSION_MEMORY


# Khởi tạo router cho API v1
# Chức năng:
# - Gom toàn bộ endpoint liên quan đến chat, upload, auth
router = APIRouter(prefix="/api/v1", tags=["chat"])

# Cấu hình HTTP Bearer để lấy JWT từ header Authorization
bearer_scheme = HTTPBearer(auto_error=False)


# Xác thực JWT cho các API được bảo vệ
# Chức năng:
# - Kiểm tra token có tồn tại hay không
# - Verify chữ ký và hạn sử dụng của JWT
# - Từ chối request nếu token không hợp lệ
async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
):
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials


# =========================
# SCHEMAS
# =========================

# Schema request cho API chat
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


# Schema response cho API chat
class ChatResponse(BaseModel):
    response: str
    sources: Optional[List[str]] = None
    mode: Optional[str] = None
    chunks_used: Optional[int] = None
    language: Optional[str] = None
    timestamp: str
    session_id: str


# Schema response cho API summary
class SummaryResponse(BaseModel):
    session_id: str
    summary: Optional[str] = None
    timestamp: str


# Schema response cho API debug session state
class SessionStateResponse(BaseModel):
    session_id: str
    summary_in_memory: Optional[str] = None
    support_state: Optional[Dict] = None
    timestamp: str


# =========================
# AUTH
# =========================

# API cấp JWT token cho partner
@router.post("/auth/token")
async def get_token(partner_key: str = Form(...)):
    if partner_key != settings.PARTNER_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid partner key")

    token = jwt.encode(
        {
            "exp": datetime.utcnow() + timedelta(hours=24),
            "sub": "partner",
        },
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400,
    }


# =========================
# CHAT API
# =========================

# API chat chính
@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.API_RATE_CHAT)
async def api_chat(
    request: Request,
    body: ChatRequest,
    token=Depends(verify_token),
):
    result = await process_chat_message(body.message, body.session_id)

    return ChatResponse(
        **result,
        timestamp=datetime.now().isoformat(),
        session_id=body.session_id,
    )


# =========================
# SUMMARY API
# =========================

# API lấy summary hội thoại theo session
@router.get("/chat/summary", response_model=SummaryResponse)
@limiter.limit(settings.API_RATE_CHAT)
async def api_chat_summary(
    request: Request,
    session_id: str,
    token=Depends(verify_token),
):
    # Vì ChatService đang dùng:
    # user_id = session_id
    # save_conversation_summary(user_id, session_id, summary)
    summary = load_latest_summary(session_id, session_id)

    return SummaryResponse(
        session_id=session_id,
        summary=summary,
        timestamp=datetime.now().isoformat(),
    )


# API debug: xem summary đang inject trong RAM
@router.get("/chat/session_state", response_model=SessionStateResponse)
@limiter.limit(settings.API_RATE_CHAT)
async def api_chat_session_state(
    request: Request,
    session_id: str,
    token=Depends(verify_token),
):
    session = SESSION_MEMORY.get(session_id, {})

    return SessionStateResponse(
        session_id=session_id,
        summary_in_memory=session.get("summary"),
        support_state=session.get("support_state"),
        timestamp=datetime.now().isoformat(),
    )


# =========================
# UPLOAD API
# =========================

# API upload tài liệu
@router.post("/upload")
@limiter.limit(settings.API_RATE_UPLOAD)
async def api_upload(
    request: Request,
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
    token=Depends(verify_token),
):
    from main import upload_files

    result = await upload_files(files=files)
    return {
        "status": "success",
        **result,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    }


# =========================
# HEALTH CHECK
# =========================

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "model": settings.LLM_MODEL,
        "timestamp": datetime.now().isoformat(),
    }


# =========================
# ROUTER REGISTRATION
# =========================

def register_api_routes(app):
    app.include_router(router)
    print("API v1 routes đã đăng ký – JWT + Rate Limit + Summary ready!")
