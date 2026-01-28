# 📘 API v1 -- Chat Service

**Base URL:**

    /api/v1

**Authentication:**\
Tất cả các API (trừ `/health`) yêu cầu JWT Bearer Token trong header:

    Authorization: Bearer <access_token>

------------------------------------------------------------------------

## 1️⃣ Authentication

### 🔐 Cấp JWT Token

**Endpoint**

    POST /api/v1/auth/token

**Content-Type**

    application/x-www-form-urlencoded

### Form Fields

| Tên         | Kiểu   | Bắt buộc | Mô tả                    |
|-------------|--------|----------|--------------------------|
| partner_key | string | ✅       | $2b$12$7c4n4GkZpW8YyW6S0p1x4eF3bP5M5D2QyYq7G1cE9fHk1n9C8qkW2 |

**Response -- 200 OK**

``` json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

------------------------------------------------------------------------

## 2️⃣ Chat API

### 💬 Gửi tin nhắn chat

**Endpoint**

    POST /api/v1/chat

**Headers**

    Authorization: Bearer <token>
    Content-Type: application/json

**Request Body**

``` json
{
  "message": "Xin chào",
  "session_id": "session_123"
}
```

**Response -- 200 OK**

``` json
{
  "response": "Chào bạn! Tôi có thể giúp gì?",
  "sources": ["doc1.md", "faq.md"],
  "mode": "rag",
  "chunks_used": 4,
  "language": "vi",
  "timestamp": "2026-01-27T10:15:30.123456",
  "session_id": "session_123"
}
```

------------------------------------------------------------------------

## 3️⃣ Summary API

### 🧠 Lấy summary hội thoại

**Endpoint**

    GET /api/v1/chat/summary?session_id=...

**Response -- 200 OK**

``` json
{
  "session_id": "session_123",
  "summary": "Người dùng hỏi về sản phẩm X...",
  "timestamp": "2026-01-27T10:20:00.000000"
}
```

------------------------------------------------------------------------

## 4️⃣ Upload API

### 📂 Upload tài liệu

**Endpoint**

    POST /api/v1/upload

**Response -- 200 OK**

``` json
{
  "status": "success",
  "uploaded_files": ["a.md", "b.md"],
  "indexed_chunks": 120,
  "session_id": "session_123",
  "timestamp": "2026-01-27T10:25:00.000000"
}
```

------------------------------------------------------------------------

## 5️⃣ Health Check

### ❤️ Kiểm tra trạng thái hệ thống

**Endpoint**

    GET /api/v1/health

**Response -- 200 OK**

``` json
{
  "status": "healthy",
  "model": "gpt-4.1-mini",
  "timestamp": "2026-01-27T10:30:00.000000"
}
```

------------------------------------------------------------------------

## 6️⃣ Authentication Errors

  Status   Mô tả
  -------- ----------------
  401      Token required
  401      Token expired
  401      Invalid token

------------------------------------------------------------------------

## 7️⃣ Ghi chú kỹ thuật

-   JWT: HS256
-   Token TTL: 24h
-   Rate limit: middleware.limiter
-   Session memory: models.vector_store.SESSION_MEMORY
-   Summary DB: models.db.load_latest_summary
