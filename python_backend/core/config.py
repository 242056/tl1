import os

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(status_code=503, detail=f"Не настроена переменная окружения: {name}")
    return value


def llm_timeout_sec() -> float:
    """Таймаут ожидания ответа LLM (сек). Deep-research модели часто отвечают 3–10+ мин."""
    raw = os.getenv("LLM_TIMEOUT_SEC", "").strip()
    if raw:
        return max(30.0, float(raw))
    return 300.0
