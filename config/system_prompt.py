from pathlib import Path

PROMPT_PATH = Path("data/systemprompt.md")

def get_system_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "# Bot rule\nBạn là trợ lý AI chuyên nghiệp..."

def save_system_prompt(content: str):
    PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_PATH.write_text(content.strip(), encoding="utf-8")