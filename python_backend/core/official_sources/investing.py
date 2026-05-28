"""Ссылка и контекст Investing.com (без агрессивного скрапинга)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

log = logging.getLogger("vtb.official_sources.investing")

# Известные slug для части БПИФ; иначе только поисковая ссылка.
INVESTING_SLUG_BY_TICKER = {
    "GOLD": "gold-moscow",
    "LQDT": "lqdt",
}


@dataclass
class SourceParseResult:
    ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    error: str | None = None


def _slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9а-яё]+", "-", s, flags=re.I)
    return s.strip("-")[:60]


async def fetch_investing(api, ticker: str | None, product_name: str) -> SourceParseResult:
    today = datetime.now(timezone.utc).date().isoformat()
    slug = INVESTING_SLUG_BY_TICKER.get((ticker or "").upper()) or _slugify(product_name)
    url = f"https://ru.investing.com/etfs/{slug}" if slug else "https://ru.investing.com/etfs"

    source = {
        "title": "Investing.com — карточка инструмента",
        "url": url,
        "type": "market_data",
        "updatedAt": today,
    }

    # Пробуем получить заголовок страницы; при блокировке оставляем только ссылку.
    title_hint = ""
    try:
        timeout = float(__import__("os").getenv("HTTP_TIMEOUT_SEC", "15"))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "VTB-MVP-AssetAnalysis/1.0"})
            if r.status_code == 200:
                m = re.search(r"<title>([^<]+)</title>", r.text, re.I)
                if m:
                    title_hint = m.group(1).strip()[:120]
    except Exception as exc:
        log.debug("investing fetch skipped: %s", exc)

    line = f"Investing.com: {title_hint or url}"
    return SourceParseResult(True, sources=[source], context_lines=[line])
