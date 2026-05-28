import os
from typing import Any, Dict

from fastapi import APIRouter

from .asset_llm import AssetLlmClient
from .asset_service import AssetService
from .clients import ExternalApiClient, VtbModelClient
from .models import AssetRequest, ChatRequest, PortfolioRequest
from .products import universe_for_api
from .product_metrics import metrics_labels_for_kind, metrics_spec_for_kind
from .services import DialogService

router = APIRouter(prefix="/api")

_api = ExternalApiClient()
_vtb = VtbModelClient()
_asset_llm = AssetLlmClient(_api)
_dialog = DialogService(_vtb)
_asset = AssetService(_asset_llm, _api)


@router.get("/health")
async def health() -> Dict[str, Any]:
    from datetime import datetime, timezone

    return {"ok": True, "at": datetime.now(timezone.utc).isoformat()}


@router.get("/products/universe")
async def products_universe() -> Dict[str, Any]:
    return {"success": True, "data": universe_for_api()}


@router.get("/products/metrics-schema")
async def products_metrics_schema(kind: str) -> Dict[str, Any]:
    k = (kind or "").strip().lower()
    return {
        "success": True,
        "data": {
            "kind": k,
            "metrics": metrics_spec_for_kind(k),
            "labels": metrics_labels_for_kind(k),
        },
    }


@router.get("/config-check")
async def config_check() -> Dict[str, Any]:
    provider = (os.getenv("LLM_PROVIDER", "aitunnel").strip() or "aitunnel").lower()
    required = ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_ENDPOINT"]
    optional = ["SOURCES_API_TOKEN", "NEWS_API_KEY"]
    missing = [k for k in required if not os.getenv(k, "").strip()]
    present_optional = [k for k in optional if os.getenv(k, "").strip()]
    return {
        "ok": len(missing) == 0 and provider in {"perplexity", "aitunnel"},
        "provider": provider,
        "provider_supported": provider in {"perplexity", "aitunnel"},
        "missing_required": missing,
        "present_optional": present_optional,
    }


@router.post("/portfolio/generate")
async def generate_portfolio(req: PortfolioRequest) -> Dict[str, Any]:
    generated = await _vtb.generate_portfolio(req.variant)
    if req.sessionId:
        s = _dialog.get_session(req.sessionId)
        s.portfolio_id = "proposed"
        s.proposed_portfolio = generated.get("data")
    return generated


@router.post("/chat")
async def chat(req: ChatRequest) -> Dict[str, Any]:
    return await _dialog.handle_chat(req.sessionId, req.message)


@router.post("/asset-analysis")
async def asset_analysis(req: AssetRequest) -> Dict[str, Any]:
    return await _asset.analyze(req.asset_id, req.asset_type, req.period_days)
