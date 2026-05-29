"""Схемы ключевых метрик по типу продукта (топ-5 на категорию)."""
from __future__ import annotations

from typing import Any, Dict, List

from .asset_text import strip_citation_markers

# key — поле в JSON; label — подпись в UI; hint — подсказка для LLM.
MetricSpec = Dict[str, str]

METRICS_BY_KIND: Dict[str, List[MetricSpec]] = {
    "opif": [
        {"key": "nav_per_share", "label": "Стоимость пая", "hint": "расчётная стоимость пая для покупки/погашения, ₽"},
        {"key": "price_change", "label": "Изменение цены", "hint": "рост/падение за день, 52 недели и год, %"},
        {"key": "nav_aum", "label": "СЧА", "hint": "чистая стоимость активов фонда, ₽"},
        {"key": "min_investment", "label": "Мин. сумма инвестиций", "hint": "порог входа для розничного инвестора, ₽"},
        {"key": "ter", "label": "TER (комиссии)", "hint": "совокупные расходы фонда на управление, %"},
    ],
    "zpif": [
        {"key": "market_price", "label": "Цена пая", "hint": "биржевая котировка или расчётная цена УК, ₽"},
        {"key": "dividend_yield_12m", "label": "Див. доходность (12 мес.)", "hint": "выплаты за 12 мес / стоимость пая, %"},
        {"key": "dividend_per_share", "label": "Дивиденд на пай", "hint": "абсолютная сумма последней выплаты, ₽"},
        {"key": "trading_volume", "label": "Объём торгов", "hint": "ликвидность в стакане за день или средний объём, ₽"},
        {"key": "fund_lifetime", "label": "Срок обращения", "hint": "дата формирования и плановая дата закрытия фонда"},
    ],
    "precious_metal": [
        {"key": "bid_price", "label": "Цена покупки (Bid)", "hint": "цена выкупа металла банком у клиента, ₽/г"},
        {"key": "ask_price", "label": "Цена продажи (Ask)", "hint": "цена продажи металла клиенту банком, ₽/г"},
        {"key": "bank_spread", "label": "Банковский спред", "hint": "разница Ask − Bid в ₽ или %"},
        {"key": "daily_range", "label": "Дневной диапазон", "hint": "High / Low за текущие торговые сутки"},
        {"key": "period_change_pct", "label": "Динамика за период", "hint": "изменение учётной цены за месяц или год, %"},
    ],
    "intellect": [
        {"key": "historical_return", "label": "Историческая доходность", "hint": "доходность с запуска или за последний год, %"},
        {"key": "min_subscription", "label": "Мин. сумма подключения", "hint": "порог входа для алгоритма, ₽"},
        {"key": "risk_profile", "label": "Профиль риска", "hint": "Низкий / Средний / Высокий"},
        {"key": "recommended_horizon", "label": "Рекомендуемый срок", "hint": "горизонт инвестирования в месяцах или годах"},
        {"key": "management_fee", "label": "Комиссия за управление", "hint": "management fee и/или success fee, %"},
    ],
    "iszh": [
        {"key": "participation_coef", "label": "Коэффициент участия (КУ)", "hint": "доля роста базового актива для клиента, %"},
        {"key": "benchmark_name", "label": "Базовый актив / индекс", "hint": "к какому индексу или активу привязана стратегия"},
        {"key": "contract_term", "label": "Срок договора", "hint": "фиксированный период программы (3, 5 лет и т.д.)"},
        {"key": "capital_guarantee", "label": "Гарантия капитала", "hint": "защитная часть, обычно 100%"},
        {"key": "income_fixation_period", "label": "Фиксация дохода", "hint": "шаг проверки базового актива: ежеквартально, ежегодно, в конце срока"},
    ],
    "nszh": [
        {"key": "maturity_payout", "label": "Выплата по дожитию", "hint": "гарантированная финальная выплата в конце срока, ₽"},
        {"key": "regular_contribution", "label": "Регулярный взнос", "hint": "сумма периодического платежа, ₽"},
        {"key": "program_term", "label": "Срок программы", "hint": "длительность договора (5–20+ лет)"},
        {"key": "covered_risks", "label": "Включённые риски", "hint": "набор застрахованных жизненных ситуаций"},
        {"key": "additional_income_ytd", "label": "ДИД за прошлый год", "hint": "доп. инвестиционный доход, начисленный СК, %"},
    ],
    "pds": [
        {"key": "cofinancing_threshold", "label": "Взнос для софинансирования", "hint": "сумма взносов для макс. субсидии (до 36 000 ₽/год)"},
        {"key": "tax_deduction", "label": "Налоговый вычет", "hint": "расчётный возврат НДФЛ: 13% или 15% от взносов"},
        {"key": "total_savings", "label": "Объём накоплений", "hint": "текущая сумма на счёте: взносы + софинансирование + доход"},
        {"key": "years_to_payout", "label": "Срок до выплаты", "hint": "лет до 15-летнего срока или пенсионного возраста"},
        {"key": "fund_investment_income", "label": "Инвест. доход фонда", "hint": "доходность НПФ, распределённая на счёт клиента, %"},
    ],
    "alternative": [
        {"key": "carat_weight", "label": "Вес (караты)", "hint": "масса драгоценного камня в каратах"},
        {"key": "color_clarity_grade", "label": "Цвет и чистота", "hint": "оценка по GIA или российской системе"},
        {"key": "list_price_index", "label": "Цена по прайс-листу", "hint": "базовая стоимость аналогичных камней на рынке, ₽"},
        {"key": "has_certificate", "label": "Сертификат", "hint": "Да / Нет — наличие паспорта геммологической лаборатории"},
        {"key": "buyback_discount", "label": "Buy-back дисконт", "hint": "потери при обратной продаже банку, %"},
    ],
    "bpif": [
        {"key": "market_price", "label": "Цена пая", "hint": "текущая рыночная котировка на бирже, ₽"},
        {"key": "daily_volume", "label": "Объём торгов за день", "hint": "сумма или количество паёв, проторгованных сегодня"},
        {"key": "return_1y", "label": "Доходность за год", "hint": "изменение цены пая за 12 месяцев, %"},
        {"key": "daily_range", "label": "Дневной диапазон", "hint": "High / Low колебания цены внутри сессии"},
        {"key": "isin", "label": "ISIN", "hint": "международный код фонда, например RU000A101NZ2"},
    ],
    "deposit": [
        {"key": "interest_rate", "label": "Ставка (% годовых)", "hint": "номинальная или эффективная ставка на баннере"},
        {"key": "placement_term", "label": "Срок размещения", "hint": "период в днях или месяцах фиксации условий"},
        {"key": "balance_limits", "label": "Мин. / макс. остаток", "hint": "лимиты сумм, на которые начисляется процент"},
        {"key": "interest_payout", "label": "Выплата процентов", "hint": "ежемесячно с капитализацией, на карту или в конце срока"},
        {"key": "deposit_flexibility", "label": "Пополнение и снятие", "hint": "условия движения средств без потери доходности"},
    ],
    "account": [
        {"key": "interest_rate", "label": "Ставка (% годовых)", "hint": "действующая ставка по накопительному счёту"},
        {"key": "placement_term", "label": "Срок размещения", "hint": "бессрочно или условия действия ставки"},
        {"key": "balance_limits", "label": "Мин. / макс. остаток", "hint": "лимиты для начисления процентов, ₽"},
        {"key": "interest_payout", "label": "Выплата процентов", "hint": "ежедневное/ежемесячное начисление, капитализация"},
        {"key": "deposit_flexibility", "label": "Пополнение и снятие", "hint": "свободное движение средств по счёту"},
    ],
    "default": [
        {"key": "primary_value", "label": "Ключевой показатель", "hint": "главная метрика продукта"},
        {"key": "secondary_value", "label": "Доп. показатель", "hint": "вторая по важности метрика"},
        {"key": "fees", "label": "Комиссии / издержки", "hint": "TER, спред, комиссии"},
        {"key": "period_change", "label": "Динамика за период", "hint": "изменение за фиксированный период"},
        {"key": "liquidity", "label": "Ликвидность", "hint": "объём торгов или условия выхода"},
    ],
}


