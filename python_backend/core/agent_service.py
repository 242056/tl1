"""Единый агент: диалог (бэктест/сценарий) + Анти-Гугл (паспорт продукта)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .agent_nlu import asset_action_label, detect_agent_route, is_passport_chip, match_product, product_suggestions
from .asset_service import AssetService
from .services import DialogService


class AgentService:
    def __init__(self, dialog: DialogService, asset: AssetService) -> None:
        self.dialog = dialog
        self.asset = asset

    async def handle(self, session_id: str, message: str) -> Dict[str, Any]:
        session = self.dialog.get_session(session_id)
        msg = (message or "").strip()
        mlow = msg.lower()

        if mlow in {"математический паспорт", "анти-гугл", "антигугл", "паспорт продукта", "паспорт"}:
            return await self._handle_asset_passport(session_id, "")
        if mlow in {"другой продукт", "выбрать другой продукт"}:
            session.pending_asset = True
            session.pending_intent = "ASSET"
            return await self._handle_asset_passport(session_id, "")
        if mlow == "обновить паспорт" and session.last_asset_name and session.last_asset_kind:
            return await self._handle_asset_passport(session_id, session.last_asset_name)

        if is_passport_chip(msg):
            session.pending_intent = None
            session.pending_asset = False
            return await self._handle_asset_passport(session_id, msg)

        pending_asset = session.pending_asset or session.pending_intent == "ASSET"
        pending_dialog = session.pending_intent if session.pending_intent in {"BACKTEST", "SCENARIO"} else None
        route = detect_agent_route(
            msg,
            pending_asset=pending_asset,
            pending_dialog_intent=pending_dialog,
        )
        if route == "ASSET":
            return await self._handle_asset_passport(session_id, msg)
        return await self.dialog.handle_chat(session_id, msg)

    async def _handle_asset_passport(self, session_id: str, message: str) -> Dict[str, Any]:
        session = self.dialog.get_session(session_id)
        session.last_intent = "ASSET"  # type: ignore[assignment]

        product = match_product(message)
        if not product:
            session.pending_intent = "ASSET"  # type: ignore[assignment]
            session.pending_asset = True
            suggestions = product_suggestions(6)
            actions = [asset_action_label(p) for p in suggestions]
            actions.append("Бэктест")
            actions.append("Сценарий")
            return {
                "success": True,
                "intent": "ASSET",
                "mode": "antigoogle",
                "reply": (
                    "Сформирую математический паспорт продукта: ключевые показатели, факторы и источники. "
                    "Выберите продукт из списка или напишите его название."
                ),
                "actions": actions,
                "context": session.model_dump(),
            }

        session.pending_intent = None
        session.pending_asset = False
        session.last_asset_name = product["productName"]
        session.last_asset_kind = product["kind"]

        result = await self.asset.analyze(
            product["productId"],
            product["kind"],
            period_days=30,
        )

        if not result.get("success"):
            return {
                "success": False,
                "intent": "ASSET",
                "mode": "antigoogle",
                "reply": result.get("message") or "Не удалось подготовить паспорт продукта.",
                "actions": ["Выбрать другой продукт", "Бэктест", "Сценарий"],
                "context": session.model_dump(),
            }

        passport = result.get("data") or {}

        return {
            "success": True,
            "intent": "ASSET",
            "mode": "antigoogle",
            "reply": "",
            "passport": passport,
            "actions": [
                "Обновить паспорт",
                "Другой продукт",
                "Бэктест",
                "Сценарий",
            ],
            "context": session.model_dump(),
        }
