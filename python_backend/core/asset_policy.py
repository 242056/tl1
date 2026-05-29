"""Политики и fallback-сообщения Анти-Гугл по ТЗ."""
from __future__ import annotations

from typing import Any, Dict

from .product_metrics import is_supported_asset_kind

MSG_NO_RECENT_NEWS = "За последние 30 дней значимых новостей по активу не найдено"
MSG_UNSUPPORTED_ASSET_TYPE = "ИИ-анализ для этого типа инструмента пока недоступен"


def llm_data_status(raw: Dict[str, Any]) -> Dict[str, Any]:
    status = raw.get("data_status")
    return status if isinstance(status, dict) else {}


def llm_has_recent_30d_data(raw: Dict[str, Any]) -> bool | None:
    """None — LLM не указала явно."""
    value = llm_data_status(raw).get("has_recent_30d_data")
    if value is True:
        return True
    if value is False:
        return False
    return None


def can_skip_recent_news_requirement(
    asset_type: str,
    stable_profile: Dict[str, Any],
    coverage: Dict[str, bool],
) -> bool:
    """Продукты с эталоном или официальными парсерами не требуют новостного фона."""
    if stable_profile.get("stable_kind"):
        return True
    k = (asset_type or "").strip().lower()
    if k == "bpif":
        return bool(coverage.get("investing") or coverage.get("moex"))
    if k in ("opif", "zpif"):
        return bool(coverage.get("investing"))
    if k == "precious_metal":
        return bool(coverage.get("investing") or coverage.get("cbr"))
    return bool(coverage.get("moex") or coverage.get("vtb_card"))


def check_asset_type_supported(asset_type: str) -> Dict[str, Any] | None:
    if is_supported_asset_kind(asset_type):
        return None
    return {
        "success": False,
        "message": MSG_UNSUPPORTED_ASSET_TYPE,
        "error_code": "unsupported_asset_type",
    }


def check_recent_news_required(
    raw: Dict[str, Any],
    asset_type: str,
    stable_profile: Dict[str, Any],
    coverage: Dict[str, bool],
) -> Dict[str, Any] | None:
    recent = llm_has_recent_30d_data(raw)
    if recent is not False:
        return None
    if can_skip_recent_news_requirement(asset_type, stable_profile, coverage):
        return None
    return {
        "success": False,
        "message": MSG_NO_RECENT_NEWS,
        "error_code": "no_recent_news",
    }
