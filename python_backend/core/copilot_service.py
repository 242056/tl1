"""ИИ-черновик / Co-pilot — ручная коррекция предложенного портфеля (заглушки)."""
from __future__ import annotations

import asyncio
import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .clients import VtbModelClient
from .copilot_metrics import compute_portfolio_metrics
from .products import PROPOSED_PORTFOLIOS, _alloc, product_by_id

_DATA_PATH = Path(__file__).resolve().parent / "data" / "copilot_scenarios.json"
_SESSIONS_PATH = Path(__file__).resolve().parent / "data" / "copilot_sessions.json"
_MAX_ASSETS = 5


def _load_scenarios() -> Dict[str, Any]:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


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


def _cap_products(products: List[Dict[str, Any]], limit: int = _MAX_ASSETS) -> List[Dict[str, Any]]:
    if len(products) <= limit:
        return products
    trimmed = sorted(products, key=lambda p: float(p.get("weight", 0)), reverse=True)[:limit]
    return _normalize_weights(trimmed)


class CopilotService:
    def __init__(self, vtb_model: VtbModelClient) -> None:
        self.vtb_model = vtb_model
        self.scenarios = _load_scenarios()
        self.sessions: Dict[str, Dict[str, Any]] = self._load_sessions_from_disk()

    def _load_sessions_from_disk(self) -> Dict[str, Dict[str, Any]]:
        if not _SESSIONS_PATH.exists():
            return {}
        try:
            with _SESSIONS_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            return dict(data.get("sessions") or {})
        except (OSError, json.JSONDecodeError):
            return {}

    def _persist_sessions(self) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sessions": {
                sid: {k: v for k, v in session.items() if not str(k).startswith("_")}
                for sid, session in self.sessions.items()
                if session.get("original_draft")
            },
        }
        _SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _SESSIONS_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _save_session(self, session_id: str) -> None:
        self._persist_sessions()

    def list_scenarios(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": s["id"],
                "title": s["title"],
                "description": s["description"],
                "risk_profile": s["risk_profile"],
                "intro_message": s.get("intro_message", ""),
            }
            for s in self.scenarios.get("draft_scenarios", [])
        ]

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {}
        return self.sessions[session_id]

    def _product_amount(self, placement: int, weight: float) -> int:
        return int(round(placement * weight))

    def _attach_amounts(
        self,
        products: List[Dict[str, Any]],
        placement: int,
    ) -> List[Dict[str, Any]]:
        rows = []
        for p in products:
            w = float(p.get("weight", 0))
            rows.append({**p, "amount": self._product_amount(placement, w)})
        return rows

    def _find_scenario(self, scenario_id: Optional[str]) -> Optional[Dict[str, Any]]:
        drafts = self.scenarios.get("draft_scenarios", [])
        if not scenario_id:
            return drafts[0] if drafts else None
        for s in drafts:
            if s["id"] == scenario_id:
                return s
        return None

    async def _build_draft_portfolio(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        custom = scenario.get("custom_weights")
        if custom:
            variant_idx = scenario.get("portfolio_variant", 0)
            base = PROPOSED_PORTFOLIOS[variant_idx % len(PROPOSED_PORTFOLIOS)]
            placement = base["placementAmount"]
            products = _alloc(placement, [(pid, w) for pid, w in custom])
            return {
                **{k: v for k, v in base.items() if k != "products"},
                "portfolioId": f"copilot_{scenario['id']}",
                "portfolioName": scenario["title"],
                "riskProfile": scenario["risk_profile"],
                "summary": {"description": scenario["description"]},
                "products": products,
            }
        variant = scenario.get("portfolio_variant", 0)
        generated = await self.vtb_model.generate_portfolio(variant)
        p = dict(generated["data"])
        p["portfolioName"] = scenario["title"]
        p["riskProfile"] = scenario["risk_profile"]
        p["summary"] = {"description": scenario["description"]}
        p["portfolioId"] = f"copilot_{scenario['id']}"
        return p

    def _asset_stub(self, product_id: str) -> Dict[str, float]:
        stubs = self.scenarios.get("asset_stubs", {})
        default = {"expected_return": 0.12, "volatility": 0.1, "risk_score": 3.0, "category": "mixed"}
        return {**default, **stubs.get(product_id, {})}

    def _compute_metrics(
        self,
        products: List[Dict[str, Any]],
        baseline: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        stubs = self.scenarios.get("asset_stubs", {})
        return compute_portfolio_metrics(products, baseline, stubs)

    def _metric_deltas(
        self,
        current: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        keys = ["expected_return", "volatility", "sharpe_ratio", "risk_score", "diversification"]
        out: Dict[str, Dict[str, Any]] = {}
        for k in keys:
            cur = float(current.get(k, 0))
            base = float(baseline.get(k, 0))
            delta = _round4(cur - base)
            if k in {"volatility", "risk_score"}:
                direction = "down" if delta < -0.001 else ("up" if delta > 0.001 else "same")
                sentiment = "good" if delta < -0.001 else ("bad" if delta > 0.001 else "neutral")
            elif k == "diversification":
                direction = "up" if delta > 0.001 else ("down" if delta < -0.001 else "same")
                sentiment = "good" if delta > 0.001 else ("bad" if delta < -0.001 else "neutral")
            else:
                direction = "up" if delta > 0.001 else ("down" if delta < -0.001 else "same")
                sentiment = "good" if delta > 0.001 else ("bad" if delta < -0.001 else "neutral")
            out[k] = {"value": current.get(k), "delta": delta, "direction": direction, "sentiment": sentiment}
        return out

    def _weight_deltas(
        self,
        current: List[Dict[str, Any]],
        original: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        orig_map = {p["productId"]: float(p.get("weight", 0)) for p in original}
        orig_amount = {p["productId"]: int(p.get("amount", 0)) for p in original}
        rows = []
        for p in current:
            w = float(p.get("weight", 0))
            base = orig_map.get(p["productId"], 0.0)
            amt = int(p.get("amount", 0))
            base_amt = orig_amount.get(p["productId"], amt)
            rows.append(
                {
                    **p,
                    "original_weight": _round4(base),
                    "weight_delta": _round4(w - base),
                    "original_amount": base_amt,
                    "amount_delta": amt - base_amt,
                }
            )
        return rows

    def _check_warnings(
        self,
        metrics: Dict[str, Any],
        baseline: Dict[str, Any],
        risk_profile: str,
        products: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        profiles = self.scenarios.get("risk_profiles", {})
        limits = profiles.get(risk_profile, profiles.get("medium", {}))
        msgs = self.scenarios.get("warnings", {})
        warnings: List[Dict[str, str]] = []

        if metrics["risk_score"] > limits.get("max_risk_score", 99):
            warnings.append({"code": "risk_above_profile", "level": "yellow", "message": msgs["risk_above_profile"]})
        if metrics["max_single_weight"] > limits.get("max_single_weight", 1.0):
            warnings.append({"code": "concentration", "level": "yellow", "message": msgs["concentration"]})
        vol_spike = metrics["volatility"] - baseline["volatility"]
        if vol_spike > limits.get("volatility_spike_threshold", 0.05):
            warnings.append({"code": "volatility_spike", "level": "yellow", "message": msgs["volatility_spike"]})
        if metrics["diversification"] < baseline["diversification"] - 0.05:
            warnings.append({"code": "diversification_drop", "level": "red", "message": msgs["diversification_drop"]})
        if metrics["expected_return"] < baseline["expected_return"] - 0.015:
            warnings.append({"code": "return_drop", "level": "red", "message": msgs["return_drop"]})
        return warnings

    def _check_rate_limit(self, session: Dict[str, Any]) -> Optional[str]:
        cfg = self.scenarios.get("rate_limit", {})
        now = time.time()
        window = session.setdefault("_rate_window", {"start": now, "count": 0})
        if now - window["start"] > 60:
            window["start"] = now
            window["count"] = 0
        window["count"] += 1
        if window["count"] > cfg.get("max_requests_per_minute", 30):
            return cfg.get("message", "Лимит на запросы превышен.")
        return None

    async def init_session(
        self,
        session_id: str,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        scenario = self._find_scenario(scenario_id)
        if not scenario:
            return {
                "success": False,
                "error_code": "unknown_scenario",
                "message": self.scenarios["errors"]["unknown_scenario"],
            }

        draft = await self._build_draft_portfolio(scenario)
        placement = int(draft["placementAmount"])
        products = _cap_products(deepcopy(draft["products"]))
        products = self._attach_amounts(products, placement)
        draft["products"] = products
        baseline_metrics = self._compute_metrics(products)

        session = self._get_session(session_id)
        session.clear()
        session.update(
            {
                "scenario_id": scenario["id"],
                "scenario_title": scenario["title"],
                "risk_profile": scenario["risk_profile"],
                "original_draft": deepcopy(draft),
                "current_portfolio": draft,
                "current_products": products,
                "baseline_metrics": baseline_metrics,
                "last_metrics": baseline_metrics,
                "recalc_history": [],
                "last_change": None,
                "confirmed": False,
                "final_portfolio": None,
                "last_success_at": datetime.now(timezone.utc).isoformat(),
                "_rate_window": {"start": time.time(), "count": 0},
            }
        )
        self._save_session(session_id)

        profile_label = self.scenarios["risk_profiles"][scenario["risk_profile"]]["label"]
        return {
            "success": True,
            "mode": "copilot",
            "intent": "COPILOT",
            "scenario": {
                "id": scenario["id"],
                "title": scenario["title"],
                "description": scenario["description"],
                "risk_profile": scenario["risk_profile"],
                "risk_profile_label": profile_label,
            },
            "reply": scenario.get("intro_message", "ИИ-черновик готов к корректировке."),
            "draft": draft,
            "metrics": baseline_metrics,
            "metric_deltas": self._metric_deltas(baseline_metrics, baseline_metrics),
            "products": self._weight_deltas(products, products),
            "warnings": [],
            "actions": [],
            "context": self._context_payload(session),
        }

    async def recalculate(
        self,
        session_id: str,
        weights: List[Dict[str, Any]],
        *,
        simulate_delay: bool = True,
    ) -> Dict[str, Any]:
        if session_id not in self.sessions or not self.sessions[session_id].get("original_draft"):
            loaded = self._load_sessions_from_disk()
            if session_id in loaded:
                self.sessions[session_id] = loaded[session_id]
        session = self._get_session(session_id)
        if not session.get("original_draft"):
            return {
                "success": False,
                "error_code": "session_empty",
                "message": self.scenarios["errors"]["session_empty"],
            }

        if len(weights) > _MAX_ASSETS:
            return {
                "success": False,
                "error_code": "max_assets",
                "message": self.scenarios["errors"]["max_assets"],
            }

        orig_products = session["original_draft"]["products"]
        orig_map = {p["productId"]: p for p in orig_products}
        new_products: List[Dict[str, Any]] = []
        placement = session["current_portfolio"]["placementAmount"]
        for row in weights:
            pid = row["productId"]
            meta = product_by_id(pid) or orig_map.get(pid)
            if not meta:
                continue
            w = _round4(float(row["weight"]))
            base = orig_map.get(pid, {})
            new_products.append(
                {
                    "productId": pid,
                    "productName": base.get("productName") or meta.get("productName", pid),
                    "category": base.get("category") or meta.get("category", ""),
                    "kind": base.get("kind") or meta.get("kind", ""),
                    "weight": w,
                    "amount": self._product_amount(placement, w),
                }
            )

        new_products = _normalize_weights(new_products)

        if simulate_delay:
            await asyncio.sleep(0.35)

        result = await self.vtb_model.recalculate_portfolio(
            session["scenario_id"],
            new_products,
            risk_profile=session["risk_profile"],
            baseline_products=orig_products,
        )
        if not result.get("success"):
            return {
                "success": False,
                "error_code": result.get("error_code", "model_error"),
                "message": self.scenarios["errors"].get(
                    result.get("error_code", "model_error"),
                    self.scenarios["errors"]["model_error"],
                ),
                "metrics": session.get("last_metrics"),
                "products": self._weight_deltas(session["current_products"], orig_products),
                "warnings": session.get("last_warnings", []),
                "context": self._context_payload(session),
            }

        metrics = result["data"]["metrics"]
        baseline = session["baseline_metrics"]
        warnings = self._check_warnings(metrics, baseline, session["risk_profile"], new_products)

        portfolio = deepcopy(session["current_portfolio"])
        portfolio["products"] = new_products
        session["current_products"] = new_products
        session["current_portfolio"] = portfolio
        session["last_metrics"] = metrics
        session["last_warnings"] = warnings
        session["last_success_at"] = datetime.now(timezone.utc).isoformat()
        change_entry = {
            "at": session["last_success_at"],
            "weights": [{p["productId"]: p["weight"]} for p in new_products],
            "metrics": metrics,
            "warnings_count": len(warnings),
        }
        session["last_change"] = change_entry
        history: List[Dict[str, Any]] = session.setdefault("recalc_history", [])
        history.append(change_entry)
        session["recalc_history"] = history[-20:]
        self._save_session(session_id)

        return {
            "success": True,
            "mode": "copilot",
            "intent": "COPILOT",
            "metrics": metrics,
            "metric_deltas": self._metric_deltas(metrics, baseline),
            "products": self._weight_deltas(new_products, orig_products),
            "warnings": warnings,
            "recalc_ms": result["data"].get("recalc_ms", 350),
            "context": self._context_payload(session),
        }

    async def apply_preset(self, session_id: str, preset_id: str) -> Dict[str, Any]:
        session = self._get_session(session_id)
        if not session.get("current_products"):
            return {"success": False, "message": self.scenarios["errors"]["session_empty"]}

        preset = next((p for p in self.scenarios.get("quick_presets", []) if p["id"] == preset_id), None)
        if not preset:
            return {"success": False, "message": "Пресет не найден"}

        products = deepcopy(session["current_products"])
        by_id = {p["productId"]: p for p in products}

        if preset.get("mode") == "equal_weights":
            n = len(products)
            even = _round4(1.0 / n)
            weights = []
            for i, p in enumerate(products):
                w = even if i < n - 1 else _round4(1.0 - even * (n - 1))
                weights.append({"productId": p["productId"], "weight": w})
            return await self.recalculate(session_id, weights)

        if preset.get("remove_product"):
            pid = preset["remove_product"]
            removed_w = float(by_id.pop(pid, {}).get("weight", 0))
            targets = preset.get("redistribute_to", [])
            if removed_w > 0 and targets:
                share = _round4(removed_w / len(targets))
                for tid in targets:
                    if tid in by_id:
                        by_id[tid]["weight"] = _round4(float(by_id[tid]["weight"]) + share)
            products = list(by_id.values())

        if preset.get("add_product"):
            pid = preset["add_product"]
            if pid not in by_id and len(products) >= _MAX_ASSETS:
                return {"success": False, "message": self.scenarios["errors"]["max_assets"]}
            if pid not in by_id:
                meta = product_by_id(pid)
                if meta:
                    placement = session["current_portfolio"]["placementAmount"]
                    init_w = float(preset.get("initial_weight", 0.1))
                    products.append(
                        {
                            **meta,
                            "weight": init_w,
                            "amount": int(round(placement * init_w)),
                        }
                    )
                    by_id = {p["productId"]: p for p in products}
                    to_reduce = preset.get("reduce_from", [])
                    if to_reduce:
                        share = _round4(init_w / len(to_reduce))
                        for rid in to_reduce:
                            if rid in by_id:
                                by_id[rid]["weight"] = max(0.0, _round4(float(by_id[rid]["weight"]) - share))

        adjustments = preset.get("adjustments", {})
        reduce_from = preset.get("reduce_from", [])
        total_add = sum(float(v) for v in adjustments.values())
        if adjustments:
            for pid, add in adjustments.items():
                if pid in by_id:
                    by_id[pid]["weight"] = _round4(float(by_id[pid]["weight"]) + float(add))
            if reduce_from and total_add > 0:
                share = _round4(total_add / len(reduce_from))
                for rid in reduce_from:
                    if rid in by_id:
                        by_id[rid]["weight"] = max(0.0, _round4(float(by_id[rid]["weight"]) - share))

        products = _normalize_weights(list(by_id.values()))
        weights = [{"productId": p["productId"], "weight": p["weight"]} for p in products]
        return await self.recalculate(session_id, weights)

    async def reset_to_original(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions or not self.sessions[session_id].get("original_draft"):
            loaded = self._load_sessions_from_disk()
            if session_id in loaded:
                self.sessions[session_id] = loaded[session_id]
        session = self._get_session(session_id)
        if not session.get("original_draft"):
            return {
                "success": False,
                "message": self.scenarios["errors"]["session_empty"],
            }
        if session.get("confirmed"):
            return {
                "success": False,
                "message": "Портфель уже оформлен — сброс недоступен",
            }
        orig = session["original_draft"]["products"]
        weights = [{"productId": p["productId"], "weight": float(p["weight"])} for p in orig]
        return await self.recalculate(session_id, weights)

    async def add_asset(self, session_id: str, product_id: str, weight: float = 0.05) -> Dict[str, Any]:
        session = self._get_session(session_id)
        if not session.get("current_products"):
            return {"success": False, "message": self.scenarios["errors"]["session_empty"]}
        products = deepcopy(session["current_products"])
        by_id = {p["productId"]: p for p in products}
        if product_id in by_id:
            return {"success": False, "message": "Актив уже в портфеле"}
        if len(products) >= _MAX_ASSETS:
            return {"success": False, "message": self.scenarios["errors"]["max_assets"]}
        meta = product_by_id(product_id)
        if not meta:
            return {"success": False, "message": "Продукт не найден во вселенной ВТБ"}
        placement = session["current_portfolio"]["placementAmount"]
        products.append({**meta, "weight": weight, "amount": int(round(placement * weight))})
        scale = _round4(1.0 - weight)
        for p in products[:-1]:
            p["weight"] = _round4(float(p["weight"]) * scale)
        products = _normalize_weights(products)
        weights = [{"productId": p["productId"], "weight": p["weight"]} for p in products]
        return await self.recalculate(session_id, weights)

    async def remove_asset(self, session_id: str, product_id: str) -> Dict[str, Any]:
        session = self._get_session(session_id)
        if not session.get("current_products"):
            return {"success": False, "message": self.scenarios["errors"]["session_empty"]}
        products = [p for p in session["current_products"] if p["productId"] != product_id]
        if len(products) == len(session["current_products"]):
            return {"success": False, "message": "Актив не найден в портфеле"}
        if not products:
            return {"success": False, "message": "Нельзя удалить все активы"}
        products = _normalize_weights(products)
        weights = [{"productId": p["productId"], "weight": p["weight"]} for p in products]
        return await self.recalculate(session_id, weights)

    async def confirm_purchase(self, session_id: str, confirmed: bool) -> Dict[str, Any]:
        session = self._get_session(session_id)
        if not session.get("current_portfolio"):
            return {"success": False, "message": self.scenarios["errors"]["session_empty"]}
        if not confirmed:
            return {
                "success": True,
                "mode": "copilot",
                "intent": "COPILOT",
                "reply": "Покупка отменена. Вы можете продолжить корректировку черновика.",
                "confirmed": False,
            }

        final = deepcopy(session["current_portfolio"])
        final["confirmedAt"] = datetime.now(timezone.utc).isoformat()
        final["userModified"] = True
        session["confirmed"] = True
        session["final_portfolio"] = final
        self._save_session(session_id)

        metrics = session["last_metrics"]
        warnings = session.get("last_warnings", [])
        baseline = session["baseline_metrics"]
        orig = session["original_draft"]["products"]
        products = self._weight_deltas(session["current_products"], orig)
        profile_label = self.scenarios["risk_profiles"][session["risk_profile"]]["label"]
        return {
            "success": True,
            "mode": "copilot",
            "intent": "COPILOT",
            "reply": "Заявка принята. Персональный менеджер свяжется с вами для оформления покупки.",
            "confirmed": True,
            "scenario": {
                "id": session["scenario_id"],
                "title": session["scenario_title"],
                "description": session.get("original_draft", {}).get("summary", {}).get("description", ""),
                "risk_profile": session["risk_profile"],
                "risk_profile_label": profile_label,
            },
            "draft": final,
            "metrics": metrics,
            "metric_deltas": self._metric_deltas(metrics, baseline),
            "products": products,
            "warnings": warnings,
            "confirmation": {
                "portfolio": final,
                "metrics": metrics,
                "warnings": warnings,
                "disclaimer": self.scenarios["disclaimer"],
                "products": products,
            },
            "context": self._context_payload(session),
        }

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions or not self.sessions[session_id].get("original_draft"):
            loaded = self._load_sessions_from_disk()
            if session_id in loaded:
                self.sessions[session_id] = loaded[session_id]
        session = self._get_session(session_id)
        if not session.get("original_draft"):
            return {"success": False, "message": self.scenarios["errors"]["session_empty"]}
        orig = session["original_draft"]["products"]
        metrics = session.get("last_metrics", session["baseline_metrics"])
        baseline = session["baseline_metrics"]
        portfolio = session.get("final_portfolio") if session.get("confirmed") else session["current_portfolio"]
        products_src = portfolio.get("products") or session["current_products"]
        profile_label = self.scenarios["risk_profiles"].get(session["risk_profile"], {}).get("label", session["risk_profile"])
        return {
            "success": True,
            "mode": "copilot",
            "scenario": {
                "id": session["scenario_id"],
                "title": session["scenario_title"],
                "risk_profile": session["risk_profile"],
                "risk_profile_label": profile_label,
            },
            "draft": portfolio,
            "original_draft": session["original_draft"],
            "metrics": metrics,
            "metric_deltas": self._metric_deltas(metrics, baseline),
            "products": self._weight_deltas(products_src, orig),
            "warnings": session.get("last_warnings", []),
            "confirmed": session.get("confirmed", False),
            "context": self._context_payload(session),
        }

    def _context_payload(self, session: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "scenario_id": session.get("scenario_id"),
            "risk_profile": session.get("risk_profile"),
            "has_original_draft": bool(session.get("original_draft")),
            "recalc_count": len(session.get("recalc_history", [])),
            "last_change_at": (session.get("last_change") or {}).get("at"),
            "confirmed": session.get("confirmed", False),
        }
