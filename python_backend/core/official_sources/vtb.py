"""Карточка инструмента ВТБ и внутренняя аналитика (URL из env)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..clients import ExternalApiClient

log = logging.getLogger("vtb.official_sources.vtb")


@dataclass
class VtbFetchResult:
    card_ok: bool
    research_ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)


def _extract_metrics_from_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Универсальный разбор JSON от внутренних API ВТБ."""
    out: Dict[str, Any] = {}
    if not isinstance(data, dict):
        return out

    flat_candidates = {
        "return_1y": ("return1y", "return_1y", "yield1y"),
        "return_3y": ("return3y", "return_3y", "yield3y"),
        "nav_aum": ("nav", "aum", "netAssetValue", "scha"),
        "ter_fee": ("ter", "terFee", "managementFee"),
        "alpha": ("alpha",),
        "interest_rate": ("rate", "interestRate", "annualRate"),
        "nav_per_share": ("navPerShare", "sharePrice", "price"),
    }
    for target, keys in flat_candidates.items():
        for k in keys:
            if k in data and data[k] not in (None, ""):
                out[target] = data[k]
                break
    if "metrics" in data and isinstance(data["metrics"], dict):
        for k, v in data["metrics"].items():
            if k not in out or out[k] is None:
                out[k] = v
    return out


async def fetch_vtb_sources(
    api: ExternalApiClient,
    asset_id: str,
    asset_type: str,
    period_days: int,
) -> VtbFetchResult:
    today = datetime.now(timezone.utc).date().isoformat()
    token = os.getenv("SOURCES_API_TOKEN")
    params = {"asset_id": asset_id, "asset_type": asset_type, "period_days": period_days, "product_name": asset_id}

    metrics: Dict[str, Any] = {}
    sources: List[Dict[str, str]] = []
    lines: List[str] = []
    errors: List[Dict[str, str]] = []
    card_ok = False
    research_ok = False

    card_url = os.getenv("SRC_INSTRUMENT_CARD_URL", "").strip()
    if card_url:
        try:
            data = await api.get(card_url, token, params)
            metrics.update(_extract_metrics_from_payload(data))
            sources.append(
                {
                    "title": "Карточка инструмента ВТБ",
                    "url": card_url,
                    "type": "vtb_instrument_card",
                    "updatedAt": today,
                }
            )
            lines.append("ВТБ: данные карточки инструмента получены.")
            card_ok = True
        except Exception as exc:
            errors.append({"source": "vtb_card", "error": str(exc)})

    research_url = os.getenv("SRC_VTB_RESEARCH_URL", "").strip()
    if research_url:
        try:
            data = await api.get(research_url, token, params)
            payload_metrics = _extract_metrics_from_payload(data)
            metrics.update(payload_metrics)
            sources.append(
                {
                    "title": "Аналитика ВТБ",
                    "url": research_url,
                    "type": "vtb_research",
                    "updatedAt": today,
                }
            )
            lines.append("ВТБ: аналитический обзор получен.")
            research_ok = True
        except Exception as exc:
            errors.append({"source": "vtb_research", "error": str(exc)})

    reports_url = os.getenv("SRC_FIN_REPORTS_URL", "").strip()
    if reports_url:
        try:
            data = await api.get(reports_url, token, params)
            sources.append(
                {
                    "title": "Отчётность эмитента / продукта",
                    "url": reports_url,
                    "type": "financial_report",
                    "updatedAt": today,
                }
            )
            lines.append("ВТБ: отчётность доступна.")
        except Exception as exc:
            errors.append({"source": "vtb_reports", "error": str(exc)})

    return VtbFetchResult(card_ok, research_ok, metrics, sources, lines, errors)
