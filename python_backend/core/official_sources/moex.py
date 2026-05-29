"""MOEX ISS API — официальные биржевые данные."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..clients import ExternalApiClient

log = logging.getLogger("vtb.official_sources.moex")

ISS_BASE = "https://iss.moex.com/iss"
ETF_BOARD = "TQTF"


@dataclass
class SourceParseResult:
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    error: str | None = None


def _table_row(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
    block = payload.get(key) if isinstance(payload.get(key), dict) else {}
    cols = block.get("columns") or []
    rows = block.get("data") or []
    if not cols or not rows:
        return {}
    row = rows[0]
    return {str(cols[i]): row[i] for i in range(min(len(cols), len(row)))}


def _fmt_rub_amount(value: Any) -> str | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return None
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f} млрд ₽".replace(".", ",")
    if num >= 1_000_000:
        return f"{num / 1_000_000:.2f} млн ₽".replace(".", ",")
    return f"{int(num):,} ₽".replace(",", " ")


def _fmt_price(value: Any) -> str | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return None
    text = f"{num:.4f}".rstrip("0").rstrip(".")
    return f"{text} ₽"


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _close_from_history_row(row: Dict[str, Any]) -> float | None:
    for key in ("CLOSE", "LEGALCLOSEPRICE", "WAPRICE", "MARKETPRICE"):
        val = row.get(key)
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        if num > 0:
            return num
    return None


def _bpif_metrics_from_board(payload: Dict[str, Any]) -> Dict[str, Any]:
    market = _table_row(payload, "marketdata")
    sec = _table_row(payload, "securities")
    out: Dict[str, Any] = {}

    last = market.get("LAST") or market.get("LCURRENTPRICE") or market.get("MARKETPRICE")
    price = _fmt_price(last)
    if price:
        out["market_price"] = price

    vol = market.get("VALTODAY") or market.get("VALTODAY_RUR") or market.get("VOLTODAY")
    vol_fmt = _fmt_rub_amount(vol)
    if vol_fmt:
        out["daily_volume"] = vol_fmt

    low = market.get("LOW")
    high = market.get("HIGH")
    if low is not None and high is not None:
        lo = _fmt_price(low)
        hi = _fmt_price(high)
        if lo and hi:
            out["daily_range"] = f"{lo.replace(' ₽', '')} — {hi.replace(' ₽', '')} ₽"

    isin = sec.get("ISIN")
    if isin:
        out["isin"] = str(isin).strip()

    return out


async def _return_1y(api: ExternalApiClient, secid: str, current_last: Any) -> str | None:
    try:
        current = float(current_last)
    except (TypeError, ValueError):
        return None
    if current <= 0:
        return None

    start = (date.today() - timedelta(days=370)).isoformat()
    url = (
        f"{ISS_BASE}/history/engines/stock/markets/shares/boards/{ETF_BOARD}/"
        f"securities/{secid}.json?from={start}&iss.meta=off&limit=1"
    )
    try:
        data = await api.get(url)
    except Exception:
        return None

    row = _table_row(data, "history")
    old = _close_from_history_row(row)
    if old is None or old <= 0:
        return None
    pct = (current / old - 1.0) * 100.0
    return _fmt_pct(pct)


async def _fetch_bpif(api: ExternalApiClient, secid: str) -> SourceParseResult:
    board_url = (
        f"{ISS_BASE}/engines/stock/markets/shares/boards/{ETF_BOARD}/"
        f"securities/{secid}.json?iss.meta=off"
    )
    try:
        board = await api.get(board_url)
    except Exception as exc:
        return SourceParseResult(False, error=str(exc))

    market = _table_row(board, "marketdata")
    sec = _table_row(board, "securities")
    shortname = str(sec.get("SHORTNAME") or sec.get("SECNAME") or secid).strip()

    metrics = _bpif_metrics_from_board(board)
    ret = await _return_1y(api, secid, market.get("LAST") or market.get("MARKETPRICE"))
    if ret and metrics.get("return_1y") is None:
        metrics["return_1y"] = ret

    if not metrics:
        return SourceParseResult(False, error="no MOEX market metrics for ETF")

    today = date.today().isoformat()
    page_url = f"https://www.moex.com/ru/issue.aspx?code={secid}"
    metric_bits = ", ".join(f"{k}={v}" for k, v in metrics.items())
    return SourceParseResult(
        True,
        metrics=metrics,
        sources=[
            {
                "title": f"MOEX: {shortname}",
                "url": page_url,
                "type": "exchange",
                "parser_origin": "moex",
                "updatedAt": today,
            }
        ],
        context_lines=[f"MOEX {secid} ({shortname}): {metric_bits}"],
    )


async def fetch_moex(api: ExternalApiClient, ticker: str, asset_type: str = "bpif") -> SourceParseResult:
    secid = (ticker or "").strip().upper()
    if not secid:
        return SourceParseResult(False, error="empty ticker")

    if (asset_type or "").strip().lower() == "bpif":
        return await _fetch_bpif(api, secid)

    url = f"{ISS_BASE}/securities/{secid}.json"
    try:
        data = await api.get(url)
    except Exception as exc:
        return SourceParseResult(False, error=str(exc))

    shortname = _pick_description(data)
    lines = [f"MOEX {secid}: {shortname or 'биржевой инструмент'}."]
    return SourceParseResult(True, metrics={}, sources=[], context_lines=lines)


def _pick_description(payload: Dict[str, Any]) -> str:
    try:
        cols = payload["securities"]["columns"]
        row = payload["securities"]["data"][0]
        idx = {name: i for i, name in enumerate(cols)}
        return str(row[idx.get("SHORTNAME", 0)] or row[idx.get("NAME", 0)] or "").strip()
    except Exception:
        return ""
