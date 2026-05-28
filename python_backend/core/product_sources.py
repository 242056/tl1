"""Подсказки для поиска данных: URL и запросы по продуктам каталога ВТБ."""
from __future__ import annotations

from typing import Any, Dict, List

from .products import product_by_id, product_by_name

SourceHint = Dict[str, str]

_KIND_URLS: Dict[str, List[SourceHint]] = {
    "bpif": [
        {"title": "Инвестиции ВТБ — фонды", "url": "https://www.vtb.ru/personal/investicii/fondi/", "type": "issuer"},
        {"title": "MOEX", "url": "https://www.moex.com/", "type": "exchange"},
    ],
    "opif": [
        {"title": "ВИМ Инвестиции — фонды", "url": "https://viminvest.ru/funds/", "type": "issuer"},
        {"title": "e-disclosure", "url": "https://e-disclosure.ru/", "type": "regulator"},
    ],
    "zpif": [
        {"title": "ВИМ Инвестиции — ЗПИФ", "url": "https://viminvest.ru/funds/", "type": "issuer"},
        {"title": "e-disclosure", "url": "https://e-disclosure.ru/", "type": "regulator"},
    ],
    "iszh": [
        {"title": "ВТБ — ИСЖ", "url": "https://www.vtb.ru/personal/strahovanie/invest-strahovanie-zhizni/", "type": "issuer"},
    ],
    "nszh": [
        {"title": "ВТБ — НСЖ", "url": "https://www.vtb.ru/personal/strahovanie/nakopitelnoe-strahovanie-zhizni/", "type": "issuer"},
    ],
    "precious_metal": [
        {"title": "ВТБ — драгметаллы", "url": "https://www.vtb.ru/personal/investicii/dragocennye-metally/", "type": "issuer"},
        {"title": "ЦБ РФ — драгметаллы", "url": "https://www.cbr.ru/hd_base/metall/", "type": "regulator"},
    ],
    "deposit": [
        {"title": "ВТБ — вклады", "url": "https://www.vtb.ru/personal/vklady-i-scheta/vklady/", "type": "issuer"},
    ],
    "account": [
        {"title": "ВТБ — накопительный счёт", "url": "https://www.vtb.ru/personal/vklady-i-scheta/scheta/", "type": "issuer"},
    ],
    "pds": [
        {"title": "ВТБ — ПДС", "url": "https://www.vtb.ru/personal/investicii/pds/", "type": "issuer"},
    ],
}

_PRODUCT_SEARCH: Dict[str, List[str]] = {
    "opif_vim_key": [
        'ОПИФ "ВИМ - Ключевой+" стоимость пая СЧА доходность',
        "viminvest.ru ключевой+ открытый паевой фонд",
    ],
    "opif_vim_save": [
        'ОПИФ "ВИМ - Сбережения" стоимость пая СЧА',
        "viminvest.ru сбережения паевой фонд",
    ],
    "opif_vim_rentier": [
        'ОПИФ "ВИМ - Сбережения. Рантье" доходность',
        "viminvest рантье паевой фонд",
    ],
    "zpif_vim_re": [
        'ЗПИФ "ВИМ-Недвижимость" стоимость пая СЧА',
        "viminvest недвижимость закрытый паевой фонд",
    ],
    "zpif_rent2": ['ЗПИФ "Рентный доход 2" ВИМ', "e-disclosure рентный доход 2"],
    "zpif_rent3": ['ЗПИФ "Рентный доход 3" ВИМ', "e-disclosure рентный доход 3"],
    "iszh_basis": ['ИСЖ "Базис Актив 2.0" ВТБ условия доходность', "site:vtb.ru базис актив"],
    "iszh_driver": ['ИСЖ "Драйвер Гарантия" ВТБ', "site:vtb.ru драйвер гарантия"],
    "iszh_maximum": ['ИСЖ "Максимум" ВТБ умные инвестиции', "site:vtb.ru максимум исж"],
    "iszh_fixed_income": ['ИСЖ "Фиксированный доход" ВТБ', "site:vtb.ru фиксированный доход исж"],
    "nszh_future": ['НСЖ "Забота о будущем" ВТБ', "site:vtb.ru забота о будущем"],
    "nszh_family": ['НСЖ "Забота о семье" ВТБ', "site:vtb.ru забота о семье"],
    "nszh_ultra": ['НСЖ "На всякий случай Ультра" ВТБ', "site:vtb.ru ультра нсж"],
    "gold_oms": ["ВТБ золото ОМС курс ЦБ комиссия", "site:vtb.ru золото омс"],
    "gold_coins": ["ВТБ золотые монеты цена", "site:vtb.ru монеты золото"],
    "gold_bars": ["ВТБ золотые слитки цена", "site:vtb.ru слитки"],
    "deposit_vtb": ["ВТБ-Вклад ставка минимальная сумма", "site:vtb.ru вклад ставка"],
    "account_vtb": ["Накопительный ВТБ счёт ставка", "site:vtb.ru накопительный счет"],
    "pds": ["ПДС ВТБ господдержка условия", "site:vtb.ru программа долгосрочных сбережений"],
}


def search_hints(product_id: str, product_name: str, kind: str) -> List[str]:
    out: List[str] = list(_PRODUCT_SEARCH.get(product_id, []))
    if not out:
        out.append(f"{product_name} ВТБ официальные условия site:vtb.ru")
    if kind in ("opif", "zpif"):
        out.append(f"{product_name} e-disclosure отчётность паевой фонд")
    return out[:4]


def source_hints(product_id: str, kind: str) -> List[SourceHint]:
    urls: List[SourceHint] = list(_KIND_URLS.get(kind, []))
    return urls[:4]


def enrichment_bundle(asset_id: str, kind: str) -> Dict[str, Any]:
    product = product_by_name(asset_id) or product_by_id(asset_id)
    product_id = (product or {}).get("productId", asset_id)
    product_name = (product or {}).get("productName", asset_id)
    hints = search_hints(product_id, product_name, kind)
    sources = source_hints(product_id, kind)
    lines = [f"Поиск: {q}" for q in hints]
    lines.extend(f"Источник: {s['title']} — {s['url']}" for s in sources)
    return {
        "product_id": product_id,
        "product_name": product_name,
        "search_queries": hints,
        "recommended_sources": sources,
        "context_lines": lines,
    }
