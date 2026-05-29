"""Карточка инструмента ВТБ и внутренняя аналитика (URL из env)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..clients import ExternalApiClient

log = logging.getLogger("vtb.official_sources.vtb")


@dataclass
class VtbFetchResult:
    card_ok: bool
    research_ok: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    context_lines: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)


def _extract_metrics_from_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Универсальный разбор JSON от внутренних API ВТБ."""
    out: Dict[str, Any] = {}
    if not isinstance(data, dict):
        return out

    flat_candidates = {
        "nav_per_share": ("navPerShare", "sharePrice", "price", "nav_per_share"),
        "price_change": ("priceChange", "oneYearChange", "dayChange"),
        "nav_aum": ("nav", "aum", "netAssetValue", "scha"),
        "min_investment": ("minInvestment", "minAmount", "min_investment"),
        "ter": ("ter", "terFee", "expenseRatio", "managementFee"),
        "market_price": ("marketPrice", "lastPrice", "price"),
        "dividend_yield_12m": ("dividendYield", "yield12m"),
        "dividend_per_share": ("dividendPerShare", "lastDividend"),
        "trading_volume": ("tradingVolume", "volume", "avgVolume"),
        "fund_lifetime": ("fundLifetime", "maturityDate", "inceptionDate"),
        "bid_price": ("bidPrice", "bid"),
        "ask_price": ("askPrice", "ask"),
        "bank_spread": ("bankSpread", "spread"),
        "daily_range": ("dailyRange", "highLow"),
        "period_change_pct": ("periodChange", "oneYearChange"),
        "historical_return": ("historicalReturn", "return1y", "return_1y"),
        "min_subscription": ("minSubscription", "minAmount"),
        "risk_profile": ("riskProfile", "riskLevel"),
        "recommended_horizon": ("recommendedHorizon", "investmentHorizon"),
        "management_fee": ("managementFee", "successFee", "ter"),
        "participation_coef": ("participationCoef", "participationRate"),
        "benchmark_name": ("benchmarkName", "underlyingIndex"),
        "contract_term": ("contractTerm", "term"),
        "capital_guarantee": ("capitalGuarantee", "guaranteedReturn"),
        "income_fixation_period": ("incomeFixationPeriod", "fixationPeriod"),
        "maturity_payout": ("maturityPayout", "insuranceAmount"),
        "regular_contribution": ("regularContribution", "contribution"),
        "program_term": ("programTerm", "insuranceTerm"),
        "covered_risks": ("coveredRisks", "riskCoverage"),
        "additional_income_ytd": ("additionalIncome", "did"),
        "cofinancing_threshold": ("cofinancingThreshold", "stateCofinancing"),
        "tax_deduction": ("taxDeduction", "taxBenefit"),
        "total_savings": ("totalSavings", "balance"),
        "years_to_payout": ("yearsToPayout", "participationTerm"),
        "fund_investment_income": ("fundInvestmentIncome", "npfReturn"),
        "carat_weight": ("caratWeight", "weight"),
        "color_clarity_grade": ("colorClarity", "certification4c"),
        "list_price_index": ("listPrice", "priceIndex"),
        "has_certificate": ("hasCertificate", "certified"),
        "buyback_discount": ("buybackDiscount", "buyBackSpread"),
        "daily_volume": ("dailyVolume", "volume"),
        "return_1y": ("return1y", "return_1y", "yield1y", "oneYearChange"),
        "isin": ("isin", "ISIN"),
        "interest_rate": ("rate", "interestRate", "nominalRate"),
        "placement_term": ("placementTerm", "depositTerm", "term"),
        "balance_limits": ("balanceLimits", "minBalance", "maxBalance"),
        "interest_payout": ("interestPayout", "capitalization"),
        "deposit_flexibility": ("depositFlexibility", "flexibility"),
    }
    for target, keys in flat_candidates.items():
        for k in keys:
            if k in data and data[k] not in (None, ""):
                out[target] = data[k]
                break
    if "metrics" in data and isinstance(data["metrics"], dict):
        for k, v in data["metrics"].items():
            if k not in out or out[k] is None:
                out[k] = v
    return out


async def fetch_vtb_sources(
    api: ExternalApiClient,
    asset_id: str,
    asset_type: str,
    period_days: int,
) -> VtbFetchResult:
    token = os.getenv("SOURCES_API_TOKEN")
    params = {"asset_id": asset_id, "asset_type": asset_type, "period_days": period_days, "product_name": asset_id}

    metrics: Dict[str, Any] = {}
    lines: List[str] = []
    errors: List[Dict[str, str]] = []
    card_ok = False
    research_ok = False

    card_url = os.getenv("SRC_INSTRUMENT_CARD_URL", "").strip()
    if card_url:
        try:
            data = await api.get(card_url, token, params)
            metrics.update(_extract_metrics_from_payload(data))
            lines.append("ВТБ: данные карточки инструмента получены.")
            card_ok = True
        except Exception as exc:
            errors.append({"source": "vtb_card", "error": str(exc)})

    research_url = os.getenv("SRC_VTB_RESEARCH_URL", "").strip()
    if research_url:
        try:
            data = await api.get(research_url, token, params)
            payload_metrics = _extract_metrics_from_payload(data)
            metrics.update(payload_metrics)
            lines.append("ВТБ: аналитический обзор получен.")
            research_ok = True
        except Exception as exc:
            errors.append({"source": "vtb_research", "error": str(exc)})

    reports_url = os.getenv("SRC_FIN_REPORTS_URL", "").strip()
    if reports_url:
        try:
            await api.get(reports_url, token, params)
            lines.append("ВТБ: отчётность доступна.")
        except Exception as exc:
            errors.append({"source": "vtb_reports", "error": str(exc)})

    return VtbFetchResult(card_ok, research_ok, metrics, [], lines, errors)
