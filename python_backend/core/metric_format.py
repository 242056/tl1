"""Нормализация форматов key_metrics для единообразного UI."""
from __future__ import annotations

import re
from typing import Any, Dict

_LIQUIDITY_MAP = {
    "low": "low",
    "низкая": "low",
    "низк": "low",
    "medium": "medium",
    "средняя": "medium",
    "средн": "medium",
    "high": "high",
    "высокая": "high",
    "высок": "high",
}

_PERCENT_KEYS_RE = re.compile(
    r"return|yield|fee|rate|drawdown|ter|alpha|cofinancing|management_fee|guaranteed|expected|maturity",
    re.I,
)


def _normalize_liquidity(val: str) -> str:
    low = val.strip().lower()
    return _LIQUIDITY_MAP.get(low, val.strip())


def _fmt_pct_number(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _normalize_percent(val: str) -> str:
    s = val.strip().replace(",", ".")
    if s.endswith("%"):
        num = s[:-1].strip()
        try:
            return _fmt_pct_number(float(num))
        except ValueError:
            return val.strip()
    try:
        f = float(s)
        if abs(f) <= 1 and "." in s:
            return _fmt_pct_number(f * 100)
        return _fmt_pct_number(f)
    except ValueError:
        return val.strip()


def normalize_metric_values(metrics: Dict[str, Any], kind: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, val in metrics.items():
        if val is None:
            out[key] = None
            continue
        if isinstance(val, (int, float)):
            if _PERCENT_KEYS_RE.search(key):
                pct = val * 100 if abs(val) <= 1 else val
                out[key] = _fmt_pct_number(float(pct))
            else:
                out[key] = val
            continue
        if not isinstance(val, str):
            out[key] = val
            continue
        s = val.strip()
        if not s:
            out[key] = None
            continue
        if key == "liquidity":
            out[key] = _normalize_liquidity(s)
        elif _PERCENT_KEYS_RE.search(key) and re.search(r"[\d]", s):
            out[key] = _normalize_percent(s)
        else:
            out[key] = s
    return out
