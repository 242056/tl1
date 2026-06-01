"""Единый агент: диалог (бэктест/сценарий) + Анти-Гугл + ИИ-черновик (Co-pilot)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .agent_nlu import asset_action_label, detect_agent_route, is_passport_chip, match_product, product_suggestions
from .asset_service import AssetService
from .copilot_service import CopilotService
from .services import DialogService

_COPILOT_KEYWORDS = re.compile(
    r"ии[\s-]?черновик|"
    r"co[\s-]?pilot|копilot|копилот|"
    r"\bчерновик\b|"
    r"корректир|редактир\w*\s+портфел|изменить\s+портфел|подкоррект|"
    r"скорректир\w*\s+портфел|"
    r"ручн\w*\s+коррек|"
    r"интерактивн\w*\s+co|"
    r"открыть\s+черновик|"
    r"показать\s+черновик|"
    r"настроить\s+портфел|"
    r"собрать\s+портфел",
    re.I,
)

_COPILOT_EXACT = frozenset({
    "ии-черновик",
    "ии черновик",
    "co-pilot",
    "copilot",
    "co pilot",
    "копilot",
    "копилот",
    "черновик",
    "корректировать портфель",
    "интерактивный co-pilot",
    "интерактивный copilot",
    "интерактивный копilot",
    "открыть черновик",
    "показать черновик",
    "скорректировать портфель",
})

_COPILOT_CHIP = re.compile(r"^черновик:\s*", re.I)


class AgentService:
    def __init__(self, dialog: DialogService, asset: AssetService, copilot: CopilotService) -> None:
        self.dialog = dialog
        self.asset = asset
        self.copilot = copilot

    async def handle(self, session_id: str, message: str) -> Dict[str, Any]:
        session = self.dialog.get_session(session_id)
        msg = (message or "").strip()
        mlow = msg.lower()

        if mlow in _COPILOT_EXACT:
            return await self._handle_copilot_init(session_id, None)
        if _COPILOT_CHIP.match(msg):
            scenario_title = _COPILOT_CHIP.sub("", msg).strip()
            return await self._handle_copilot_init(session_id, scenario_title)

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

        if _COPILOT_KEYWORDS.search(msg) and not is_passport_chip(msg):
            return await self._handle_copilot_init(session_id, msg)

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

    def _match_copilot_scenario(self, hint: str) -> Optional[str]:
        hint_l = hint.lower().strip()
        for s in self.copilot.list_scenarios():
            if s["title"].lower() in hint_l or hint_l in s["title"].lower():
                return s["id"]
            if s["id"].replace("draft_", "").replace("_", " ") in hint_l:
                return s["id"]
        return None

    async def _handle_copilot_init(self, session_id: str, hint: Optional[str]) -> Dict[str, Any]:
        session = self.dialog.get_session(session_id)
        session.last_intent = "COPILOT"  # type: ignore[assignment]

        scenario_id = None
        if hint:
            scenario_id = self._match_copilot_scenario(hint)

        result = await self.copilot.init_session(session_id, scenario_id)
        if not result.get("success"):
            return {
                "success": False,
                "intent": "COPILOT",
                "mode": "copilot",
                "reply": result.get("message", "Не удалось открыть ИИ-черновик"),
                "actions": [],
                "context": session.model_dump(),
            }

        return {
            **result,
            "actions": [],
            "open_copilot": True,
            "context": {**session.model_dump(), **(result.get("context") or {})},
        }
