"""Проверка доступности URL источников перед показом пользователю."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, List
from urllib.parse import parse_qs, urlparse

import httpx

from .nlu import clean_public_url, is_valid_http_url
from .product_sources import catalog_page_url

# В UI — MOEX, Investing.com, ЦБ РФ, vtb.ru, wealthim.ru (каталог).
_DISPLAYABLE_URL_PATTERNS = (
    re.compile(r"^https://www\.moex\.com/ru/issue\.aspx\?code=[A-Z0-9]+$", re.I),
    re.compile(r"^https://ru\.investing\.com/(etfs|commodities|funds)/[a-z0-9-]+$", re.I),
    re.compile(r"^https://www\.cbr\.ru/hd_base/metall/?$", re.I),
    re.compile(r"^https://www\.vtb\.ru/personal/[a-z0-9\-_/]+/?$", re.I),
    re.compile(r"^https://private\.vtb\.ru/[a-z0-9\-_/]+/?$", re.I),
    re.compile(r"^https://www\.wealthim\.ru/?$", re.I),
    re.compile(r"^https://www\.wealthim\.ru/products/pif/(opif|zpif)/[a-z0-9_-]+/?$", re.I),
)

_BLOCKED_URL_MARKERS = (
    "iss.moex.com/iss",
    "viminvest.ru",
    "e-disclosure.ru",
    "/api/",
    "localhost",
)

_ALLOWED_PARSER_ORIGINS = frozenset({"moex", "investing", "cbr", "vtb", "wealthim"})

log = logging.getLogger("vtb.source_validator")

_USER_AGENT = "VTB-MVP-AssetAnalysis/1.0"
_SOURCE_CANDIDATE_LIMIT = 12


def source_item_url(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("url") or "").strip()
    return ""


def is_displayable_source_url(url: str) -> bool:
    """URL можно показывать пользователю — только проверенные шаблоны, без generic/home/API."""
    cleaned = clean_public_url((url or "").strip())
    if not cleaned or not is_valid_http_url(cleaned):
        return False
    low = cleaned.lower()
    if any(marker in low for marker in _BLOCKED_URL_MARKERS):
        return False
    if any(pat.match(cleaned) for pat in _DISPLAYABLE_URL_PATTERNS):
        return True
    return False


def filter_display_sources(sources: List[Any], *, product_id: str | None = None) -> List[Any]:
    """Оставляет источники с URL, разрешёнными для показа в паспорте."""
    out: List[Any] = []
    seen: set[str] = set()
    for item in sources:
        if not isinstance(item, dict):
            continue
        origin = str(item.get("parser_origin") or "").strip().lower()
        if origin not in _ALLOWED_PARSER_ORIGINS:
            continue
        url = clean_public_url(source_item_url(item))
        if not url or url in seen or not is_displayable_source_url(url):
            continue
        if product_id and not _source_matches_product(url, origin, product_id, item):
            continue
        seen.add(url)
        out.append(_normalize_source_item(item))
    return out


def _investing_path_matches_ticker(path: str, ticker: str) -> bool:
    t = (ticker or "").strip().upper()
    slug = (path or "").lower()
    if not t or not slug:
        return False
    if t == "GOLD":
        return "gold" in slug
    return t.lower() in slug


def _source_matches_product(url: str, origin: str, product_id: str, item: Any) -> bool:
    """URL должен относиться к тому же инструменту, что и product_id в каталоге."""
    from .products import MOEX_TICKER_BY_PRODUCT

    ticker = (MOEX_TICKER_BY_PRODUCT.get(product_id) or "").upper()
    if not ticker:
        return True
    if origin == "moex":
        qs = parse_qs(urlparse(url).query)
        code = (qs.get("code") or [""])[0].strip().upper()
        return code == ticker
    if origin == "investing":
        expected_path = ""
        if isinstance(item, dict):
            expected_path = str(item.get("instrument_path") or "").strip()
        if expected_path and expected_path.lower() not in url.lower():
            return False
        if ticker and expected_path and not _investing_path_matches_ticker(expected_path, ticker):
            return False
        return True
    if origin == "cbr":
        return product_id in {
            "gold_oms",
            "gold_coins",
            "gold_bars",
            "platinum_oms",
            "palladium_oms",
        }
    if origin == "vtb":
        expected = catalog_page_url(product_id, "vtb")
        if not expected:
            return True
        return url.rstrip("/").lower() == expected.rstrip("/").lower()
    if origin == "wealthim":
        expected = catalog_page_url(product_id, "wealthim")
        if not expected:
            return url.rstrip("/").lower() in {
                "https://www.wealthim.ru",
                "https://www.wealthim.ru/",
            }
        return url.rstrip("/").lower() == expected.rstrip("/").lower()
    return False


def _normalize_source_item(item: Any) -> Any:
    url = clean_public_url(source_item_url(item))
    if not url:
        return item
    if isinstance(item, dict):
        return {**item, "url": url}
    return url


async def _probe_url(client: httpx.AsyncClient, url: str) -> bool:
    if not url or not is_valid_http_url(url):
        return False
    if not is_displayable_source_url(url):
        return False
    host = (urlparse(url).hostname or "").lower()
    use_get = host.endswith("vtb.ru") or host.endswith("wealthim.ru")
    try:
        if use_get:
            resp = await client.get(url)
        else:
            resp = await client.head(url)
            if resp.status_code in {405, 501, 404}:
                resp = await client.get(url)
        if resp.status_code >= 400:
            log.info("Source URL rejected status=%s url=%s", resp.status_code, url)
            return False
        final_url = clean_public_url(str(resp.url))
        if not is_displayable_source_url(final_url):
            log.info("Source URL redirect to disallowed target url=%s final=%s", url, final_url)
            return False
        return True
    except httpx.HTTPError as exc:
        log.info("Source URL unreachable url=%s error=%s", url, exc)
        return False


async def is_source_reachable(url: str, *, timeout: float | None = None) -> bool:
    t = timeout if timeout is not None else float(os.getenv("HTTP_SOURCE_CHECK_TIMEOUT_SEC", "5"))
    async with httpx.AsyncClient(
        timeout=t,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        return await _probe_url(client, url)


async def select_reachable_sources(
    sources: List[Any],
    *,
    limit: int = 3,
    timeout: float | None = None,
    product_id: str | None = None,
) -> List[Any]:
    """Оставляет до limit источников с живыми URL, сохраняя исходный приоритет."""
    if not sources or limit <= 0:
        return []

    t = timeout if timeout is not None else float(os.getenv("HTTP_SOURCE_CHECK_TIMEOUT_SEC", "5"))
    normalized = filter_display_sources(sources, product_id=product_id)

    async with httpx.AsyncClient(
        timeout=t,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        checks = await asyncio.gather(*(_probe_url(client, source_item_url(s)) for s in normalized))

    out: List[Any] = []
    for item, ok in zip(normalized, checks):
        if not ok:
            continue
        out.append(item)
        if len(out) >= limit:
            break

    if not out:
        catalog = [
            s
            for s in normalized
            if isinstance(s, dict)
            and str(s.get("catalog_verified") or "") == "1"
            and str(s.get("parser_origin") or "").lower() in {"moex", "vtb", "wealthim"}
        ]
        out = catalog[:limit]

    return out


def candidate_limit() -> int:
    return _SOURCE_CANDIDATE_LIMIT
