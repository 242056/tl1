"""Investing.com — опциональный источник: только при живом поиске и реальных метриках на странице."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from urllib.parse import quote

import httpx

from ..metric_values import is_concrete_metric

log = logging.getLogger("vtb.official_sources.investing")

INVESTING_BASE = "https://ru.investing.com"

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_LINK_SYMBOL_RE = re.compile(
    r'"link":"(\\/(?:etfs|commodities|funds)\\/[^"]+)".{0,500}?"symbol":"([^"]+)"',
    re.S,
)
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>({.*?})</script>', re.S)


@dataclass
class SourceParseResult:
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    error: str | None = None


def _timeout() -> float:
    return float(__import__("os").getenv("HTTP_TIMEOUT_SEC", "15"))


def _fmt_pct(value: Any) -> str | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return f"{num:.2f}%"


def _extract_state(html: str) -> Dict[str, Any]:
    m = _NEXT_DATA_RE.search(html or "")
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
        state = data.get("props", {}).get("pageProps", {}).get("state") or {}
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _instrument_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("etfStore", "commodityStore", "equitiesStore", "fundsStore"):
        block = state.get(key)
        if isinstance(block, dict) and isinstance(block.get("instrument"), dict):
            return block["instrument"]
    return {}


def _parse_search_hits(html: str, *, ticker: str | None = None) -> List[Tuple[str, str]]:
    want = (ticker or "").strip().upper()
    hits: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for m in _LINK_SYMBOL_RE.finditer(html or ""):
        path = m.group(1).replace("\\/", "/")
        sym = m.group(2).strip().upper()
        chunk = m.group(0)
        if want and sym != want:
            continue
        if path in seen:
            continue
        if "Моск" in chunk or "Moscow" in chunk or "Russian" in chunk or "Russia" in chunk:
            seen.add(path)
            hits.append((sym, path))
        elif want and sym == want:
            seen.add(path)
            hits.append((sym, path))
    return hits


async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    return await client.get(url, headers={"User-Agent": _USER_AGENT})


async def _search_path(
    client: httpx.AsyncClient,
    query: str,
    *,
    ticker: str | None = None,
) -> str:
    q = (query or "").strip()
    if not q:
        return ""
    url = f"{INVESTING_BASE}/search/?q={quote(q)}"
    resp = await _get(client, url)
    if resp.status_code >= 400:
        return ""
    hits = _parse_search_hits(resp.text, ticker=ticker)
    if not hits:
        return ""
    if ticker:
        want = ticker.strip().upper()
        for sym, path in hits:
            if sym == want:
                return path
        return ""
    return hits[0][1]


async def _resolve_path_via_search(
    client: httpx.AsyncClient,
    *,
    ticker: str | None,
    product_name: str,
) -> str:
    """Только живой поиск — без захардкоженных URL."""
    t = (ticker or "").strip().upper()
    if t:
        path = await _search_path(client, t, ticker=t)
        if path:
            return path
    if product_name and not t:
        return await _search_path(client, product_name, ticker=None)
    return ""


def _instrument_path_matches_ticker(path: str, ticker: str) -> bool:
    """Slug страницы должен содержать тикер — иначе это чужой инструмент с тем же символом."""
    t = (ticker or "").strip().upper()
    slug = (path or "").lower()
    if not t or not slug:
        return False
    if t == "GOLD":
        return "gold" in slug
    return t.lower() in slug


def _metrics_bpif(instrument: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    stats = instrument.get("keyStatistics") if isinstance(instrument.get("keyStatistics"), dict) else {}
    fundamental = instrument.get("fundamental") if isinstance(instrument.get("fundamental"), dict) else {}
    price = instrument.get("price") if isinstance(instrument.get("price"), dict) else {}
    name = instrument.get("name") if isinstance(instrument.get("name"), dict) else {}

    last = price.get("last")
    if isinstance(last, (int, float)) and last > 0:
        out["market_price"] = f"{last:,.4f} ₽".replace(",", " ")

    volume = stats.get("volume") or price.get("volume")
    if volume not in (None, ""):
        out["daily_volume"] = str(volume)

    ret_1y = fundamental.get("oneYearReturn")
    if ret_1y is None:
        ret_1y = price.get("oneYearChange")
    if ret_1y is None:
        ret_1y = stats.get("oneYearChange")
    ret_pct = _fmt_pct(ret_1y)
    if ret_pct:
        out["return_1y"] = ret_pct

    high = price.get("high")
    low = price.get("low")
    if isinstance(high, (int, float)) and isinstance(low, (int, float)):
        out["daily_range"] = f"{low:,.4f} — {high:,.4f} ₽".replace(",", " ")

    isin = name.get("isin") or stats.get("isin")
    if isin:
        out["isin"] = str(isin).strip()

    return out


def _metrics_precious_metal(instrument: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    price = instrument.get("price") if isinstance(instrument.get("price"), dict) else {}
    fundamental = instrument.get("fundamental") if isinstance(instrument.get("fundamental"), dict) else {}
    currency = str(price.get("currency") or "RUB").upper()
    sym = "₽" if currency == "RUB" else "$" if currency == "USD" else currency

    bid = price.get("bid")
    ask = price.get("ask")
    last = price.get("last")
    if isinstance(bid, (int, float)) and bid > 0:
        out["bid_price"] = f"{bid:,.2f} {sym}".replace(",", " ")
    if isinstance(ask, (int, float)) and ask > 0:
        out["ask_price"] = f"{ask:,.2f} {sym}".replace(",", " ")
    elif isinstance(last, (int, float)) and last > 0:
        out["ask_price"] = f"{last:,.2f} {sym}".replace(",", " ")

    if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and ask > bid > 0:
        spread_pct = (ask - bid) / ((ask + bid) / 2) * 100
        out["bank_spread"] = f"{spread_pct:.2f}%"

    high = price.get("high")
    low = price.get("low")
    if isinstance(high, (int, float)) and isinstance(low, (int, float)):
        out["daily_range"] = f"{low:,.2f} — {high:,.2f} {sym}".replace(",", " ")

    ret = fundamental.get("oneYearReturn")
    if ret is None:
        ret = price.get("oneYearChange")
    ret_pct = _fmt_pct(ret)
    if ret_pct:
        out["period_change_pct"] = f"{ret_pct} за 1 год"

    return out


def _map_metrics(instrument: Dict[str, Any], asset_type: str) -> Dict[str, Any]:
    k = (asset_type or "").strip().lower()
    if k == "precious_metal":
        return _metrics_precious_metal(instrument)
    if k == "bpif":
        return _metrics_bpif(instrument)
    return {}


def _has_useful_metrics(metrics: Dict[str, Any]) -> bool:
    return any(is_concrete_metric(v) for v in metrics.values())


def _instrument_title(instrument: Dict[str, Any]) -> str:
    name = instrument.get("name") if isinstance(instrument.get("name"), dict) else {}
    return str(name.get("shortName") or name.get("fullName") or name.get("symbol") or "Investing.com")


_PRODUCT_STOP_WORDS = frozenset(
    {
        "бпиф",
        "опиф",
        "зпиф",
        "фонд",
        "пиф",
        "паевой",
        "биржевой",
        "инвестиционный",
        "инвест",
        "паи",
        "для",
        "the",
        "uk",
        "втб",
    }
)


def _product_keywords(product_name: str) -> List[str]:
    m = re.search(r"«([^»]+)»", product_name or "")
    core = m.group(1) if m else (product_name or "")
    words = re.findall(r"[а-яёa-z0-9]+", core.lower())
    return [w for w in words if len(w) >= 4 and w not in _PRODUCT_STOP_WORDS]


def _instrument_page_text(instrument: Dict[str, Any]) -> str:
    parts: List[str] = []
    name = instrument.get("name") if isinstance(instrument.get("name"), dict) else {}
    for key in ("fullName", "shortName", "symbol", "parentName"):
        val = name.get(key)
        if val:
            parts.append(str(val))
    underlying = instrument.get("underlying")
    if isinstance(underlying, dict):
        for key in ("name", "shortName", "fullName"):
            val = underlying.get(key)
            if val:
                parts.append(str(val))
    return " ".join(parts).lower()


def _instrument_matches_product(instrument: Dict[str, Any], product_name: str) -> bool:
    """Символ на Investing.com может указывать на другой фонд — сверяем название с каталогом ВТБ."""
    if not (product_name or "").strip():
        return True

    page = _instrument_page_text(instrument)
    product_low = product_name.lower()

    if any(x in product_low for x in ("облига", "bond")):
        if any(x in page for x in ("акци", "equity", "stock")) and not any(
            x in page for x in ("облига", "bond")
        ):
            return False

    if any(x in product_low for x in ("индекс", "акци", "мосбирж", "mosb")) and "облига" not in product_low:
        if any(x in page for x in ("облига", "bond")) and not any(
            x in product_low for x in ("облига", "bond")
        ):
            return False

    if "золот" in product_low or "gold" in product_low:
        if "золот" not in page and "gold" not in page:
            return False
    if "серебр" in product_low or "silver" in product_low:
        if "серебр" not in page and "silver" not in page:
            return False
    if "паллад" in product_low or "palladium" in product_low:
        if "паллад" not in page and "palladium" not in page:
            return False
    if "платин" in product_low or "platinum" in product_low:
        if "платин" not in page and "platinum" not in page:
            return False

    keys = _product_keywords(product_name)
    if not keys:
        return True
    return any(key in page for key in keys)


async def fetch_investing(
    api,
    *,
    product_id: str,
    asset_type: str,
    ticker: str | None = None,
    product_name: str = "",
) -> SourceParseResult:
    today = datetime.now(timezone.utc).date().isoformat()
    timeout = _timeout()

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            path = await _resolve_path_via_search(
                client,
                ticker=ticker,
                product_name=product_name,
            )
            if not path:
                return SourceParseResult(False, error="instrument not found on investing.com")

            page_url = f"{INVESTING_BASE}{path}"
            resp = await _get(client, page_url)
            if resp.status_code >= 400:
                return SourceParseResult(False, error=f"investing page status {resp.status_code}")

            final_path = httpx.URL(str(resp.url)).path or path
            if not re.match(r"^/(etfs|commodities|funds)/[a-z0-9-]+$", final_path, re.I):
                return SourceParseResult(False, error="investing redirect to non-instrument page")

            if ticker and not _instrument_path_matches_ticker(final_path, ticker):
                return SourceParseResult(
                    False,
                    error=f"investing path slug mismatch for {ticker}: {final_path}",
                )

            state = _extract_state(resp.text)
            instrument = _instrument_from_state(state)
            if not instrument:
                return SourceParseResult(False, error="instrument payload not found")

            name_block = instrument.get("name") if isinstance(instrument.get("name"), dict) else {}
            page_symbol = str(name_block.get("symbol") or "").strip().upper()
            if ticker and page_symbol and page_symbol != ticker.strip().upper():
                return SourceParseResult(False, error="investing symbol mismatch")

            if product_name and not _instrument_matches_product(instrument, product_name):
                title = _instrument_title(instrument)
                return SourceParseResult(
                    False,
                    error=f"investing instrument name mismatch: {title}",
                )

            metrics = _map_metrics(instrument, asset_type)
            if not _has_useful_metrics(metrics):
                return SourceParseResult(
                    False,
                    metrics=metrics,
                    error="no concrete metrics on investing.com page",
                )

            title = product_name.strip() or _instrument_title(instrument)
            source = {
                "title": f"Investing.com: {title}",
                "url": f"{INVESTING_BASE}{final_path}",
                "type": "market_data",
                "parser_origin": "investing",
                "instrument_path": final_path,
                "expected_symbol": page_symbol or (ticker or "").upper(),
                "updatedAt": today,
            }
            metric_bits = ", ".join(f"{k}={v}" for k, v in metrics.items() if v is not None)
            line = f"Investing.com ({page_symbol or ticker or title}): {metric_bits}"
            return SourceParseResult(True, metrics=metrics, sources=[source], context_lines=[line])
    except Exception as exc:
        log.info("investing fetch failed product=%s error=%s", product_id, exc)
        return SourceParseResult(False, error=str(exc))
