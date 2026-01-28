from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
import secrets
# Controllers
from controllers.chat_controller import ChatController
from controllers.upload_controller import UploadController
from controllers.vector_controller import VectorController
from controllers.config_controller import ConfigController
from controllers.history_controller import HistoryController

# Middleware
from middleware.limiter import limiter
from middleware.loguploadfile import LoggingMiddleware

# Config
from config.config import settings
from config.cskh_system import register_cskh_routes




app = FastAPI(title="Trợ lý ảo Hidemium AI")


# Rate limit (SlowAPI)


app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda r, e: JSONResponse(
        status_code=429,
        content={"detail": "Quá nhiều request!"}
    ),
)

app.add_middleware(SlowAPIMiddleware)


# Security middleware






app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET or secrets.token_hex(32)
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Static files & templates


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Register controllers (Web UI)


ChatController(app, templates).register()
UploadController(app, templates).register()
VectorController(app, templates).register()
ConfigController(app, templates).register()
HistoryController(app, templates).register()

# CSKH routes
register_cskh_routes(app, templates)


# Register API routes (JWT + HMAC + Rate limit)


try:
    from routes.api import register_api_routes
    register_api_routes(app)
except Exception as e:
    print("❌ API ROUTE LOAD FAILED:", e)


# Logging middleware (cuối pipeline)

app.add_middleware(LoggingMiddleware)
