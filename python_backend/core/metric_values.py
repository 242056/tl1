"""Проверка «конкретности» значений метрик."""
from __future__ import annotations

import re
from typing import Any

_VAGUE_PHRASES = (
    "по условиям",
    "по тарифам",
    "по правилам",
    "по выбран",
    "зависит от",
    "не применяется",
    "уточня",
    "варьиру",
    "может измен",
    "включены в",
    "по программе",
    "по договору",
    "гибкий",
    "опционально",
    "банковский спред",
    "комиссия за ведение",
)

_HAS_DIGIT_RE = re.compile(r"\d")


def is_concrete_metric(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return True
    if not isinstance(val, str):
        return False
    s = val.strip().lower()
    if not s or s in {"unknown", "нет данных", "н/д", "n/a", "-", "—", "null"}:
        return False
    if _HAS_DIGIT_RE.search(s):
        return True
    if s in {"low", "medium", "high", "да", "нет", "бессрочно"}:
        return True
    if any(p in s for p in _VAGUE_PHRASES):
        return False
    return len(s) >= 3
