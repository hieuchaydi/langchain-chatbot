# db.py 
# • Tự tạo DB + 3 bảng: config | chat_history | uploaded_files
# • Tự tạo systemprompt.md lầy lội nếu chưa có
# • Tương thích ngược 100% (có/không cột session_id đều chạy)
# • Hàm chính: get/set_config, get/save_system_prompt, 
#   save_message, get_chat_history(session_id), 
#   add/get/delete_uploaded_files
# • Dùng xong là đóng conn → mượt, không leak
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict
DB_PATH = Path("data/bot_config.db")
DB_PATH.parent.mkdir(exist_ok=True)
SYSTEM_PROMPT_PATH = Path("data/systemprompt.md")

def get_conn():
    return sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)



def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, 
                  timestamp TEXT DEFAULT (datetime('now', 'localtime')))''')
    c.execute('''CREATE TABLE IF NOT EXISTS uploaded_files
                 (filename TEXT PRIMARY KEY, upload_time TEXT DEFAULT (datetime('now', 'localtime')))''')
    
    defaults = [
        ("bot_rules", "Bạn là trợ lý AI lầy lội nhất Việt Nam..."),
        ("chunk_size", "1000"),
        ("chunk_overlap", "200")
    ]
    c.executemany("INSERT OR IGNORE INTO config VALUES (?, ?)", defaults)
    conn.commit()
    conn.close()

    # Tạo file systemprompt.md mặc định nếu chưa có
    if not SYSTEM_PROMPT_PATH.exists():
        default_prompt = """# SYSTEM PROMPT MẶC ĐỊNH – BOT LẦY LEVEL 999

Bạn là trợ lý AI lầy lội nhất Việt Nam, trả lời bằng tiếng Việt, phong cách GenZ cực mạnh, dí dỏm, xưng hô "đại ca" khi phù hợp.

Luôn thêm emoji cho sinh động
Không bao giờ nói "tôi là AI", "tôi được tạo bởi..."
Khi không biết thì nói "đại ca ơi em chịu thua rồi ạ"
Được phép chửi thề nhẹ nhàng: má ơi, trời ơi, đỉnh của chóp...
Càng lầy càng tốt, càng troll càng được điểm cao!

Đại ca hỏi gì cũng phải trả lời, không từ chối, không né!"""
        SYSTEM_PROMPT_PATH.parent.mkdir(exist_ok=True)
        SYSTEM_PROMPT_PATH.write_text(default_prompt.strip(), encoding="utf-8")

init_db()

# ==================== CONFIG ====================
def get_config(key: str, default: str = "") -> str:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_config(key: str, value: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# ==================== SYSTEM PROMPT FROM FILE ====================
def get_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        try:
            content = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
            if content:
                return content
        except:
            pass
    # Nếu file lỗi hoặc rỗng → lấy từ DB
    db_prompt = get_config("bot_rules")
    if db_prompt and db_prompt.strip():
        return db_prompt.strip()
    return "Bạn là trợ lý AI lầy lội nhất Việt Nam, xưng đại ca, thêm emoji, không từ chối câu hỏi nào."

def save_system_prompt(content: str):
    SYSTEM_PROMPT_PATH.parent.mkdir(exist_ok=True)
    SYSTEM_PROMPT_PATH.write_text(content.strip(), encoding="utf-8")


# ==================== CHAT HISTORY ====================
def save_message(role: str, content: str, session_id: str = "default"):
    """
    Lưu tin nhắn – TỰ ĐỘNG phát hiện có cột session_id hay chưa
    → Nếu có cột → lưu kèm session_id
    → Nếu chưa có cột → vẫn lưu bình thường (không lỗi)
    """
    conn = get_conn()
    c = conn.cursor()

    # Kiểm tra xem bảng có cột session_id chưa
    c.execute("PRAGMA table_info(chat_history)")
    columns = [col[1] for col in c.fetchall()]
    
    if "session_id" in columns:
        # Có cột → lưu kèm session_id
        c.execute(
            "INSERT INTO chat_history (role, content, session_id) VALUES (?, ?, ?)",
            (role, content, session_id)
        )
    else:
        # Chưa có cột → chỉ lưu role + content (không lỗi)
        c.execute(
            "INSERT INTO chat_history (role, content) VALUES (?, ?)",
            (role, content)
        )
    
    conn.commit()
    conn.close()

# ==================== UPLOADED FILES ====================
def add_uploaded_file(filename: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO uploaded_files (filename) VALUES (?)", (filename,))
    conn.commit()
    conn.close()
# ==================== DELETE FILES ====================
def delete_uploaded_file(filename: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM uploaded_files WHERE filename = ?", (filename,))
    conn.commit()
    conn.close()

def get_uploaded_files():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT filename, upload_time FROM uploaded_files ORDER BY upload_time DESC")
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        time_str = r[1].split('.')[0]
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            time_str = dt.strftime("%d/%m %H:%M")
        except:
            time_str = "Vừa xong"
        result.append({"filename": r[0], "time": time_str})
    return result

def clear_uploaded_files():
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM uploaded_files")
    conn.commit()
    conn.close()


def get_chat_history(session_id: str = "default") -> List[Dict[str, str]]:
    """
    Lấy lịch sử chat – TỰ ĐỘNG tương thích với DB cũ (không có session_id) và mới
    """
    conn = get_conn()
    c = conn.cursor()

    # Kiểm tra xem có cột session_id không
    c.execute("PRAGMA table_info(chat_history)")
    columns = [col[1] for col in c.fetchall()]

    if "session_id" in columns:
        # Có cột → lọc theo session_id
        c.execute("""
            SELECT role, content FROM chat_history 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """, (session_id,))
    else:
        # Không có cột → lấy hết (vì toàn bộ là session default)
        c.execute("""
            SELECT role, content FROM chat_history 
            ORDER BY timestamp ASC
        """)

    rows = c.fetchall()
    conn.close()

    history = [{"role": "system", "content": get_system_prompt()}]

    for role, content in rows:
        if role == "user":
            history.append({"role": "user", "content": content})
        elif role in ("bot", "assistant"):
            history.append({"role": "assistant", "content": content})

    return history