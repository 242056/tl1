"""Стабилизация паспорта: эталонные тексты и метрики поверх ответа LLM."""
from __future__ import annotations

from typing import Any, Dict, List

from .metric_format import normalize_metric_values
from .metric_values import is_concrete_metric
from .product_metrics import metrics_keys
from .product_reference import is_stable_kind, reference_profile, resolve_product_id
from .products import product_by_id, product_by_name


def _resolve_metric(
    key: str,
    official: Dict[str, Any],
    llm: Dict[str, Any],
    reference: Dict[str, Any],
) -> Any:
    for bucket in (official, llm, reference):
        val = bucket.get(key)
        if is_concrete_metric(val):
            return val
    for bucket in (official, llm, reference):
        val = bucket.get(key)
        if val is not None and str(val).strip():
            return val
    return None


def stabilize_passport(
    *,
    asset_id: str,
    asset_type: str,
    raw: Dict[str, Any],
    official_metrics: Dict[str, Any],
    merged_metrics: Dict[str, Any],
    summary: str,
    positive_factors: List[str],
    negative_factors: List[str],
) -> Dict[str, Any]:
    product = product_by_name(asset_id) or product_by_id(asset_id)
    product_id = resolve_product_id(asset_id, product)
    profile = reference_profile(product_id, asset_type)
    ref_metrics = profile.get("metrics") or {}

    metrics: Dict[str, Any] = {}
    for key in metrics_keys(asset_type):
        metrics[key] = _resolve_metric(key, official_metrics, merged_metrics, ref_metrics)

    metrics = normalize_metric_values(metrics, asset_type)

    asset_name = (product or {}).get("productName") or raw.get("asset_name") or asset_id
    ticker = raw.get("ticker")
    if ticker is not None and str(ticker).strip().lower() in {"", "нет данных", "unknown", "n/a", "-"}:
        ticker = None

    if not is_stable_kind(asset_type):
        return {
            "asset_name": asset_name,
            "ticker": ticker,
            "summary": summary,
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "key_metrics": metrics,
        }

    stable_summary = profile.get("summary") or summary
    template_pos = profile.get("positive_factors") or []
    template_neg = profile.get("negative_factors") or []
    stable_pos = template_pos if template_pos else positive_factors
    stable_neg = template_neg if template_neg else negative_factors

    return {
        "asset_name": asset_name,
        "ticker": ticker,
        "summary": stable_summary or summary,
        "positive_factors": stable_pos,
        "negative_factors": stable_neg,
        "key_metrics": metrics,
    }
