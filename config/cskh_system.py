from typing import Dict
from fastapi import FastAPI, Request, WebSocket
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
import json
import uuid

# ====== GLOBAL STATE ======
active_customers: Dict[str, dict] = {}
cskh_websocket: WebSocket | None = None


class CSKHSystem:
    def is_customer_support_intent(self, message: str) -> bool:
        triggers = [
            "cskh", "nhân viên", "người thật", "gặp người",
            "zalo", "hotline", "đặt hàng", "mua",
            "giao hàng", "thanh toán"
        ]
        return any(word in message.lower() for word in triggers)

    async def handle_cskh_transfer(
        self,
        message: str,
        customer_name: str = "Khách hàng"
    ):
        session_id = str(uuid.uuid4())[-8:]

        active_customers[session_id] = {
            "ws": None,
            "first_msg": message,
            "name": customer_name,
            "confirmed": False,
            "message_queue": []
        }

        if cskh_websocket:
            await cskh_websocket.send_text(json.dumps({
                "type": "new_customer",
                "session_id": session_id,
                "message": message,
                "name": customer_name
            }))

        html = f"""
        <div style="text-align:center;padding:15px;background:#00ff8833;
                    border-radius:12px;margin:15px 0;">
            <h3 style="color:#00ff88;margin:0;">
                Đã kết nối với nhân viên hỗ trợ thật 100%!
            </h3>
            <p style="color:#ccc;margin:5px 0 0;">
                Nhân viên sẽ trả lời ngay trong khung chat này
            </p>
        </div>
        <script>
            if (typeof window.connectToCSKH === "function") {{
                window.connectToCSKH("{session_id}");
            }}
        </script>
        """

        return {
            "response": Markup(html),
            "is_cskh": True,
            "session_id": session_id
        }


# ====== INSTANCE DÙNG CHUNG ======
cskh_system = CSKHSystem()


# ====== REGISTER ROUTES ======
def register_cskh_routes(app: FastAPI, templates: Jinja2Templates):

    @app.get("/cskh")
    async def cskh_page(request: Request):
        return templates.TemplateResponse(
            "cskh.html",
            {"request": request}
        )

    @app.post("/cskh/transfer")
    async def transfer_to_cskh(request: Request):
        data = await request.json()
        message = data.get("message", "")
        return await cskh_system.handle_cskh_transfer(message)


def is_customer_support_intent(message: str) -> bool:
    return cskh_system.is_customer_support_intent(message)


async def handle_cskh_transfer(
    message: str,
    customer_name: str = "Khách hàng"
):
    return await cskh_system.handle_cskh_transfer(message, customer_name)