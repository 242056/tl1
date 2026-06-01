import math
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import httpx

TimeoutSetting = Union[float, httpx.Timeout]

from .products import CURRENT_PORTFOLIO, PROPOSED_PORTFOLIOS, SCENARIO_CONFIGS


class ExternalApiClient:
    def __init__(self) -> None:
        self.timeout = float(os.getenv("HTTP_TIMEOUT_SEC", "60"))

    async def post(
        self,
        url: str,
        payload: Dict[str, Any],
        token: Optional[str] = None,
        timeout: Optional[TimeoutSetting] = None,
    ) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req_timeout = timeout if timeout is not None else self.timeout
        async with httpx.AsyncClient(timeout=req_timeout) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()

    async def get(
        self,
        url: str,
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        headers: Dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if extra_headers:
            headers.update(extra_headers)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            try:
                return r.json()
            except ValueError:
                return {
                    "url": str(r.url),
                    "status_code": r.status_code,
                    "content_type": r.headers.get("content-type", ""),
                    "raw_text": r.text[:12000],
                }


class VtbModelClient:
    def __init__(self) -> None:
        self.portfolios = PROPOSED_PORTFOLIOS
        self.current_portfolio = dict(CURRENT_PORTFOLIO)

    def get_current_portfolio(self) -> Dict[str, Any]:
        return dict(self.current_portfolio)

    def _series(
        self,
        annual_return: float,
        years: int,
        *,
        vol: float = 0.15,
        seed_offset: int = 0,
    ) -> List[float]:
        """Normalized index: 1.0 → (1+r)^years with realistic volatility."""
        points = 8
        months = max(12, years * 12)
        seed = ((int(round(annual_return * 1e4)) ^ years * 7919) + seed_offset) & 0xFFFFFFFF
        rng = random.Random(seed)

        mu = math.log(1 + annual_return)
        monthly_vol = vol / math.sqrt(12)
        monthly_mu = mu / 12 - 0.5 * monthly_vol * monthly_vol

        path = [1.0]
        for _ in range(months):
            z = rng.gauss(0, 1)
            path.append(path[-1] * math.exp(monthly_mu + monthly_vol * z))

        target = (1 + annual_return) ** years
        path[-1] = max(path[-1], 1e-6)
        scale = target / path[-1]
        path = [v * scale for v in path]

        idxs = [round(i * months / (points - 1)) for i in range(points)]
        return [round(path[i], 4) for i in idxs]

    async def generate_portfolio(self, variant: Optional[int]) -> Dict[str, Any]:
        idx = (variant or 0) % len(self.portfolios)
        p = dict(self.portfolios[idx])
        p["generatedAt"] = datetime.now(timezone.utc).isoformat()
        return {"success": True, "data": p}

    async def backtest(self, portfolio_id: str, period_years: int, benchmark: str) -> Dict[str, Any]:
        if portfolio_id == "proposed" and period_years >= 5:
            return {"success": False, "error_code": "insufficient_data"}

        now = datetime.now(timezone.utc)
        points = 8
        dates = []
        for i in range(points):
            offset_months = round(period_years * 12 * (points - 1 - i) / (points - 1))
            year = now.year
            month = now.month - offset_months
            while month <= 0:
                month += 12
                year -= 1
            dates.append(datetime(year, month, 1, tzinfo=timezone.utc).date().isoformat())

        r = 0.124 if portfolio_id == "current" else 0.138
        b = 0.098

        r_prev = round(r - 0.015 if portfolio_id == "current" else r - 0.02, 4)
        b_prev = round(b - 0.012, 4)

        dates_prev = []
        for i in range(points):
            offset_months_prev = round(period_years * 12 * (points - 1 - i) / (points - 1)) + period_years * 12
            year = now.year
            month = now.month - offset_months_prev
            while month <= 0:
                month += 12
                year -= 1
            dates_prev.append(datetime(year, month, 1, tzinfo=timezone.utc).date().isoformat())

        return {
            "success": True,
            "data": {
                "dates": dates,
                "portfolio_values": self._series(r, period_years, vol=0.19, seed_offset=0),
                "benchmark_values": self._series(b, period_years, vol=0.14, seed_offset=9001),
                "previous": {
                    "dates": dates_prev,
                    "portfolio_values": self._series(r_prev, period_years, vol=0.19, seed_offset=42),
                    "benchmark_values": self._series(b_prev, period_years, vol=0.14, seed_offset=9043),
                    "metrics": {
                        "portfolio": {
                            "annual_return": r_prev,
                            "max_drawdown": -0.108 if portfolio_id == "current" else -0.125,
                            "sharpe_ratio": 1.0 if portfolio_id == "current" else 1.12,
                            "volatility": 0.175 if portfolio_id == "current" else 0.2,
                            "worst_drawdown_date": dates_prev[3],
                        },
                        "benchmark": {
                            "annual_return": b_prev,
                            "max_drawdown": -0.14,
                            "sharpe_ratio": 0.9,
                        },
                    },
                },
                "metrics": {
                    "portfolio": {
                        "annual_return": r,
                        "max_drawdown": -0.112 if portfolio_id == "current" else -0.128,
                        "sharpe_ratio": 1.08 if portfolio_id == "current" else 1.16,
                        "volatility": 0.162 if portfolio_id == "current" else 0.188,
                        "worst_drawdown_date": dates[3],
                    },
                    "benchmark": {"annual_return": b, "max_drawdown": -0.135, "sharpe_ratio": 0.87},
                },
            },
        }

    async def scenario(self, portfolio_id: str, scenario_type: str, scenario_value: float) -> Dict[str, Any]:
        if scenario_type not in SCENARIO_CONFIGS:
            return {"success": False, "error_code": "unsupported_scenario"}

        base_map = {"rate_hike": -8.2, "market_drop": -12.5, "currency_shock": -6.3}
        base = base_map[scenario_type]
        k = 1.0 if portfolio_id == "current" else 1.1
        total = round(base * (scenario_value / 25.0) * k, 1)

        cfg = SCENARIO_CONFIGS[scenario_type]

        losers = [
            {"asset_name": x["asset_name"], "impact_percent": round(total * x["coef"], 1)}
            for x in cfg["losers"]
        ]
        winners = [
            {"asset_name": x["asset_name"], "impact_percent": round(abs(total) * x["coef"], 1)}
            for x in cfg["winners"]
        ]
        return {
            "success": True,
            "data": {
                "total_impact_percent": total,
                "top_losers": losers,
                "top_winners": winners,
                "explanation_factors": cfg["explanation"],
            },
        }

    async def recalculate_portfolio(
        self,
        scenario_id: str,
        products: List[Dict[str, Any]],
        *,
        risk_profile: str = "medium",
        baseline_products: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Заглушка пересчёта метрик Co-pilot (< 2 с)."""
        import asyncio

        from .copilot_metrics import compute_portfolio_metrics

        await asyncio.sleep(0.08)

        metrics = compute_portfolio_metrics(products, baseline_products)

        return {
            "success": True,
            "data": {
                "recalc_ms": 350,
                "metrics": metrics,
            },
        }
