"""Вселенная продуктов ВТБ для MVP (портфели, сценарии, анти-гугл)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Полная вселенная (единственный источник названий продуктов в заглушках).
PRODUCT_UNIVERSE: List[Dict[str, str]] = [
    {"productId": "bpif_gold_exchange", "productName": "БПИФ «Золото.Биржевой»", "kind": "bpif", "category": "Фонды"},
    {"productId": "bpif_moex_index", "productName": "БПИФ «Индекс МосБиржи»", "kind": "bpif", "category": "Фонды"},
    {"productId": "bpif_liquidity", "productName": "БПИФ «Ликвидность»", "kind": "bpif", "category": "Фонды"},
    {"productId": "bpif_ru_bonds", "productName": "БПИФ «Российские облигации»", "kind": "bpif", "category": "Фонды"},
    {"productId": "bpif_esg_ru", "productName": "БПИФ «Устойчивое развитие российских компаний»", "kind": "bpif", "category": "Фонды"},
    {"productId": "deposit_vtb", "productName": "Вклад ВТБ-Вклад", "kind": "deposit", "category": "Денежные продукты"},
    {"productId": "gold_coins", "productName": "Золото в монетах", "kind": "precious_metal", "category": "Драгметаллы"},
    {"productId": "gold_bars", "productName": "Золото в слитках", "kind": "precious_metal", "category": "Драгметаллы"},
    {"productId": "gold_oms", "productName": "Золото на ОМС", "kind": "precious_metal", "category": "Драгметаллы"},
    {"productId": "zpif_vim_re", "productName": 'ЗПИФ "ВИМ-Недвижимость"', "kind": "zpif", "category": "Фонды"},
    {"productId": "zpif_rent2", "productName": 'ЗПИФ "Рентный доход 2"', "kind": "zpif", "category": "Фонды"},
    {"productId": "zpif_rent3", "productName": 'ЗПИФ "Рентный доход 3"', "kind": "zpif", "category": "Фонды"},
    {"productId": "diamonds", "productName": "Инвестиционные бриллианты", "kind": "alternative", "category": "Альтернативы"},
    {"productId": "intellect_eternal", "productName": "Интеллект. Вечный портфель", "kind": "intellect", "category": "Готовые стратегии"},
    {"productId": "intellect_ai", "productName": "Интеллект. Искусственный интеллект", "kind": "intellect", "category": "Готовые стратегии"},
    {"productId": "intellect_conservative", "productName": "Интеллект. Консервативный портфель", "kind": "intellect", "category": "Готовые стратегии"},
    {"productId": "iszh_basis", "productName": 'ИСЖ "Базис Актив 2.0."', "kind": "iszh", "category": "Страхование"},
    {"productId": "iszh_driver", "productName": 'ИСЖ "Драйвер Гарантия"', "kind": "iszh", "category": "Страхование"},
    {"productId": "iszh_maximum", "productName": 'ИСЖ "Максимум" Умные инвестиции', "kind": "iszh", "category": "Страхование"},
    {"productId": "iszh_fixed_income", "productName": 'ИСЖ "Фиксированный доход"', "kind": "iszh", "category": "Страхование"},
    {"productId": "account_vtb", "productName": "Накопительный ВТБ Счет", "kind": "account", "category": "Денежные продукты"},
    {"productId": "nszh_future", "productName": 'НСЖ "Забота о будущем"', "kind": "nszh", "category": "Страхование"},
    {"productId": "nszh_family", "productName": 'НСЖ "Забота о семье"', "kind": "nszh", "category": "Страхование"},
    {"productId": "nszh_ultra", "productName": 'НСЖ "На всякий случай Ультра"', "kind": "nszh", "category": "Страхование"},
    {"productId": "opif_vim_key", "productName": 'ОПИФ "ВИМ - Ключевой+"', "kind": "opif", "category": "Фонды"},
    {"productId": "opif_vim_save", "productName": 'ОПИФ "ВИМ - Сбережения"', "kind": "opif", "category": "Фонды"},
    {"productId": "opif_vim_rentier", "productName": 'ОПИФ "ВИМ - Сбережения. Рантье"', "kind": "opif", "category": "Фонды"},
    {"productId": "palladium_oms", "productName": "Палладий на ОМС", "kind": "precious_metal", "category": "Драгметаллы"},
    {"productId": "platinum_oms", "productName": "Платина на ОМС", "kind": "precious_metal", "category": "Драгметаллы"},
    {"productId": "pds", "productName": "Программа долгосрочных сбережений (ПДС)", "kind": "pds", "category": "Пенсионные накопления"},
]

_BY_ID = {p["productId"]: p for p in PRODUCT_UNIVERSE}
_BY_NAME = {p["productName"]: p for p in PRODUCT_UNIVERSE}

# Тикеры MOEX для БПИФ (официальные источники).
MOEX_TICKER_BY_PRODUCT: Dict[str, str] = {
    "bpif_gold_exchange": "GOLD",
    "bpif_liquidity": "LQDT",
    "bpif_moex_index": "TMOS",
    "bpif_ru_bonds": "SBMX",
    "bpif_esg_ru": "ESG",
}


def product_by_id(product_id: str) -> Optional[Dict[str, str]]:
    return _BY_ID.get(product_id)


def product_by_name(name: str) -> Optional[Dict[str, str]]:
    return _BY_NAME.get(name)


def universe_for_api() -> List[Dict[str, str]]:
    return list(PRODUCT_UNIVERSE)


def _alloc(
    placement_amount: int,
    rows: List[Tuple[str, float]],
) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    for product_id, weight in rows:
        meta = _BY_ID[product_id]
        products.append(
            {
                "productId": product_id,
                "productName": meta["productName"],
                "category": meta["category"],
                "kind": meta["kind"],
                "weight": weight,
                "amount": int(round(placement_amount * weight)),
            }
        )
    return products


# Тестовый «текущий» портфель клиента (2,5 млн ₽).
CURRENT_PORTFOLIO: Dict[str, Any] = {
    "portfolioId": "portfolio_current",
    "portfolioName": "Текущий портфель (тест)",
    "currency": "RUB",
    "investmentHorizon": "5_years",
    "placementAmount": 2_500_000,
    "expectedReturn": {"target": 12.4, "inflationAdjusted": True},
    "riskProfile": "medium",
    "summary": {
        "description": "Тестовый текущий портфель из продуктов вселенной ВТБ: фонды, ликвидность и драгметаллы.",
    },
    "products": _alloc(
        2_500_000,
        [
            ("bpif_liquidity", 0.20),
            ("bpif_ru_bonds", 0.25),
            ("bpif_moex_index", 0.20),
            ("bpif_gold_exchange", 0.10),
            ("account_vtb", 0.15),
            ("opif_vim_save", 0.10),
        ],
    ),
    "goal": {
        "enabled": True,
        "goalName": "Финансовая подушка",
        "targetAmount": 3_000_000,
        "currentInvestment": 2_500_000,
        "investmentTermYears": 5,
        "goalAchievable": False,
        "recommendedMonthlyContribution": 12000,
    },
    "rebalance": {"enabled": True, "frequency": "quarterly"},
}


def _portfolio_shell(
    portfolio_id: str,
    name: str,
    placement: int,
    horizon: str,
    risk: str,
    target_return: float,
    description: str,
    product_rows: List[Tuple[str, float]],
    goal: Dict[str, Any],
    rebalance_frequency: str = "quarterly",
) -> Dict[str, Any]:
    return {
        "portfolioId": portfolio_id,
        "portfolioName": name,
        "currency": "RUB",
        "investmentHorizon": horizon,
        "placementAmount": placement,
        "expectedReturn": {"target": target_return, "inflationAdjusted": True},
        "riskProfile": risk,
        "summary": {"description": description},
        "products": _alloc(placement, product_rows),
        "goal": goal,
        "rebalance": {"enabled": True, "frequency": rebalance_frequency},
    }


# Пять вариантов предложенного портфеля для /api/portfolio/generate.
PROPOSED_PORTFOLIOS: List[Dict[str, Any]] = [
    _portfolio_shell(
        "portfolio_784512",
        "Сбалансированный мультипродукт",
        3_000_000,
        "5_years",
        "medium",
        14.5,
        "Диверсификация между фондами, ликвидностью и защитными инструментами из линейки ВТБ.",
        [
            ("bpif_ru_bonds", 0.30),
            ("bpif_moex_index", 0.25),
            ("bpif_liquidity", 0.15),
            ("bpif_gold_exchange", 0.10),
            ("account_vtb", 0.10),
            ("opif_vim_save", 0.10),
        ],
        {
            "enabled": True,
            "goalName": "Образование ребенка",
            "targetAmount": 5_000_000,
            "currentInvestment": 1_500_000,
            "investmentTermYears": 10,
            "goalAchievable": False,
            "recommendedMonthlyContribution": 25000,
        },
    ),
    _portfolio_shell(
        "portfolio_551204",
        "Доход и ликвидность",
        2_500_000,
        "5_years",
        "medium",
        13.2,
        "Упор на облигационные БПИФ, накопительный счёт и консервативные ОПИФ.",
        [
            ("bpif_ru_bonds", 0.35),
            ("bpif_liquidity", 0.20),
            ("account_vtb", 0.15),
            ("opif_vim_rentier", 0.15),
            ("iszh_fixed_income", 0.15),
        ],
        {
            "enabled": True,
            "goalName": "Пассивный капитал",
            "targetAmount": 4_500_000,
            "currentInvestment": 1_000_000,
            "investmentTermYears": 9,
            "goalAchievable": False,
            "recommendedMonthlyContribution": 22000,
        },
    ),
    _portfolio_shell(
        "portfolio_330119",
        "Защитный баланс",
        1_800_000,
        "3_years",
        "low",
        10.4,
        "Сохранение капитала: облигации, ликвидность, золото и консервативная стратегия Интеллект.",
        [
            ("bpif_ru_bonds", 0.35),
            ("bpif_liquidity", 0.25),
            ("gold_oms", 0.15),
            ("account_vtb", 0.15),
            ("intellect_conservative", 0.10),
        ],
        {
            "enabled": False,
            "goalName": "Резерв",
            "targetAmount": 0,
            "currentInvestment": 0,
            "investmentTermYears": 0,
            "goalAchievable": True,
            "recommendedMonthlyContribution": 0,
        },
        rebalance_frequency="semi_annual",
    ),
    _portfolio_shell(
        "portfolio_889021",
        "Рост и альтернативы",
        4_000_000,
        "10_years",
        "high",
        18.1,
        "Акцент на индексные и тематические продукты, недвижимость и ИИ-стратегию.",
        [
            ("bpif_moex_index", 0.30),
            ("bpif_esg_ru", 0.15),
            ("intellect_ai", 0.15),
            ("zpif_vim_re", 0.20),
            ("bpif_gold_exchange", 0.10),
            ("opif_vim_key", 0.10),
        ],
        {
            "enabled": True,
            "goalName": "Финансовая независимость",
            "targetAmount": 12_000_000,
            "currentInvestment": 2_500_000,
            "investmentTermYears": 12,
            "goalAchievable": False,
            "recommendedMonthlyContribution": 45000,
        },
    ),
    _portfolio_shell(
        "portfolio_472883",
        "Краткосрочный доход",
        1_200_000,
        "3_years",
        "low",
        9.7,
        "Депозит, ликвидные БПИФ и программа долгосрочных сбережений.",
        [
            ("deposit_vtb", 0.30),
            ("bpif_liquidity", 0.25),
            ("bpif_ru_bonds", 0.25),
            ("pds", 0.20),
        ],
        {
            "enabled": True,
            "goalName": "Первоначальный взнос",
            "targetAmount": 2_000_000,
            "currentInvestment": 700_000,
            "investmentTermYears": 4,
            "goalAchievable": False,
            "recommendedMonthlyContribution": 18000,
        },
        rebalance_frequency="monthly",
    ),
]


def _pn(product_id: str) -> str:
    return _BY_ID[product_id]["productName"]


# Сценарии: влияние на продукты из вселенной (поле asset_name в API — историческое имя).
SCENARIO_CONFIGS: Dict[str, Dict[str, Any]] = {
    "rate_hike": {
        "losers": [
            {"asset_name": _pn("bpif_ru_bonds"), "coef": 1.7},
            {"asset_name": _pn("zpif_vim_re"), "coef": 0.9},
            {"asset_name": _pn("iszh_maximum"), "coef": 0.55},
        ],
        "winners": [
            {"asset_name": _pn("bpif_liquidity"), "coef": 0.4},
            {"asset_name": _pn("account_vtb"), "coef": 0.35},
            {"asset_name": _pn("deposit_vtb"), "coef": 0.12},
        ],
        "explanation": (
            "Рост ключевой ставки обычно снижает котировки длинных облигационных фондов и чувствительных "
            "к ставке продуктов, тогда как ликвидные и депозитные инструменты становятся относительно привлекательнее."
        ),
    },
    "market_drop": {
        "losers": [
            {"asset_name": _pn("bpif_moex_index"), "coef": 1.6},
            {"asset_name": _pn("bpif_esg_ru"), "coef": 0.95},
            {"asset_name": _pn("intellect_ai"), "coef": 0.7},
        ],
        "winners": [
            {"asset_name": _pn("bpif_ru_bonds"), "coef": 0.55},
            {"asset_name": _pn("bpif_liquidity"), "coef": 0.22},
            {"asset_name": _pn("gold_oms"), "coef": 0.1},
        ],
        "explanation": (
            "При падении рынка проседают индексные и рисковые фонды, а облигационные БПИФ, "
            "ликвидность и защитные активы обычно теряют в цене меньше."
        ),
    },
    "currency_shock": {
        "losers": [
            {"asset_name": _pn("bpif_ru_bonds"), "coef": 0.9},
            {"asset_name": _pn("deposit_vtb"), "coef": 0.6},
            {"asset_name": _pn("account_vtb"), "coef": 0.45},
        ],
        "winners": [
            {"asset_name": _pn("gold_oms"), "coef": 0.35},
            {"asset_name": _pn("bpif_gold_exchange"), "coef": 0.28},
            {"asset_name": _pn("platinum_oms"), "coef": 0.1},
        ],
        "explanation": (
            "Ослабление рубля перераспределяет эффект между рублёвыми накоплениями и инструментами "
            "с защитной/валютной компонентой, включая драгметаллы на ОМС."
        ),
    },
}