def is_supported_asset_kind(kind: str) -> bool:
    k = (kind or "").strip().lower()
    return bool(k) and k in METRICS_BY_KIND and k != "default"


def metrics_spec_for_kind(kind: str) -> List[MetricSpec]:
    k = (kind or "").strip().lower()
    return METRICS_BY_KIND.get(k) or METRICS_BY_KIND["default"]


def metrics_labels_for_kind(kind: str) -> Dict[str, str]:
    return {m["key"]: m["label"] for m in metrics_spec_for_kind(kind)}


def metrics_keys(kind: str) -> List[str]:
    return [m["key"] for m in metrics_spec_for_kind(kind)]


def metrics_schema_for_prompt(kind: str) -> Dict[str, str]:
    return {m["key"]: m["hint"] for m in metrics_spec_for_kind(kind)}


def normalize_key_metrics(raw: Any, kind: str) -> Dict[str, Any]:
    spec = metrics_spec_for_kind(kind)
    source = raw if isinstance(raw, dict) else {}
    out: Dict[str, Any] = {}
    for m in spec:
        key = m["key"]
        val = source.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            out[key] = None
            continue
        if isinstance(val, (int, float)):
            out[key] = val
        elif isinstance(val, str):
            s = val.strip()
            if s.lower() in {
                "unknown",
                "нет данных",
                "нет данных.",
                "н/д",
                "н.д.",
                "n/a",
                "-",
                "—",
                "null",
            }:
                out[key] = None
            else:
                cleaned = strip_citation_markers(s)
                out[key] = cleaned if cleaned else None
        else:
            out[key] = val
    return out
