"""Эталонные профили продуктов — стабильные метрики и формулировки для MVP."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Категории, где LLM даёт нестабильный текст/цифры — фиксируем эталоном.
STABLE_KINDS = frozenset({"iszh", "nszh", "precious_metal", "deposit", "account", "pds"})

KindTemplate = Dict[str, Any]
ProductProfile = Dict[str, Any]

_KIND_DEFAULTS: Dict[str, KindTemplate] = {
    "iszh": {
        "summary": (
            "ИСЖ совмещает страховую защиту и инвестиционную часть; итог зависит от условий договора и срока."
        ),
        "positive_factors": [
            "Страховое покрытие по программе договора",
            "Налоговый вычет при соблюдении срока удержания",
            "Дисциплина долгосрочных накоплений",
        ],
        "negative_factors": [
            "Штрафы и потери при досрочном расторжении",
            "Инвестиционная часть без полной гарантии дохода",
            "Низкая ликвидность до окончания срока",
        ],
    },
    "nszh": {
        "summary": (
            "НСЖ ориентирован на защиту и накопление; возврат средств привязан к сроку и условиям полиса."
        ),
        "positive_factors": [
            "Страховая защита жизни и здоровья по полису",
            "Предсказуемый горизонт накоплений",
            "Возможность налогового вычета по правилам программы",
        ],
        "negative_factors": [
            "Ограниченная гибкость при досрочном выходе",
            "Доходность ниже рисковых активов",
            "Условия выплат зависят от выбранного пакета рисков",
        ],
    },
    "precious_metal": {
        "summary": (
            "Драгметалл в ВТБ — инструмент защиты от инфляции; цена привязана к рыночным котировкам."
        ),
        "positive_factors": [
            "Защитный актив при неопределённости на рынках",
            "Физический актив с ограниченным предложением",
            "Доступ через ОМС и слитки в линейке ВТБ",
        ],
        "negative_factors": [
            "Колебания котировок металла на бирже",
            "Спред между покупкой и продажей",
            "Комиссии хранения и стоимость обращения",
        ],
    },
    "deposit": {
        "summary": "Вклад фиксирует ставку и срок; доход определяется условиями договора банка.",
        "positive_factors": [
            "Предсказуемый процентный доход",
            "Страхование вкладов в установленных лимитах",
            "Простая структура без рыночной волатильности",
        ],
        "negative_factors": [
            "Ограничения на снятие до окончания срока",
            "Ставка может отставать от инфляции",
            "Штрафы при досрочном расторжении",
        ],
    },
    "account": {
        "summary": "Накопительный счёт сочетает доступ к деньгам и начисление процентов на остаток.",
        "positive_factors": [
            "Свободное пополнение и снятие средств",
            "Ежедневное или регулярное начисление процентов",
            "Низкий порог входа",
        ],
        "negative_factors": [
            "Ставка может изменяться банком",
            "Доходность обычно ниже срочных вкладов",
            "Нет гарантии сохранения ставки надолго",
        ],
    },
    "pds": {
        "summary": "ПДС — долгосрочная программа с господдержкой; выгода зависит от срока участия.",
        "positive_factors": [
            "Государственное софинансирование в рамках программы",
            "Налоговые льготы при соблюдении условий",
            "Дисциплина пенсионных накоплений",
        ],
        "negative_factors": [
            "Деньги заморожены до наступления условий выхода",
            "Штрафы при досрочном прекращении участия",
            "Итоговая доходность зависит от выбранного портфеля",
        ],
    },
}

# productId → дополнения к шаблону kind (метрики и тексты).
_PRODUCT_PROFILES: Dict[str, ProductProfile] = {
    "iszh_basis": {
        "metrics": {
            "guaranteed_return": "гарантируется по правилам программы",
            "expected_return": "участие в доходе эмитента",
            "contract_term": "от 5 лет",
            "insurance_amount": "по условиям договора",
            "fees": "включены в структуру продукта",
        },
        "summary": "ИСЖ «Базис Актив 2.0» сочетает гарантию и участие в доходе; результат зависит от срока.",
    },
    "iszh_driver": {
        "metrics": {
            "guaranteed_return": "фиксируется в договоре",
            "expected_return": "ограничена условиями программы",
            "contract_term": "от 3 лет",
            "insurance_amount": "по выбранной программе",
            "fees": "по тарифам страховщика",
        },
        "summary": "ИСЖ «Драйвер Гарантия» делает акцент на гарантированной части при страховой защите.",
    },
    "iszh_maximum": {
        "metrics": {
            "guaranteed_return": "минимальный уровень в договоре",
            "expected_return": "повышенное участие в доходе",
            "contract_term": "от 5 лет",
            "insurance_amount": "по условиям договора",
            "fees": "по тарифам программы",
        },
        "summary": "ИСЖ «Максимум» ориентирован на более высокое участие в доходе при сохранении защиты.",
    },
    "iszh_fixed_income": {
        "metrics": {
            "guaranteed_return": "фиксированная ставка в договоре",
            "expected_return": "не применяется",
            "contract_term": "от 3 лет",
            "insurance_amount": "по условиям договора",
            "fees": "включены в продукт",
        },
        "summary": "ИСЖ «Фиксированный доход» ориентирован на заранее определённые условия доходности.",
    },
    "nszh_future": {
        "metrics": {
            "insurance_amount": "по выбранному пакету рисков",
            "maturity_return": "по правилам программы накопления",
            "insurance_term": "от 5 лет",
            "contribution": "регулярный или единовременный",
            "risk_coverage": "жизнь, инвалидность, критические заболевания",
        },
        "summary": "НСЖ «Забота о будущем» нацелен на накопление к целевой дате при страховой защите.",
    },
    "nszh_family": {
        "metrics": {
            "insurance_amount": "семейный пакет покрытия",
            "maturity_return": "по условиям программы",
            "insurance_term": "от 5 лет",
            "contribution": "гибкий график взносов",
            "risk_coverage": "жизнь и здоровье застрахованных",
        },
        "summary": "НСЖ «Забота о семье» объединяет защиту близких и накопительную составляющую.",
    },
    "nszh_ultra": {
        "metrics": {
            "insurance_amount": "расширенное покрытие рисков",
            "maturity_return": "по правилам продукта",
            "insurance_term": "от 3 лет",
            "contribution": "по выбранному тарифу",
            "risk_coverage": "расширенный набор рисков",
        },
        "summary": "НСЖ «На всякий случай Ультра» усиливает страховое покрытие при накоплении.",
    },
    "gold_oms": {
        "metrics": {
            "metal_price": "по курсу ЦБ РФ на дату операции",
            "return_period": "зависит от динамики золота",
            "spread": "банковский спред покупка/продажа",
            "storage_fee": "комиссия за ведение ОМС",
            "liquidity": "medium",
        },
        "summary": "Золото на ОМС — обезличенный металл на счёте; цена следует котировкам ЦБ.",
    },
    "gold_coins": {
        "metrics": {
            "metal_price": "цена монеты по прайсу банка",
            "return_period": "зависит от рынка золота",
            "spread": "спред к биржевой котировке",
            "storage_fee": "не применяется при выдаче",
            "liquidity": "medium",
        },
        "summary": "Инвестиционные монеты — физическое золото с премией к спот-цене металла.",
    },
    "gold_bars": {
        "metrics": {
            "metal_price": "по весу и котировке металла",
            "return_period": "зависит от рынка золота",
            "spread": "спред покупка/продажа",
            "storage_fee": "опционально в хранилище банка",
            "liquidity": "medium",
        },
        "summary": "Слитки — прямое владение металлом; ликвидность ниже биржевых инструментов.",
    },
    "palladium_oms": {
        "metrics": {
            "metal_price": "по курсу ЦБ РФ на дату операции",
            "return_period": "зависит от динамики палладия",
            "spread": "банковский спред покупка/продажа",
            "storage_fee": "комиссия за ведение ОМС",
            "liquidity": "low",
        },
        "summary": "Палладий на ОМС — нишевый драгметалл с повышенной волатильностью спроса.",
    },
    "platinum_oms": {
        "metrics": {
            "metal_price": "по курсу ЦБ РФ на дату операции",
            "return_period": "зависит от динамики платины",
            "spread": "банковский спред покупка/продажа",
            "storage_fee": "комиссия за ведение ОМС",
            "liquidity": "low",
        },
        "summary": "Платина на ОМС — драгметалл промышленного спроса с умеренной ликвидностью.",
    },
    "deposit_vtb": {
        "metrics": {
            "interest_rate": "по тарифам на дату открытия",
            "min_amount": "от 10 000 ₽",
            "deposit_term": "от 2 месяцев",
            "capitalization": "да",
            "flexibility": "пополнение по условиям тарифа",
        },
    },
    "account_vtb": {
        "metrics": {
            "interest_rate": "по действующей ставке банка",
            "min_amount": "от 0 ₽",
            "account_term": "бессрочно",
            "capitalization": "да",
            "flexibility": "снятие и пополнение без ограничений",
        },
    },
    "pds": {
        "metrics": {
            "state_cofinancing": "до 36 000 ₽/год",
            "participation_term": "от 15 лет",
            "expected_return": "зависит от инвестиционного портфеля",
            "early_exit": "с потерей господдержки",
            "tax_benefit": "вычет 13% в пределах лимитов",
        },
    },
}


def reference_profile(product_id: str | None, kind: str) -> Dict[str, Any]:
    """Эталон summary, факторов и метрик для стабильного ответа."""
    k = (kind or "").strip().lower()
    base = dict(_KIND_DEFAULTS.get(k, {}))
    product = _PRODUCT_PROFILES.get(product_id or "", {})

    summary = product.get("summary") or base.get("summary") or ""
    pos = product.get("positive_factors") or base.get("positive_factors") or []
    neg = product.get("negative_factors") or base.get("negative_factors") or []
    metrics = dict(product.get("metrics") or {})

    return {
        "stable_kind": k in STABLE_KINDS,
        "summary": summary,
        "positive_factors": list(pos)[:3],
        "negative_factors": list(neg)[:3],
        "metrics": metrics,
    }


def is_stable_kind(kind: str) -> bool:
    return (kind or "").strip().lower() in STABLE_KINDS


def resolve_product_id(asset_id: str, product: Optional[Dict[str, str]]) -> str:
    if product and product.get("productId"):
        return str(product["productId"])
    return (asset_id or "").strip()
