"""Учётные цены драгметаллов ЦБ РФ (XML)."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

log = logging.getLogger("vtb.official_sources.cbr")

CBR_METALS_PAGE_URL = "https://www.cbr.ru/hd_base/metall/"
CBR_METALS_XML_URL = "http://www.cbr.ru/scripts/xml_metall.asp"

# Коды металлов в XML ЦБ: 1 — золото, 2 — серебро, 3 — платина, 4 — палладий.
METAL_CODE_BY_PRODUCT: Dict[str, str] = {
    "gold_oms": "1",
    "gold_coins": "1",
    "gold_bars": "1",
    "platinum_oms": "3",
    "palladium_oms": "4",
}

METAL_NAME_BY_CODE = {
    "1": "Золото",
    "2": "Серебро",
    "3": "Платина",
    "4": "Палладий",
}


@dataclass
class SourceParseResult:
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    error: str | None = None


def _parse_ru_float(raw: str) -> Optional[float]:
    if not raw:
        return None
    try:
        return float(str(raw).strip().replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def _parse_record_date(raw: str) -> Optional[datetime]:
    try:
        return datetime.strptime(raw.strip(), "%d.%m.%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fmt_price_rub(value: float) -> str:
    text = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{text} ₽/г"


def _fmt_spread_pct(bid: float, ask: float) -> str:
    if bid <= 0 or ask <= bid:
        return ""
    mid = (bid + ask) / 2
    return f"{(ask - bid) / mid * 100:.2f}%"


def _fmt_return_pct(start: float, end: float, years: int) -> str:
    if start <= 0:
        return ""
    pct = (end / start - 1.0) * 100.0
    word = "год" if years == 1 else "года" if 2 <= years <= 4 else "лет"
    return f"{pct:+.1f}% за {years} {word}"


def _records_from_xml(payload: bytes, metal_code: str) -> List[Tuple[datetime, float, float | None]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError(f"invalid xml: {exc}") from exc

    out: List[Tuple[datetime, float, float | None]] = []
    for rec in root.findall("Record"):
        if (rec.get("Code") or "").strip() != metal_code:
            continue
        dt = _parse_record_date(rec.get("Date") or "")
        buy = _parse_ru_float((rec.findtext("Buy") or "").strip())
        sell = _parse_ru_float((rec.findtext("Sell") or "").strip())
        price = sell or buy
        if dt and price is not None and price > 0:
            out.append((dt, buy or price, sell or price))
    out.sort(key=lambda x: x[0])
    return out


def _metrics_from_records(records: List[Tuple[datetime, float, float | None]]) -> Dict[str, Any]:
    if not records:
        return {}

    latest_dt, latest_buy, latest_sell = records[-1]
    metrics: Dict[str, Any] = {
        "bid_price": _fmt_price_rub(latest_buy),
        "ask_price": _fmt_price_rub(latest_sell),
    }
    spread = _fmt_spread_pct(latest_buy, latest_sell)
    if spread:
        metrics["bank_spread"] = spread

    now = latest_dt
    for years in (1, 3):
        cutoff = now - timedelta(days=365 * years)
        window = [(dt, buy, sell) for dt, buy, sell in records if dt >= cutoff]
        if len(window) < 2:
            continue
        start_price = window[0][2]
        end_price = window[-1][2]
        ret = _fmt_return_pct(start_price, end_price, years)
        if ret:
            metrics["period_change_pct"] = ret
            break

    metrics["_price_date"] = latest_dt.date().isoformat()
    return metrics


async def fetch_cbr_metal(product_id: str) -> SourceParseResult:
    metal_code = METAL_CODE_BY_PRODUCT.get((product_id or "").strip())
    if not metal_code:
        return SourceParseResult(False, error="product has no CBR metal mapping")

    today = datetime.now(timezone.utc).date()
    date_from = today - timedelta(days=365 * 3 + 30)
    params = {
        "date_req1": date_from.strftime("%d/%m/%Y"),
        "date_req2": today.strftime("%d/%m/%Y"),
    }
    url = CBR_METALS_XML_URL

    try:
        timeout = float(__import__("os").getenv("HTTP_TIMEOUT_SEC", "15"))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, params=params, headers={"User-Agent": "VTB-MVP-AssetAnalysis/1.0"})
            resp.raise_for_status()
            records = _records_from_xml(resp.content, metal_code)
    except Exception as exc:
        log.info("CBR metals fetch failed product=%s error=%s", product_id, exc)
        return SourceParseResult(False, error=str(exc))

    metrics = _metrics_from_records(records)
    if not metrics.get("ask_price"):
        return SourceParseResult(False, error="metal price not found in CBR XML")

    metal_name = METAL_NAME_BY_CODE.get(metal_code, "металл")
    price_date = metrics.pop("_price_date", today.isoformat())
    lines = [
        f"ЦБ РФ ({metal_name}): bid={metrics.get('bid_price')}, ask={metrics.get('ask_price')}"
        + (f", {metrics['period_change_pct']}" if metrics.get("period_change_pct") else "")
        + f" (на {price_date}).",
    ]

    return SourceParseResult(
        True,
        metrics=metrics,
        sources=[
            {
                "title": "ЦБ РФ — учётные цены на драгоценные металлы",
                "url": CBR_METALS_PAGE_URL,
                "type": "regulator",
                "parser_origin": "cbr",
                "updatedAt": price_date,
            }
        ],
        context_lines=lines,
    )
