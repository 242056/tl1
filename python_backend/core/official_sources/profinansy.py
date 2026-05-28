"""Парсер profinansy.ru — метрики фондов из __NEXT_DATA__ (etf_data)."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("vtb.official_sources.profinansy")

PROFINANSY_INSTRUMENT_URL = "https://profinansy.ru/market/instrument/{code}"


@dataclass
class SourceParseResult:
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    error: str | None = None


def _extract_from_next_data(html: str) -> Dict[str, Any]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>({.*?})</script>', html, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


def _unwrap(field: Any) -> Any:
    if isinstance(field, dict) and "v" in field:
        return field["v"]
    return field


def _fmt_pct(ratio: float) -> str:
    return f"{ratio * 100:.2f}%"


def _fmt_aum_rub(value: float) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} млрд ₽"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f} млн ₽"
    return f"{int(value):,} ₽".replace(",", " ")


def _instrument_query_key(code: str) -> str:
    return f'getInstrument({{"code":"{code}"}})'


def _find_instrument_payload(data: Dict[str, Any], codes: List[str]) -> tuple[Dict[str, Any], str]:
    try:
        queries = data["props"]["pageProps"]["initialState"]["mainBaseApi"]["queries"]
    except (KeyError, TypeError):
        return {}, ""
    for code in codes:
        block = queries.get(_instrument_query_key(code))
        if isinstance(block, dict) and isinstance(block.get("data"), dict):
            return block["data"], code
    return {}, ""


def _etf_data_from_next(data: Dict[str, Any], codes: List[str]) -> tuple[Dict[str, Any], str]:
    payload, code = _find_instrument_payload(data, codes)
    etf = payload.get("etf_data")
    return (etf if isinstance(etf, dict) else {}), code


def _metrics_from_etf_data(etf: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    ret_1y = _unwrap(etf.get("calc_12m_return") or etf.get("calc_12m_perfomance"))
    if isinstance(ret_1y, (int, float)):
        out["return_1y"] = _fmt_pct(float(ret_1y))

    ret_3y = _unwrap(etf.get("calc_3y_return") or etf.get("calc_3y_perfomance"))
    if isinstance(ret_3y, (int, float)):
        out["return_3y"] = _fmt_pct(float(ret_3y))

    ter = _unwrap(etf.get("expense_ratio"))
    if isinstance(ter, (int, float)):
        out["ter_fee"] = _fmt_pct(float(ter))

    aum = _unwrap(etf.get("aum_orig") or etf.get("aum"))
    if isinstance(aum, (int, float)) and aum > 0:
        out["nav_aum"] = _fmt_aum_rub(float(aum))

    alpha = _unwrap(etf.get("alphaY1") or etf.get("alpha"))
    if isinstance(alpha, (int, float)):
        out["alpha"] = _fmt_pct(float(alpha))

    return out


def _map_metrics_for_kind(raw: Dict[str, Any], kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    k = (kind or "").strip().lower()
    if k == "bpif":
        return raw

    asset = payload.get("asset") if isinstance(payload.get("asset"), dict) else {}
    price = asset.get("last_price") or asset.get("close")
    nav_line = f"{price} ₽" if isinstance(price, (int, float)) and price > 0 else None

    if k == "opif":
        out: Dict[str, Any] = {}
        if nav_line:
            out["nav_per_share"] = nav_line
        if raw.get("return_1y"):
            out["return_period"] = raw["return_1y"]
        elif raw.get("return_3y"):
            out["return_period"] = raw["return_3y"]
        if raw.get("nav_aum"):
            out["nav_aum"] = raw["nav_aum"]
        if raw.get("ter_fee"):
            out["management_fee"] = raw["ter_fee"]
        return out

    if k == "zpif":
        out = {}
        if nav_line:
            out["nav_per_share"] = nav_line
        if raw.get("return_1y"):
            out["return_period"] = raw["return_1y"]
        if raw.get("nav_aum"):
            out["nav_aum"] = raw["nav_aum"]
        if raw.get("ter_fee"):
            out["rental_yield"] = raw.get("return_1y")
        return out

    return raw


def _code_candidates(secid: str) -> List[str]:
    s = (secid or "").strip().upper()
    if not s:
        return []
    candidates = [f"{s}-MOEX", s]
    seen: set[str] = set()
    out: List[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


async def fetch_profinansy(api, ticker: str, asset_type: str = "bpif") -> SourceParseResult:
    secid = (ticker or "").strip().upper()
    if not secid:
        return SourceParseResult(False, error="empty ticker")

    codes = _code_candidates(secid)
    today = datetime.now(timezone.utc).date().isoformat()
    html = ""
    url = PROFINANSY_INSTRUMENT_URL.format(code=codes[0])
    try:
        timeout = float(__import__("os").getenv("HTTP_TIMEOUT_SEC", "15"))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for code in codes:
                url = PROFINANSY_INSTRUMENT_URL.format(code=code)
                r = await client.get(url, headers={"User-Agent": "VTB-MVP-AssetAnalysis/1.0"})
                if r.status_code != 200:
                    continue
                html = r.text
                next_data = _extract_from_next_data(html)
                etf, matched = _etf_data_from_next(next_data, [code])
                if etf:
                    payload, _ = _find_instrument_payload(next_data, [code])
                    raw = _metrics_from_etf_data(etf)
                    metrics = _map_metrics_for_kind(raw, asset_type, payload)
                    if metrics:
                        lines = [
                            f"Profinansy {matched}: "
                            + ", ".join(f"{k}={v}" for k, v in metrics.items() if v is not None),
                        ]
                        return SourceParseResult(
                            True,
                            metrics=metrics,
                            sources=[
                                {
                                    "title": f"Profinansy: {matched}",
                                    "url": url,
                                    "type": "market_data",
                                    "updatedAt": today,
                                }
                            ],
                            context_lines=lines,
                        )
    except Exception as exc:
        return SourceParseResult(False, error=str(exc))

    return SourceParseResult(
        False,
        sources=[{"title": "Profinansy", "url": url, "type": "market_data", "updatedAt": today}],
        error="fund metrics not found in page",
    )
