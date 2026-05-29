"""Маршрутизация запросов агента: диалог vs математический паспорт."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .nlu import detect_intent, extract_portfolio
from .products import PRODUCT_UNIVERSE, product_by_name

_ASSET_KEYWORDS = re.compile(
    r"паспорт|анти[\s-]?гугл|математическ\w*\s+паспорт|"
    r"ключев\w*\s+показател|показател\w*\s+продукта|"
    r"анализ\s+продукта|что\s+за\s+продукт|характеристик\w*\s+продукта",
    re.I,
)

_ASSET_VERBS = re.compile(
    r"расскаж|покаж|опиш|проанализ|найди\s+данн|узнать\s+о|информац\w*\s+о",
    re.I,
)

_CHIP_PREFIX = re.compile(r"^паспорт:\s*", re.I)

_EXPLICIT_DIALOG = re.compile(
    r"бэ?к[\s\-]?тест|бектест|^сценар|сценар\s|что если|"
    r"рост\s+став|падени\w*\s+индекс|индекс\w*\s+(?:упад|сниз|пад)|"
    r"(?:рубл|доллар|валют).*(?:ослаб|шок)|ослаб\w*\s+(?:рубл|доллар)",
    re.I,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("«", "").replace("»", "").replace('"', "")).strip()


def match_product(text: str) -> Optional[Dict[str, str]]:
    raw = _CHIP_PREFIX.sub("", text or "").strip()
    t = _norm(raw)
    if not t:
        return None

    exact = product_by_name(raw.strip()) or product_by_name(text.strip())
    if exact:
        return exact

    best: Optional[Dict[str, str]] = None
    best_score = -1
    for p in PRODUCT_UNIVERSE:
        name = _norm(p["productName"])
        if not name:
            continue
        score = 0
        if name == t:
            score = 1000
        elif t in name:
            # «ВИМ - Сбережения» не должно матчиться на «…Сбережения. Рантье»
            score = 500 - len(name)
        elif name in t:
            score = 400 + len(name)
        if score > 0 and score > best_score:
            best = p
            best_score = score
        # короткие алиасы
        aliases = {
            "bpif_gold_exchange": ["золото биржев", "gold", "золото.биржев"],
            "bpif_liquidity": ["ликвидность", "lqdt"],
            "bpif_moex_index": ["индекс мос", "tmos", "мосбирж"],
            "deposit_vtb": ["втб-вклад", "вклад втб"],
            "account_vtb": ["накопительный", "втб счет", "втб-счет"],
            "gold_oms": ["золото омс", "омс золото"],
            "opif_vim_save": ["вим - сбережения", "вим сбережения", "сбережения вим"],
            "opif_vim_rentier": ["рантье", "сбережения. рантье"],
            "opif_vim_key": ["ключевой+", "ключевой"],
        }
        for alias in aliases.get(p["productId"], []):
            if alias in t or t == alias:
                alias_score = 800 + len(alias)
                if alias_score > best_score:
                    best = p
                    best_score = alias_score

    return best if best_score > 0 else None


def is_passport_chip(text: str) -> bool:
    return bool(_CHIP_PREFIX.match((text or "").strip()))


def detect_agent_route(
    text: str,
    *,
    pending_asset: bool = False,
    pending_dialog_intent: str | None = None,
) -> str:
    """DIALOG | ASSET | AUTO"""
    msg = (text or "").strip()
    if not msg:
        return "AUTO"

    if pending_asset:
        return "ASSET"

    if is_passport_chip(msg):
        return "ASSET"

    if _ASSET_KEYWORDS.search(msg):
        return "ASSET"

    if pending_dialog_intent in {"BACKTEST", "SCENARIO"}:
        return "DIALOG"

    v = msg.lower()

    if extract_portfolio(msg):
        return "DIALOG"

    product = match_product(msg)
    if product and not _EXPLICIT_DIALOG.search(v):
        t = _norm(msg)
        name = _norm(product["productName"])
        if name == t or t in name or name in t:
            return "ASSET"

    dialog_intent = detect_intent(msg)
    if dialog_intent in {"BACKTEST", "SCENARIO"}:
        if not _ASSET_KEYWORDS.search(v):
            return "DIALOG"

    if _ASSET_KEYWORDS.search(v):
        return "ASSET"

    if product:
        t = _norm(msg)
        name = _norm(product["productName"])
        product_named = name == t or t in name or name in t
        if _ASSET_VERBS.search(v) or _CHIP_PREFIX.match(msg) or product_named:
            if dialog_intent == "UNKNOWN" or _ASSET_VERBS.search(v) or _CHIP_PREFIX.match(msg) or product_named:
                return "ASSET"

    return "AUTO"


def product_suggestions(limit: int = 6) -> List[Dict[str, str]]:
    popular_ids = [
        "bpif_liquidity",
        "bpif_gold_exchange",
        "bpif_moex_index",
        "opif_vim_save",
        "deposit_vtb",
        "iszh_basis",
    ]
    out: List[Dict[str, str]] = []
    by_id = {p["productId"]: p for p in PRODUCT_UNIVERSE}
    for pid in popular_ids:
        if pid in by_id:
            out.append(by_id[pid])
    if len(out) < limit:
        for p in PRODUCT_UNIVERSE:
            if p not in out:
                out.append(p)
            if len(out) >= limit:
                break
    return out[:limit]


def asset_action_label(product: Dict[str, str]) -> str:
    name = product.get("productName", "")
    short = name.replace("БПИФ ", "").replace('ОПИФ "', "").replace('"', "")
    if len(short) > 36:
        short = short[:33] + "…"
    return f"Паспорт: {short}"
