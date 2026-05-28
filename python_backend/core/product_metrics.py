"""Схемы ключевых метрик по типу продукта (топ-5 на категорию)."""
from __future__ import annotations

from typing import Any, Dict, List

from .asset_text import strip_citation_markers

# key — поле в JSON; label — подпись в UI; hint — подсказка для LLM.
MetricSpec = Dict[str, str]

METRICS_BY_KIND: Dict[str, List[MetricSpec]] = {
    "bpif": [
        {"key": "return_1y", "label": "Доходность за 1 год", "hint": "годовая доходность в % или долях"},
        {"key": "return_3y", "label": "Доходность за 3 года", "hint": "доходность за 3 года в % или долях"},
        {"key": "nav_aum", "label": "СЧА", "hint": "стоимость чистых активов, ₽"},
        {"key": "ter_fee", "label": "Комиссия (TER)", "hint": "годовая комиссия управления, %"},
        {"key": "alpha", "label": "Коэффициент Альфа", "hint": "избыточная доходность к бенчмарку"},
    ],
    "precious_metal": [
        {"key": "metal_price", "label": "Цена за грамм/унцию", "hint": "текущая рыночная цена"},
        {"key": "return_period", "label": "Доходность за период", "hint": "изменение цены за 1/3/5 лет, %"},
        {"key": "spread", "label": "Спред (покупка/продажа)", "hint": "разница цен покупки и продажи"},
        {"key": "storage_fee", "label": "Комиссия хранения", "hint": "годовая плата за хранение ОМС/слитков, %"},
        {"key": "liquidity", "label": "Ликвидность", "hint": "low|medium|high|unknown или краткое описание"},
    ],
    "zpif": [
        {"key": "nav_per_share", "label": "Стоимость пая (НСА)", "hint": "текущая цена/стоимость пая, ₽"},
        {"key": "rental_yield", "label": "Рентная/дивидендная доходность", "hint": "годовая выплата, %"},
        {"key": "nav_aum", "label": "СЧА", "hint": "размер фонда, ₽"},
        {"key": "portfolio_objects", "label": "Объекты в портфеле", "hint": "число или краткое описание диверсификации"},
        {"key": "return_period", "label": "Доходность за 1/3 года", "hint": "историческая доходность, %"},
    ],
    "iszh": [
        {"key": "guaranteed_return", "label": "Гарантированная доходность", "hint": "минимальная гарантированная ставка, %"},
        {"key": "expected_return", "label": "Ожидаемая доходность", "hint": "прогноз, не гарантия, %"},
        {"key": "contract_term", "label": "Срок договора", "hint": "лет или формулировка"},
        {"key": "insurance_amount", "label": "Страховая сумма", "hint": "выплата при страховом случае"},
        {"key": "fees", "label": "Комиссии", "hint": "входная и за управление, %"},
    ],
    "nszh": [
        {"key": "insurance_amount", "label": "Страховая сумма", "hint": "выплата при смерти/травме"},
        {"key": "maturity_return", "label": "Возврат в конце срока", "hint": "% от внесённых средств"},
        {"key": "insurance_term", "label": "Срок страхования", "hint": "лет"},
        {"key": "contribution", "label": "Размер взноса", "hint": "единовременный или регулярный"},
        {"key": "risk_coverage", "label": "Покрытие рисков", "hint": "кратко: какие случаи включены"},
    ],
    "deposit": [
        {"key": "interest_rate", "label": "Ставка (% годовых)", "hint": "текущая процентная ставка"},
        {"key": "min_amount", "label": "Минимальная сумма", "hint": "порог входа, ₽"},
        {"key": "deposit_term", "label": "Срок вклада", "hint": "месяцы или формулировка"},
        {"key": "capitalization", "label": "Капитализация", "hint": "да/нет или описание"},
        {"key": "flexibility", "label": "Снятие и пополнение", "hint": "условия гибкости"},
    ],
    "account": [
        {"key": "interest_rate", "label": "Ставка (% годовых)", "hint": "текущая ставка по счёту"},
        {"key": "min_amount", "label": "Минимальная сумма", "hint": "порог входа, ₽"},
        {"key": "account_term", "label": "Условия по сроку", "hint": "бессрочно / условия"},
        {"key": "capitalization", "label": "Капитализация", "hint": "да/нет"},
        {"key": "flexibility", "label": "Снятие и пополнение", "hint": "условия гибкости"},
    ],
    "alternative": [
        {"key": "price_per_carat", "label": "Цена за карат", "hint": "зависит от качества"},
        {"key": "certification_4c", "label": "4C (огранка, цвет, чистота, вес)", "hint": "сертификация"},
        {"key": "return_period", "label": "Доходность за период", "hint": "исторический рост, %"},
        {"key": "spread", "label": "Спред (покупка/продажа)", "hint": "разница цен"},
        {"key": "liquidity", "label": "Ликвидность", "hint": "low|medium|high|unknown или описание"},
    ],
    "intellect": [
        {"key": "return_period", "label": "Доходность за 1/3 года", "hint": "историческая, %"},
        {"key": "risk_level", "label": "Уровень риска", "hint": "консервативный/умеренный/агрессивный"},
        {"key": "portfolio_mix", "label": "Состав портфеля", "hint": "доли акций/облигаций/золота"},
        {"key": "max_drawdown", "label": "Макс. просадка", "hint": "%"},
        {"key": "sharpe_ratio", "label": "Коэффициент Шарпа", "hint": "число"},
    ],
    "opif": [
        {"key": "nav_per_share", "label": "Стоимость пая (НСА)", "hint": "₽"},
        {"key": "return_period", "label": "Доходность за 1/3 года", "hint": "%"},
        {"key": "nav_aum", "label": "СЧА", "hint": "объём активов, ₽"},
        {"key": "management_fee", "label": "Комиссия управления", "hint": "%"},
        {"key": "portfolio_structure", "label": "Структура портфеля", "hint": "облигации/акции/деньги"},
    ],
    "pds": [
        {"key": "state_cofinancing", "label": "Госсофинансирование", "hint": "до 36 000 ₽/год или %"},
        {"key": "participation_term", "label": "Срок участия", "hint": "лет до выхода"},
        {"key": "expected_return", "label": "Ожидаемая доходность", "hint": "прогноз, %"},
        {"key": "early_exit", "label": "Досрочный выход", "hint": "условия и штрафы"},
        {"key": "tax_benefit", "label": "Налоговые льготы", "hint": "вычет 13% и лимиты"},
    ],
    "default": [
        {"key": "return_period", "label": "Доходность за период", "hint": "1/3/5 лет, %"},
        {"key": "size_or_value", "label": "Размер / стоимость", "hint": "СЧА, пай, цена актива"},
        {"key": "fees", "label": "Комиссии", "hint": "TER, входная, управление, хранение"},
        {"key": "risk_volatility", "label": "Риск / волатильность", "hint": "просадка, альфа, шарп"},
        {"key": "liquidity", "label": "Ликвидность", "hint": "объём торгов, скорость продажи"},
    ],
}


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
