import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

from .models import Intent, PortfolioKind, ScenarioType

# Явные запросы сценария — без одиночных «индекс/рубль/рынок» (они есть в названиях продуктов).
_SCENARIO_INTENT_RE = re.compile(
    r"^сценар|сценар\s|что если|"
    r"рост\s+став|падени\w*\s+индекс|индекс\w*\s+(?:упад|сниз|пад)|"
    r"(?:упад|сниз|обвал).*(?:индекс|рынок|мосбирж)|"
    r"(?:рубл|доллар|валют).*(?:ослаб|шок)|ослаб\w*\s+(?:рубл|доллар)",
    re.I,
)


def detect_intent(text: str) -> Intent:
    v = text.lower()
    if re.search(r"бэ?к[\s\-]?тест|бектест|истори|испытание временем", v):
        return "BACKTEST"
    if _SCENARIO_INTENT_RE.search(v):
        return "SCENARIO"
    return "UNKNOWN"


def extract_period_years(text: str):
    m = re.search(r"(\d+)\s*(?:лет|года|год)\b", text.lower())
    return int(m.group(1)) if m else None


def detect_scenario_type(text: str):
    v = text.lower()
    if re.search(r"ставк|ключев|цб", v):
        if re.search(r"упад|сниж|пониж|паден", v):
            return "unsupported_rate_drop"
        return "rate_hike"
    if re.search(r"индекс|рынок|обвал|падени", v):
        return "market_drop"
    if re.search(r"рубл|доллар|валют|ослаб|укреп", v):
        return "currency_shock"
    return None


def extract_scenario_value(text: str):
    lower = text.lower()
    pct = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:%|процент(?:а|ов)?)", lower)
    if pct:
        return float(pct.group(1).replace(",", "."))
    abs_val = re.search(r"\bдо\s*(\d+(?:[\.,]\d+)?)", lower)
    if abs_val:
        return float(abs_val.group(1).replace(",", "."))
    delta_val = re.search(r"\bна\s*(\d+(?:[\.,]\d+)?)", lower)
    if delta_val:
        return float(delta_val.group(1).replace(",", "."))
    return None


def extract_portfolio(text: str):
    v = text.lower()
    if re.search(r"текущ|current", v):
        return "current"
    if re.search(r"предлож|proposed", v):
        return "proposed"
    return None


def is_compare_portfolio_request(text: str) -> bool:
    v = text.lower()
    if re.search(r"сравн\w*.*портфел|портфел.*сравн", v):
        return True
    if re.search(r"друг\w*\s+портфел", v):
        return True
    if re.search(r"то же самое", v) and re.search(r"портфел|друг", v):
        return True
    if re.search(r"переключ\w*.*портфел|на друг\w*\s+портфел", v):
        return True
    if "с другим портфелем" in v or "с другой портфел" in v:
        return True
    if "сравнить с другим портфелем" in v:
        return True
    return False


def is_same_operation_other_portfolio(text: str) -> bool:
    v = text.lower()
    return bool(re.search(r"то же самое", v) and re.search(r"портфел|друг", v))


def flip_portfolio(portfolio_id: Optional[PortfolioKind]) -> PortfolioKind:
    if portfolio_id == "current":
        return "proposed"
    return "current"


def portfolio_label(portfolio_id: Optional[str]) -> str:
    if portfolio_id == "proposed":
        return "предложенный"
    return "текущий"


def portfolio_phrase(portfolio_id: Optional[str]) -> str:
    if portfolio_id == "proposed":
        return "На предложенном портфеле"
    return "На текущем портфеле"


def is_yes(text: str) -> bool:
    v = text.strip().lower()
    return v in {"да", "угу", "ок", "хорошо", "yes"} or "да, показать" in v or "да, 5 лет" in v


def is_other_period(text: str) -> bool:
    v = text.strip().lower()
    return "другой период" in v or "другой срок" in v


def years_word(n: int) -> str:
    n = abs(n) % 100
    n1 = n % 10
    if 11 <= n <= 19:
        return "лет"
    if n1 == 1:
        return "год"
    if 2 <= n1 <= 4:
        return "года"
    return "лет"


def is_valid_http_url(url: str) -> bool:
    try:
        p = urlparse(url.strip())
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def clean_public_url(url: str) -> str:
    p = urlparse(url.strip())
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))
