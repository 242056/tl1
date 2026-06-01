"""Расчёт метрик Co-pilot с учётом чувствительности продуктов."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCENARIOS_PATH = Path(__file__).resolve().parent / "data" / "copilot_scenarios.json"
_DEFAULT_STUB = {
    "expected_return": 0.12,
    "volatility": 0.1,
    "risk_score": 3.0,
    "metric_sensitivity": 1.0,
    "category": "mixed",
}


def _round4(v: float) -> float:
    return round(v, 4)


def _normalize_weights(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    total = sum(float(r.get("weight", 0)) for r in rows)
    if total <= 0:
        n = len(rows) or 1
        even = _round4(1.0 / n)
        out = []
        for i, r in enumerate(rows):
            w = even if i < len(rows) - 1 else _round4(1.0 - even * (len(rows) - 1))
            out.append({**r, "weight": w})
        return out
    return [{**r, "weight": _round4(float(r["weight"]) / total)} for r in rows]


def load_asset_stubs() -> Dict[str, Dict[str, Any]]:
    try:
        with _SCENARIOS_PATH.open(encoding="utf-8") as f:
            return json.load(f).get("asset_stubs", {})
    except OSError:
        return {}


def asset_stub(product_id: str, stubs: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    src = stubs if stubs is not None else load_asset_stubs()
    return {**_DEFAULT_STUB, **src.get(product_id, {})}


def effective_metric_weights(
    products: List[Dict[str, Any]],
    baseline: Optional[List[Dict[str, Any]]] = None,
    stubs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Усиление отклонения от ИИ-черновика по metric_sensitivity продукта."""
    if not baseline:
        return products
    base_map = {p["productId"]: float(p.get("weight", 0)) for p in baseline}
    eff: List[Dict[str, Any]] = []
    for p in products:
        pid = p["productId"]
        w = float(p.get("weight", 0))
        w0 = base_map.get(pid, w)
        sens = float(asset_stub(pid, stubs).get("metric_sensitivity", 1.0))
        w_eff = max(0.0, w0 + (w - w0) * sens)
        eff.append({**p, "weight": w_eff})
    return _normalize_weights(eff)


def compute_portfolio_metrics(
    products: List[Dict[str, Any]],
    baseline: Optional[List[Dict[str, Any]]] = None,
    stubs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    stub_map = stubs if stubs is not None else load_asset_stubs()
    metric_rows = effective_metric_weights(products, baseline, stub_map)
    exp = vol_sq = risk = 0.0
    categories: Dict[str, float] = {}
    for p in metric_rows:
        w = float(p.get("weight", 0))
        stub = asset_stub(p["productId"], stub_map)
        exp += w * float(stub["expected_return"])
        vol_sq += (w * float(stub["volatility"])) ** 2
        risk += w * float(stub["risk_score"])
        cat = str(stub.get("category", "mixed"))
        categories[cat] = categories.get(cat, 0.0) + w
    volatility = math.sqrt(vol_sq)
    sharpe = round(exp / volatility, 2) if volatility > 1e-9 else 0.0
    raw_weights = [float(p.get("weight", 0)) for p in products]
    hhi = sum(w * w for w in raw_weights)
    max_w = max(raw_weights) if raw_weights else 0.0
    return {
        "expected_return": _round4(exp),
        "volatility": _round4(volatility),
        "sharpe_ratio": sharpe,
        "risk_score": _round4(risk),
        "diversification": round(1.0 - hhi, 3),
        "max_single_weight": _round4(max_w),
        "category_mix": {k: _round4(v) for k, v in categories.items()},
    }
