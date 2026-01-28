from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import logging
# log ra những gì ở terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("data/api.log"),
        logging.StreamHandler()
    ]
)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = datetime.now()
        client_ip = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logging.error(
                f"ERROR | {client_ip} | {request.method} {request.url} | {duration:.2f}ms | {e}"
            )
            raise

        duration = (datetime.now() - start_time).total_seconds() * 1000
        logging.info(
            f"{client_ip} | {request.method} {request.url} | {status_code} | {duration:.2f}ms"
        )
        return response
