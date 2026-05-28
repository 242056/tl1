"""MOEX ISS API — официальные биржевые данные."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..clients import ExternalApiClient

log = logging.getLogger("vtb.official_sources.moex")

ISS_BASE = "https://iss.moex.com/iss"


@dataclass
class SourceParseResult:
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    error: str | None = None


async def fetch_moex(api: ExternalApiClient, ticker: str) -> SourceParseResult:
    secid = (ticker or "").strip().upper()
    if not secid:
        return SourceParseResult(False, error="empty ticker")

    today = datetime.now(timezone.utc).date().isoformat()
    url = f"{ISS_BASE}/securities/{secid}.json"
    try:
        data = await api.get(url)
    except Exception as exc:
        return SourceParseResult(False, error=str(exc))

    shortname = _pick_description(data)
    source = {
        "title": f"MOEX: {secid}" + (f" — {shortname}" if shortname else ""),
        "url": f"https://www.moex.com/ru/issue.aspx?code={secid}",
        "type": "exchange",
        "updatedAt": today,
    }

    lines = [f"MOEX {secid}: {shortname or 'биржевой инструмент'}."]
    metrics: Dict[str, Any] = {}

    return SourceParseResult(
        True,
        metrics=metrics,
        sources=[source],
        context_lines=lines,
    )


def _pick_description(payload: Dict[str, Any]) -> str:
    try:
        cols = payload["securities"]["columns"]
        row = payload["securities"]["data"][0]
        idx = {name: i for i, name in enumerate(cols)}
        return str(row[idx.get("SHORTNAME", 0)] or row[idx.get("NAME", 0)] or "").strip()
    except Exception:
        return ""
