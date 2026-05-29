"""Сбор проверенных данных с официальных источников до запроса к LLM."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..clients import ExternalApiClient
from ..product_metrics import metrics_keys, normalize_key_metrics
from ..product_reference import reference_profile, resolve_product_id
from ..product_sources import enrichment_bundle, official_catalog_sources
from ..products import MOEX_TICKER_BY_PRODUCT, product_by_id, product_by_name
from .cbr_metals import fetch_cbr_metal
from .investing import fetch_investing
from .moex import fetch_moex
from .vtb import fetch_vtb_sources

log = logging.getLogger("vtb.official_sources")

# Порядок = приоритет метрик: первый источник побеждает при совпадении ключей,
# следующие заполняют только пустые поля.
_METRIC_PARSER_ORDER: Dict[str, List[str]] = {
    "bpif": ["moex", "investing"],
    "opif": ["investing"],
    "zpif": ["investing"],
    "precious_metal": ["investing", "cbr"],
}


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
            "investing": False,
            "cbr": False,
            "vtb_card": False,
            "vtb_research": False,
            "vtb_catalog": False,
        }
        errors: List[Dict[str, str]] = []

        if product:
            context_lines.append(
                f"Каталог ВТБ: «{product['productName']}», категория «{product['category']}», тип {product['kind']}."
            )

        product_id = product["productId"] if product else asset_id
        moex_ticker = MOEX_TICKER_BY_PRODUCT.get(product_id)
        product_name = (product or {}).get("productName", asset_id)

        enrich = enrichment_bundle(asset_id, asset_type)
        context_lines.extend(enrich.get("context_lines") or [])
        search_queries.extend(enrich.get("search_queries") or [])

        for parser in _METRIC_PARSER_ORDER.get(asset_type, []):
            if parser == "moex":
                if asset_type != "bpif" or not moex_ticker:
                    continue
                await self._fetch_moex(
                    moex_ticker,
                    asset_type,
                    metrics=metrics,
                    sources=sources,
                    context_lines=context_lines,
                    coverage=coverage,
                    errors=errors,
                )
            elif parser == "investing":
                await self._fetch_investing(
                    product_id=product_id,
                    asset_type=asset_type,
                    ticker=moex_ticker if asset_type == "bpif" else None,
                    product_name=product_name,
                    metrics=metrics,
                    sources=sources,
                    context_lines=context_lines,
                    coverage=coverage,
                    errors=errors,
                )
            elif parser == "cbr":
                if asset_type != "precious_metal":
                    continue
                await self._fetch_cbr(
                    product_id=product_id,
                    asset_type=asset_type,
                    metrics=metrics,
                    sources=sources,
                    context_lines=context_lines,
                    coverage=coverage,
                    errors=errors,
                )

        try:
            vtb = await fetch_vtb_sources(self.api, asset_id, asset_type, period_days)
            self._merge_metrics(metrics, vtb.metrics, asset_type)
            context_lines.extend(vtb.context_lines)
            coverage["vtb_card"] = vtb.card_ok
            coverage["vtb_research"] = vtb.research_ok
            if vtb.errors:
                errors.extend(vtb.errors)
        except Exception as exc:
            errors.append({"source": "vtb", "error": str(exc)})

        catalog_sources = official_catalog_sources(product_id, product_name)
        if catalog_sources:
            sources.extend(catalog_sources)
            coverage["vtb_catalog"] = True

        if moex_ticker and asset_type == "bpif" and not any(
            str(s.get("parser_origin") or "").lower() == "moex" for s in sources
        ):
            sources.append(
                {
                    "title": f"MOEX: {moex_ticker}",
                    "url": f"https://www.moex.com/ru/issue.aspx?code={moex_ticker}",
                    "parser_origin": "moex",
                    "product_id": product_id,
                    "catalog_verified": "1",
                }
            )

        metrics = normalize_key_metrics(metrics, asset_type)
        deduped_sources = self._dedupe_sources(sources)

        log.info(
            "Official collect %s (%s): filled=%d sources=%d coverage=%s",
            asset_id,
            asset_type,
            sum(1 for v in metrics.values() if v is not None),
            len(deduped_sources),
            coverage,
        )
        return OfficialFetchResult(
            metrics,
            deduped_sources,
            context_lines,
            coverage,
            errors,
            search_queries,
        )

    def stable_profile_for(self, asset_id: str, asset_type: str) -> Dict[str, Any]:
        product = product_by_name(asset_id) or product_by_id(asset_id)
        product_id = resolve_product_id(asset_id, product)
        return reference_profile(product_id, asset_type)

    async def _fetch_moex(
        self,
        ticker: str,
        asset_type: str,
        *,
        metrics: Dict[str, Any],
        sources: List[Dict[str, str]],
        context_lines: List[str],
        coverage: Dict[str, bool],
        errors: List[Dict[str, str]],
    ) -> None:
        try:
            mx = await fetch_moex(self.api, ticker, asset_type)
            self._merge_metrics(metrics, mx.metrics, asset_type)
            context_lines.extend(mx.context_lines)
            coverage["moex"] = mx.ok
            if mx.ok:
                sources.extend(mx.sources)
            if mx.error:
                errors.append({"source": "moex", "error": mx.error})
        except Exception as exc:
            errors.append({"source": "moex", "error": str(exc)})

    async def _fetch_investing(
        self,
        *,
        product_id: str,
        asset_type: str,
        ticker: str | None,
        product_name: str,
        metrics: Dict[str, Any],
        sources: List[Dict[str, str]],
        context_lines: List[str],
        coverage: Dict[str, bool],
        errors: List[Dict[str, str]],
    ) -> None:
        try:
            inv = await fetch_investing(
                self.api,
                product_id=product_id,
                asset_type=asset_type,
                ticker=ticker,
                product_name=product_name,
            )
            self._merge_metrics(metrics, inv.metrics, asset_type)
            coverage["investing"] = inv.ok
            if inv.ok:
                sources.extend(inv.sources)
                context_lines.extend(inv.context_lines)
            if inv.error:
                errors.append({"source": "investing", "error": inv.error})
        except Exception as exc:
            errors.append({"source": "investing", "error": str(exc)})

    async def _fetch_cbr(
        self,
        *,
        product_id: str,
        asset_type: str,
        metrics: Dict[str, Any],
        sources: List[Dict[str, str]],
        context_lines: List[str],
        coverage: Dict[str, bool],
        errors: List[Dict[str, str]],
    ) -> None:
        try:
            cbr = await fetch_cbr_metal(product_id)
            self._merge_metrics(metrics, cbr.metrics, asset_type)
            coverage["cbr"] = cbr.ok
            if cbr.ok:
                sources.extend(cbr.sources)
            context_lines.extend(cbr.context_lines)
            if cbr.error:
                errors.append({"source": "cbr", "error": cbr.error})
        except Exception as exc:
            errors.append({"source": "cbr", "error": str(exc)})

    def _merge_metrics(self, target: Dict[str, Any], patch: Dict[str, Any], kind: str) -> None:
        """Слияние по приоритету: уже заполненные поля не перезаписываются."""
        allowed = set(metrics_keys(kind))
        for key, val in patch.items():
            if key not in allowed:
                continue
            if val is None:
                continue
            if isinstance(val, str) and not val.strip():
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
