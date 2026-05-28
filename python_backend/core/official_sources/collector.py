"""Сбор проверенных данных с официальных источников до запроса к LLM."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..clients import ExternalApiClient
from ..product_metrics import metrics_keys, normalize_key_metrics
from ..product_reference import reference_profile, resolve_product_id
from ..product_sources import enrichment_bundle
from ..products import MOEX_TICKER_BY_PRODUCT, PROFINANSY_CODE_BY_PRODUCT, product_by_id, product_by_name
from .investing import fetch_investing
from .moex import fetch_moex
from .profinansy import fetch_profinansy
from .vtb import fetch_vtb_sources

log = logging.getLogger("vtb.official_sources")


class OfficialFetchResult:
    def __init__(
        self,
        metrics: Dict[str, Any],
        sources: List[Dict[str, str]],
        context_lines: List[str],
        coverage: Dict[str, bool],
        errors: List[Dict[str, str]],
        search_queries: List[str],
    ) -> None:
        self.metrics = metrics
        self.sources = sources
        self.context_lines = context_lines
        self.coverage = coverage
        self.errors = errors
        self.search_queries = search_queries

    @property
    def filled_metrics_count(self) -> int:
        return sum(1 for v in self.metrics.values() if v is not None and str(v).strip())

    def sufficient_for_metrics(self, kind: str) -> bool:
        need = 3 if kind == "bpif" else 2
        return self.filled_metrics_count >= need

    def context_text(self) -> str:
        return "\n".join(self.context_lines)


class OfficialDataCollector:
    def __init__(self, api: ExternalApiClient) -> None:
        self.api = api

    async def collect(
        self,
        asset_id: str,
        asset_type: str,
        period_days: int = 30,
    ) -> OfficialFetchResult:
        product = product_by_name(asset_id)
        if not product:
            product = product_by_id(asset_id)

        metrics: Dict[str, Any] = {k: None for k in metrics_keys(asset_type)}
        sources: List[Dict[str, str]] = []
        context_lines: List[str] = []
        search_queries: List[str] = []
        coverage: Dict[str, bool] = {
            "moex": False,
            "profinansy": False,
            "investing": False,
            "vtb_card": False,
            "vtb_research": False,
        }
        errors: List[Dict[str, str]] = []

        if product:
            context_lines.append(
                f"Каталог ВТБ: «{product['productName']}», категория «{product['category']}», тип {product['kind']}."
            )

        product_id = product["productId"] if product else asset_id
        moex_ticker = MOEX_TICKER_BY_PRODUCT.get(product_id)
        profinansy_code = PROFINANSY_CODE_BY_PRODUCT.get(product_id)

        enrich = enrichment_bundle(asset_id, asset_type)
        context_lines.extend(enrich.get("context_lines") or [])
        sources.extend(enrich.get("recommended_sources") or [])
        search_queries.extend(enrich.get("search_queries") or [])

        if moex_ticker and asset_type == "bpif":
            try:
                mx = await fetch_moex(self.api, moex_ticker)
                self._merge(metrics, mx.metrics, asset_type)
                sources.extend(mx.sources)
                context_lines.extend(mx.context_lines)
                coverage["moex"] = mx.ok
                if mx.error:
                    errors.append({"source": "moex", "error": mx.error})
            except Exception as exc:
                errors.append({"source": "moex", "error": str(exc)})

            try:
                pf = await fetch_profinansy(self.api, moex_ticker, asset_type)
                self._merge(metrics, pf.metrics, asset_type)
                sources.extend(pf.sources)
                context_lines.extend(pf.context_lines)
                coverage["profinansy"] = pf.ok
                if pf.error:
                    errors.append({"source": "profinansy", "error": pf.error})
            except Exception as exc:
                errors.append({"source": "profinansy", "error": str(exc)})

            try:
                inv = await fetch_investing(self.api, moex_ticker, asset_id)
                sources.extend(inv.sources)
                context_lines.extend(inv.context_lines)
                coverage["investing"] = inv.ok
            except Exception as exc:
                errors.append({"source": "investing", "error": str(exc)})

        elif profinansy_code and asset_type in ("opif", "zpif"):
            try:
                pf = await fetch_profinansy(self.api, profinansy_code, asset_type)
                self._merge(metrics, pf.metrics, asset_type)
                sources.extend(pf.sources)
                context_lines.extend(pf.context_lines)
                coverage["profinansy"] = pf.ok
                if pf.error:
                    errors.append({"source": "profinansy", "error": pf.error})
            except Exception as exc:
                errors.append({"source": "profinansy", "error": str(exc)})

        try:
            vtb = await fetch_vtb_sources(self.api, asset_id, asset_type, period_days)
            self._merge(metrics, vtb.metrics, asset_type)
            sources.extend(vtb.sources)
            context_lines.extend(vtb.context_lines)
            coverage["vtb_card"] = vtb.card_ok
            coverage["vtb_research"] = vtb.research_ok
            if vtb.errors:
                errors.extend(vtb.errors)
        except Exception as exc:
            errors.append({"source": "vtb", "error": str(exc)})

        # Эталонные метрики не подмешиваем сюда — только парсеры и API; эталон применяется после LLM.
        metrics = normalize_key_metrics(metrics, asset_type)
        deduped_sources = self._dedupe_sources(sources)

        log.info(
            "Official collect %s (%s): filled=%d coverage=%s",
            asset_id,
            asset_type,
            sum(1 for v in metrics.values() if v is not None),
            coverage,
        )
        return OfficialFetchResult(
            metrics, deduped_sources, context_lines, coverage, errors, search_queries
        )

    def stable_profile_for(self, asset_id: str, asset_type: str) -> Dict[str, Any]:
        product = product_by_name(asset_id) or product_by_id(asset_id)
        product_id = resolve_product_id(asset_id, product)
        return reference_profile(product_id, asset_type)

    def _merge(self, target: Dict[str, Any], patch: Dict[str, Any], kind: str) -> None:
        allowed = set(metrics_keys(kind))
        for key, val in patch.items():
            if key not in allowed:
                continue
            if val is None:
                continue
            if target.get(key) is None:
                target[key] = val

    def _dedupe_sources(self, sources: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen: set[str] = set()
        out: List[Dict[str, str]] = []
        for s in sources:
            url = (s.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(s)
        return out
