"""Подсказки для поиска и официальные ссылки на продукты каталога ВТБ."""
from __future__ import annotations

from typing import Any, Dict, List

from .products import product_by_id, product_by_name

_PRODUCT_SEARCH: Dict[str, List[str]] = {
    "opif_vim_key": [
        'ОПИФ "ВИМ - Ключевой+" стоимость пая СЧА доходность',
        "wealthim.ru ключевой+ открытый паевой фонд",
    ],
    "opif_vim_save": [
        'ОПИФ "ВИМ - Сбережения" стоимость пая СЧА',
        "wealthim.ru сбережения паевой фонд",
    ],
    "opif_vim_rentier": [
        'ОПИФ "ВИМ - Сбережения. Рантье" доходность',
        "wealthim.ru рантье паевой фонд",
    ],
    "zpif_vim_re": [
        'ЗПИФ "ВИМ-Недвижимость" стоимость пая СЧА',
        "wealthim.ru недвижимость закрытый паевой фонд",
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
    "palladium_oms": ["ВТБ палладий ОМС курс ЦБ", "учётная цена палладия ЦБ РФ"],
    "platinum_oms": ["ВТБ платина ОМС курс ЦБ", "учётная цена платины ЦБ РФ"],
    "gold_coins": ["ВТБ золотые монеты цена", "site:vtb.ru монеты золото"],
    "gold_bars": ["ВТБ золотые слитки цена", "site:vtb.ru слитки"],
    "deposit_vtb": ["ВТБ-Вклад ставка минимальная сумма", "site:vtb.ru вклад ставка"],
    "account_vtb": ["Накопительный ВТБ счёт ставка", "site:vtb.ru накопительный счет"],
    "pds": ["ПДС ВТБ господдержка условия", "site:vtb.ru программа долгосрочных сбережений"],
}

# Официальные страницы на vtb.ru (проверенные URL, без query-параметров).
_PRODUCT_OFFICIAL_PAGES: Dict[str, Dict[str, str]] = {
    "deposit_vtb": {
        "url": "https://www.vtb.ru/personal/vklady-i-scheta/vtb-vklad-r/",
        "title": "ВТБ-Вклад — условия на vtb.ru",
    },
    "account_vtb": {
        "url": "https://www.vtb.ru/personal/vklady-i-scheta/vtb-schet/",
        "title": "Накопительный ВТБ-Счёт — условия на vtb.ru",
    },
    "pds": {
        "url": "https://www.vtb.ru/personal/investicii/pds/",
        "title": "Программа долгосрочных сбережений — vtb.ru",
    },
    "gold_oms": {
        "url": "https://www.vtb.ru/personal/vklady-i-scheta/obezlichennyj-metallicheskij-schet/",
        "title": "ОМС — vtb.ru",
    },
    "gold_coins": {
        "url": "https://www.vtb.ru/personal/vklady-i-scheta/kurs-zolota/",
        "title": "Золото — vtb.ru",
    },
    "gold_bars": {
        "url": "https://www.vtb.ru/personal/vklady-i-scheta/kurs-zolota/",
        "title": "Золото в слитках — vtb.ru",
    },
    "palladium_oms": {
        "url": "https://www.vtb.ru/personal/vklady-i-scheta/kurs-palladiya/",
        "title": "Палладий на ОМС — vtb.ru",
    },
    "platinum_oms": {
        "url": "https://www.vtb.ru/personal/vklady-i-scheta/obezlichennyj-metallicheskij-schet/",
        "title": "Платина на ОМС — vtb.ru",
    },
    "iszh_basis": {
        "url": "https://www.vtb.ru/personal/drugie-uslugi/strahovye-i-servisnye-produkty/investitsionnoe-strakhovanie-zhizni/",
        "title": "ИСЖ — vtb.ru",
    },
    "iszh_driver": {
        "url": "https://www.vtb.ru/personal/drugie-uslugi/strahovye-i-servisnye-produkty/investitsionnoe-strakhovanie-zhizni/",
        "title": "ИСЖ — vtb.ru",
    },
    "iszh_maximum": {
        "url": "https://www.vtb.ru/personal/drugie-uslugi/strahovye-i-servisnye-produkty/investitsionnoe-strakhovanie-zhizni/",
        "title": "ИСЖ — vtb.ru",
    },
    "iszh_fixed_income": {
        "url": "https://www.vtb.ru/personal/drugie-uslugi/strahovye-i-servisnye-produkty/investitsionnoe-strakhovanie-zhizni/",
        "title": "ИСЖ — vtb.ru",
    },
    "nszh_future": {
        "url": "https://www.vtb.ru/personal/drugie-uslugi/strahovye-i-servisnye-produkty/nakopitelnoe-strakhovanie-zhizni/",
        "title": "НСЖ — vtb.ru",
    },
    "nszh_family": {
        "url": "https://www.vtb.ru/personal/drugie-uslugi/strahovye-i-servisnye-produkty/nakopitelnoe-strakhovanie-zhizni/",
        "title": "НСЖ «Забота о семье» — vtb.ru",
    },
    "nszh_ultra": {
        "url": "https://www.vtb.ru/personal/drugie-uslugi/strahovye-i-servisnye-produkty/nakopitelnoe-strakhovanie-zhizni/",
        "title": "НСЖ — vtb.ru",
    },
    "intellect_eternal": {
        "url": "https://www.vtb.ru/personal/investicii/intellect/",
        "title": "Интеллект — vtb.ru",
    },
    "intellect_ai": {
        "url": "https://www.vtb.ru/personal/investicii/intellect/",
        "title": "Интеллект — vtb.ru",
    },
    "intellect_conservative": {
        "url": "https://www.vtb.ru/personal/investicii/intellect/",
        "title": "Интеллект — vtb.ru",
    },
    "diamonds": {
        "url": "https://private.vtb.ru/bankovskie-uslugi/alternativnye-sberezheniya/investicionnye-brillianty/",
        "title": "Инвестиционные бриллианты — vtb.ru",
    },
    "zpif_vim_re": {
        "url": "https://www.wealthim.ru/",
        "title": "УК «ВИМ Инвестиции» — раскрытие информации",
    },
    "zpif_rent2": {
        "url": "https://www.wealthim.ru/",
        "title": "УК «ВИМ Инвестиции» — раскрытие информации",
    },
    "zpif_rent3": {
        "url": "https://www.wealthim.ru/",
        "title": "УК «ВИМ Инвестиции» — раскрытие информации",
    },
}

# Карточки фондов на сайте УК (для ОПИФ без MOEX/Investing).
_PRODUCT_WEALTHIM_PAGES: Dict[str, Dict[str, str]] = {
    "opif_vim_save": {
        "url": "https://www.wealthim.ru/products/pif/opif/wimsbr/",
        "title": 'ОПИФ «ВИМ — Сбережения» — wealthim.ru',
    },
    "opif_vim_key": {
        "url": "https://www.wealthim.ru/products/pif/opif/wimklych/",
        "title": 'ОПИФ «ВИМ — Ключевой+» — wealthim.ru',
    },
    "opif_vim_rentier": {
        "url": "https://www.wealthim.ru/products/pif/opif/wimsbran/",
        "title": 'ОПИФ «ВИМ — Сбережения. Рантье» — wealthim.ru',
    },
}


def _catalog_source(page: Dict[str, str], *, product_id: str, origin: str) -> Dict[str, str]:
    return {
        "title": page.get("title") or product_id,
        "url": (page.get("url") or "").strip(),
        "parser_origin": origin,
        "product_id": product_id,
        "catalog_verified": "1",
    }


def official_catalog_sources(product_id: str, product_name: str) -> List[Dict[str, str]]:
    """Ссылки на официальные страницы для продуктов без биржевых парсеров."""
    out: List[Dict[str, str]] = []
    vtb = _PRODUCT_OFFICIAL_PAGES.get(product_id)
    if vtb and vtb.get("url"):
        out.append(_catalog_source(vtb, product_id=product_id, origin="vtb"))
    wealthim = _PRODUCT_WEALTHIM_PAGES.get(product_id)
    if wealthim and wealthim.get("url"):
        out.append(_catalog_source(wealthim, product_id=product_id, origin="wealthim"))
    return out


def official_page_url(product_id: str) -> str | None:
    page = _PRODUCT_OFFICIAL_PAGES.get(product_id) or _PRODUCT_WEALTHIM_PAGES.get(product_id)
    if not page:
        return None
    url = (page.get("url") or "").strip()
    return url or None


def catalog_page_url(product_id: str, origin: str) -> str | None:
    if origin == "wealthim":
        page = _PRODUCT_WEALTHIM_PAGES.get(product_id)
    else:
        page = _PRODUCT_OFFICIAL_PAGES.get(product_id)
    if not page:
        return None
    url = (page.get("url") or "").strip()
    return url or None


def search_hints(product_id: str, product_name: str, kind: str) -> List[str]:
    out: List[str] = list(_PRODUCT_SEARCH.get(product_id, []))
    if not out:
        out.append(f"{product_name} ВТБ официальные условия site:vtb.ru")
    if kind in ("opif", "zpif"):
        out.append(f"{product_name} wealthim.ru e-disclosure отчётность паевой фонд")
    return out[:4]


def enrichment_bundle(asset_id: str, kind: str) -> Dict[str, Any]:
    product = product_by_name(asset_id) or product_by_id(asset_id)
    product_id = (product or {}).get("productId", asset_id)
    product_name = (product or {}).get("productName", asset_id)
    hints = search_hints(product_id, product_name, kind)
    return {
        "product_id": product_id,
        "product_name": product_name,
        "search_queries": hints,
        "context_lines": [f"Поиск: {q}" for q in hints],
    }
