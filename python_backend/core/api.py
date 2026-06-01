import os
from typing import Any, Dict

from fastapi import APIRouter

from .agent_service import AgentService
from .asset_llm import AssetLlmClient
from .asset_service import AssetService
from .clients import ExternalApiClient, VtbModelClient
from .copilot_service import CopilotService
from .models import (
    AgentRequest,
    AssetRequest,
    ChatRequest,
    CopilotAssetRequest,
    CopilotConfirmRequest,
    CopilotInitRequest,
    CopilotPresetRequest,
    CopilotRecalculateRequest,
    CopilotSessionRequest,
    PortfolioRequest,
)
from .products import universe_for_api
from .product_metrics import metrics_labels_for_kind, metrics_spec_for_kind
from .services import DialogService

router = APIRouter(prefix="/api")

_api = ExternalApiClient()
_vtb = VtbModelClient()
_asset_llm = AssetLlmClient(_api)
_dialog = DialogService(_vtb)
_asset = AssetService(_asset_llm, _api)
_copilot = CopilotService(_vtb)
_agent = AgentService(_dialog, _asset, _copilot)


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
    return await _agent.handle(req.sessionId, req.message)


@router.post("/agent")
async def agent(req: AgentRequest) -> Dict[str, Any]:
    return await _agent.handle(req.sessionId, req.message)


@router.post("/asset-analysis")
async def asset_analysis(req: AssetRequest) -> Dict[str, Any]:
    return await _asset.analyze(req.asset_id, req.asset_type, req.period_days)


@router.get("/copilot/scenarios")
async def copilot_scenarios() -> Dict[str, Any]:
    return {"success": True, "data": _copilot.list_scenarios()}


@router.get("/copilot/session/{session_id}")
async def copilot_session(session_id: str) -> Dict[str, Any]:
    return _copilot.get_session_state(session_id)


@router.post("/copilot/init")
async def copilot_init(req: CopilotInitRequest) -> Dict[str, Any]:
    return await _copilot.init_session(req.sessionId, req.scenarioId)


@router.post("/copilot/recalculate")
async def copilot_recalculate(req: CopilotRecalculateRequest) -> Dict[str, Any]:
    weights = [{"productId": w.productId, "weight": w.weight} for w in req.weights]
    return await _copilot.recalculate(req.sessionId, weights)


@router.post("/copilot/preset")
async def copilot_preset(req: CopilotPresetRequest) -> Dict[str, Any]:
    return await _copilot.apply_preset(req.sessionId, req.presetId)


@router.post("/copilot/reset")
async def copilot_reset(req: CopilotSessionRequest) -> Dict[str, Any]:
    return await _copilot.reset_to_original(req.sessionId)


@router.post("/copilot/add-asset")
async def copilot_add_asset(req: CopilotAssetRequest) -> Dict[str, Any]:
    return await _copilot.add_asset(req.sessionId, req.productId, req.weight)


@router.post("/copilot/remove-asset")
async def copilot_remove_asset(req: CopilotAssetRequest) -> Dict[str, Any]:
    return await _copilot.remove_asset(req.sessionId, req.productId)


@router.post("/copilot/confirm")
async def copilot_confirm(req: CopilotConfirmRequest) -> Dict[str, Any]:
    return await _copilot.confirm_purchase(req.sessionId, req.confirmed)
