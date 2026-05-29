"""Очистка текстов паспорта актива: ссылки [N], утечки метрик в факторы."""
from __future__ import annotations

import re
from typing import Any, List

# Perplexity / sonar: [1], [3][6], [1, 2]
_CITATION_MARKERS_RE = re.compile(r"\[\s*\d+(?:\s*[,;]\s*\d+)*\s*\]")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_HTTP_URL_RE = re.compile(r"https?://\S+", re.I)


def strip_citation_markers(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    cleaned = _CITATION_MARKERS_RE.sub("", text)
    cleaned = _HTTP_URL_RE.sub("", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    return cleaned.strip()


# Числа и типичные метрики — только в key_metrics, не в факторах.
_METRIC_LEAK_RE = re.compile(
    r"("
    r"доходност\w*|"
    r"рентабел\w*|"
    r"\bсча\b|"
    r"чист\w*\s+актив|"
    r"\bter\b|"
    r"комисси\w*|"
    r"\bальфа\b|"
    r"коэффициент\s+шарп|"
    r"\bшарп\b|"
    r"просадк|"
    r"дивиденд|"
    r"на\s*сча|"
    r"стоимост\w*\s+пая|"
    r"управляющ\w*\s+комисси|"
    r"\d+[,.]?\d*\s*%|"
    r"\d+\s*млрд|"
    r"\d+\s*млн|"
    r"\d+[,.]?\d*\s*₽"
    r")",
    re.I,
)

_NUMBER_RE = re.compile(r"\d+[,.]?\d*")


def is_metric_leak_in_factor(text: str) -> bool:
    return bool(_METRIC_LEAK_RE.search(text or ""))


def _redact_numbers(text: str) -> str:
    cleaned = _NUMBER_RE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;—-")
    return cleaned


def _qualitative_factor(text: str) -> str:
    line = strip_citation_markers((text or "").strip())
    if not line or is_metric_leak_in_factor(line):
        return ""
    line = _redact_numbers(line)
    if len(line) < 12 or is_metric_leak_in_factor(line):
        return ""
    return line


def sanitize_factors(items: List[Any]) -> List[str]:
    out: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        line = _qualitative_factor(item)
        if line:
            out.append(line)
    return out
