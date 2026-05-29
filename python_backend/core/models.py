from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

PortfolioKind = Literal["current", "proposed"]
Intent = Literal["BACKTEST", "SCENARIO", "ASSET", "UNKNOWN"]
ScenarioType = Literal["rate_hike", "market_drop", "currency_shock"]
PendingIntent = Literal["BACKTEST", "SCENARIO", "ASSET"]


class SessionContext(BaseModel):
    portfolio_id: Optional[PortfolioKind] = None
    last_intent: Optional[Intent] = None
    last_scenario: Optional[Dict[str, Any]] = None
    last_backtest_years: Optional[int] = None
    pending_compare_intent: Optional[Intent] = None
    history: List[str] = Field(default_factory=list)
    proposed_portfolio: Optional[Dict[str, Any]] = None
    pending_intent: Optional[PendingIntent] = None
    pending_backtest_years: Optional[int] = None
    pending_scenario_type: Optional[ScenarioType] = None
    pending_scenario_value: Optional[float] = None
    pending_asset: bool = False
    last_asset_name: Optional[str] = None
    last_asset_kind: Optional[str] = None


class ChatRequest(BaseModel):
    sessionId: str
    message: str


class AgentRequest(BaseModel):
    sessionId: str
    message: str


class AssetRequest(BaseModel):
    asset_id: str
    asset_type: str
    user_id: str = "current"
    period_days: int = 30


class PortfolioRequest(BaseModel):
    sessionId: Optional[str] = None
    variant: Optional[int] = None
