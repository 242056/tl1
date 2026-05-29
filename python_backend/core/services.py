from datetime import datetime
from typing import Any, Dict, Optional

from .clients import VtbModelClient
from .models import SessionContext
from .nlu import (
    detect_intent,
    detect_scenario_type,
    extract_period_years,
    extract_portfolio,
    extract_scenario_value,
    flip_portfolio,
    is_compare_portfolio_request,
    is_other_period,
    is_same_operation_other_portfolio,
    is_yes,
    portfolio_label,
    portfolio_phrase,
    years_word,
)


class DialogService:
    def __init__(self, vtb_model: VtbModelClient) -> None:
        self.vtb_model = vtb_model
        self.sessions: Dict[str, SessionContext] = {}

    def get_session(self, session_id: str) -> SessionContext:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionContext()
        return self.sessions[session_id]

    def _portfolio_for_session(self, s: SessionContext):
        if s.portfolio_id == "proposed":
            return s.proposed_portfolio
        if s.portfolio_id == "current":
            return self.vtb_model.get_current_portfolio()
        return None

    async def _ensure_proposed_portfolio(self, s: SessionContext) -> None:
        if s.proposed_portfolio is None:
            s.proposed_portfolio = (await self.vtb_model.generate_portfolio(None)).get("data")

    async def _set_portfolio(self, s: SessionContext, portfolio_id: str) -> None:
        s.portfolio_id = portfolio_id  # type: ignore[assignment]
        if portfolio_id == "proposed":
            await self._ensure_proposed_portfolio(s)

    def _scenario_value_prompt(self, scenario_type: str) -> Dict[str, Any]:
        if scenario_type == "market_drop":
            return {
                "reply": "На сколько процентов, по вашему мнению, упадет индекс? Например, на 30%.",
                "actions": ["На 10%", "На 30%"],
            }
        if scenario_type == "currency_shock":
            return {
                "reply": "На сколько процентов, по вашему мнению, ослабнет рубль? Например, на 20%.",
                "actions": ["На 10%", "На 20%"],
            }
        return {
            "reply": "На сколько процентов, по вашему мнению, вырастет ставка? Например, до 25%.",
            "actions": ["До 25%", "На 30%"],
        }

    def _scenario_reply(self, scenario_type: str, scenario_value: float, total_impact: float) -> str:
        if scenario_type == "rate_hike":
            return f"Если ключевая ставка вырастет до {scenario_value:.1f}%, общий эффект по портфелю может составить {total_impact}%."
        if scenario_type == "market_drop":
            return f"Если индекс снизится на {scenario_value:.1f}%, общий эффект по портфелю может составить {total_impact}%."
        return f"Если рубль ослабнет на {scenario_value:.1f}%, общий эффект по портфелю может составить {total_impact}%."

    def _worst_drawdown_text(self, metrics: Dict[str, Any]) -> str:
        worst_date = metrics["portfolio"].get("worst_drawdown_date")
        if not worst_date:
            return ""
        try:
            dt = datetime.fromisoformat(str(worst_date))
            return dt.strftime("%m.%Y")
        except ValueError:
            return str(worst_date)

    async def _build_backtest_result(
        self,
        s: SessionContext,
        years: int,
        *,
        prefix: str = "",
    ) -> Dict[str, Any]:
        result = await self.vtb_model.backtest(s.portfolio_id, years, "IMOEX")
        if not result.get("success"):
            if result.get("error_code") == "insufficient_data":
                return {
                    "success": False,
                    "intent": "BACKTEST",
                    "reply": "Истории портфеля пока недостаточно для расчета. Попробуйте через пару месяцев.",
                    "context": s.model_dump(),
                }
            return {
                "success": False,
                "intent": "BACKTEST",
                "reply": "Не удалось рассчитать бэктест. Попробуйте позже или выберите другой период",
                "context": s.model_dump(),
            }

        m = result["data"]["metrics"]
        s.pending_intent = None
        s.pending_backtest_years = None
        s.last_backtest_years = years
        s.last_intent = "BACKTEST"
        worst_date_text = self._worst_drawdown_text(m)
        portfolio_name = portfolio_label(s.portfolio_id)
        reply = (
            f"{prefix}Проверил {portfolio_name} портфель за последние {years} {years_word(years)}. "
            f"Годовая доходность портфеля {(m['portfolio']['annual_return'] * 100):.1f}% "
            f"(IMOEX: {(m['benchmark']['annual_return'] * 100):.1f}%). "
            f"Максимальная просадка {(m['portfolio']['max_drawdown'] * 100):.1f}%"
            f"{f' (пик просадки: {worst_date_text})' if worst_date_text else ''}. "
            f"Коэффициент Шарпа {m['portfolio']['sharpe_ratio']}."
        )
        return {
            "success": True,
            "intent": "BACKTEST",
            "reply": reply,
            "data": result["data"],
            "portfolio": self._portfolio_for_session(s),
            "actions": ["Задать другой период", "Сравнить с другим портфелем", "Что это значит?", "Оформить портфель"],
            "context": s.model_dump(),
        }

    async def _build_scenario_result(
        self,
        s: SessionContext,
        scenario_type: str,
        scenario_value: float,
        *,
        prefix: str = "",
        persist: bool = True,
    ) -> Dict[str, Any]:
        result = await self.vtb_model.scenario(s.portfolio_id, scenario_type, scenario_value)
        if not result.get("success"):
            if result.get("error_code") == "unsupported_scenario":
                return {
                    "success": False,
                    "intent": "SCENARIO",
                    "reply": "Этот сценарий пока недоступен. Могу показать рост ставки, падение индекса или ослабление рубля.",
                    "actions": ["Рост ставки", "Падение индекса", "Ослабление рубля"],
                    "context": s.model_dump(),
                }
            return {
                "success": False,
                "intent": "SCENARIO",
                "reply": "Не удалось рассчитать сценарий. Попробуйте другую величину или обратитесь к менеджеру",
                "context": s.model_dump(),
            }

        if persist:
            s.last_scenario = {"type": scenario_type, "value": scenario_value}
            s.pending_intent = None
            s.pending_scenario_type = None
            s.pending_scenario_value = None
        s.last_intent = "SCENARIO"
        portfolio_name = portfolio_phrase(s.portfolio_id)
        reply = f"{prefix}{portfolio_name}: {self._scenario_reply(scenario_type, scenario_value, result['data']['total_impact_percent'])}"
        return {
            "success": True,
            "intent": "SCENARIO",
            "reply": reply,
            "data": result["data"],
            "portfolio": self._portfolio_for_session(s),
            "actions": ["Сравнить с другим портфелем", "Другой сценарий", "Что делать в этом случае?", "Защитить портфель", "Оформить портфель"],
            "context": s.model_dump(),
        }

    async def _handle_compare_portfolio(
        self,
        s: SessionContext,
        msg: str,
        portfolio_hint: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        target = portfolio_hint
        if not target and is_same_operation_other_portfolio(msg) and s.portfolio_id:
            target = flip_portfolio(s.portfolio_id)

        if s.last_intent == "SCENARIO" and s.last_scenario:
            if not target:
                s.pending_compare_intent = "SCENARIO"
                return {
                    "success": True,
                    "intent": "SCENARIO",
                    "reply": "Хорошо, выберите портфель для сравнения: текущий или предложенный.",
                    "actions": ["Текущий", "Предложенный"],
                    "context": s.model_dump(),
                }
            await self._set_portfolio(s, target)
            s.pending_compare_intent = None
            t = s.last_scenario.get("type")
            v = s.last_scenario.get("value")
            if t and v is not None:
                return await self._build_scenario_result(
                    s,
                    str(t),
                    float(v),
                    prefix="Пересчитал тот же сценарий. ",
                    persist=False,
                )

        if s.last_backtest_years or s.last_intent == "BACKTEST":
            if not s.last_backtest_years:
                s.pending_intent = "BACKTEST"
                return {
                    "success": True,
                    "intent": "BACKTEST",
                    "reply": "Сначала сделайте бэктест (например, за 3 года), и я смогу сравнить с другим портфелем.",
                    "actions": ["1 год", "3 года", "5 лет"],
                    "context": s.model_dump(),
                }
            if not target:
                s.pending_compare_intent = "BACKTEST"
                return {
                    "success": True,
                    "intent": "BACKTEST",
                    "reply": "Хорошо, выберите портфель для сравнения: текущий или предложенный.",
                    "actions": ["Текущий", "Предложенный"],
                    "context": s.model_dump(),
                }
            await self._set_portfolio(s, target)
            s.pending_compare_intent = None
            return await self._build_backtest_result(
                s,
                s.last_backtest_years,
                prefix="Пересчитал тот же бэктест. ",
            )

        if s.last_intent == "SCENARIO":
            return {
                "success": True,
                "intent": "SCENARIO",
                "reply": "Сначала запустите сценарий, а затем я смогу сравнить его на другом портфеле.",
                "actions": ["Другой сценарий"],
                "context": s.model_dump(),
            }

        return {
            "success": True,
            "intent": "BACKTEST",
            "reply": "Сначала сделайте бэктест (например, за 3 года), и я смогу сравнить с другим портфелем.",
            "actions": ["1 год", "3 года", "5 лет"],
            "context": s.model_dump(),
        }

    def _contextual_unknown_reply(self, s: SessionContext) -> Dict[str, Any]:
        if s.last_intent == "BACKTEST" and s.last_backtest_years:
            years = s.last_backtest_years
            portfolio = portfolio_label(s.portfolio_id)
            return {
                "success": True,
                "intent": "BACKTEST",
                "reply": (
                    f"Последний расчёт — бэктест за {years} {years_word(years)} ({portfolio} портфель). "
                    "Могу пересчитать на другом портфеле или задать другой период."
                ),
                "actions": ["Сравнить с другим портфелем", "Задать другой период", "Сценарий"],
                "context": s.model_dump(),
            }
        if s.last_intent == "SCENARIO" and s.last_scenario:
            return {
                "success": True,
                "intent": "SCENARIO",
                "reply": (
                    "Последний расчёт — стресс-сценарий. "
                    "Могу пересчитать на другом портфеле или задать другой сценарий."
                ),
                "actions": ["Сравнить с другим портфелем", "Другой сценарий", "Бэктест"],
                "context": s.model_dump(),
            }
        return {
            "success": True,
            "intent": "UNKNOWN",
            "reply": "Я помогу с тремя задачами: бэктест портфеля, стресс-сценарий или математический паспорт продукта (Анти-Гугл). Что вас интересует?",
            "actions": ["Бэктест", "Сценарий", "Математический паспорт"],
            "context": s.model_dump(),
        }

    async def handle_chat(self, session_id: str, message: str) -> Dict[str, Any]:
        s = self.get_session(session_id)
        s.history.append(message)
        s.history = s.history[-20:]
        msg = message.strip()
        mlow = msg.lower()

        portfolio_hint = extract_portfolio(msg)

        if is_compare_portfolio_request(msg):
            return await self._handle_compare_portfolio(s, msg, portfolio_hint)

        if portfolio_hint:
            await self._set_portfolio(s, portfolio_hint)

            if s.pending_compare_intent == "BACKTEST" and s.last_backtest_years:
                s.pending_compare_intent = None
                return await self._build_backtest_result(
                    s,
                    s.last_backtest_years,
                    prefix="Пересчитал тот же бэктест. ",
                )

            if s.pending_compare_intent == "SCENARIO" and s.last_scenario:
                t = s.last_scenario.get("type")
                v = s.last_scenario.get("value")
                s.pending_compare_intent = None
                if t and v is not None:
                    return await self._build_scenario_result(
                        s,
                        str(t),
                        float(v),
                        prefix="Пересчитал тот же сценарий. ",
                        persist=False,
                    )

        if s.pending_intent == "BACKTEST" and s.pending_backtest_years == 5 and is_yes(msg):
            msg = f"{msg} 5 лет"
        if s.pending_intent == "BACKTEST" and is_other_period(msg):
            return {"success": True, "intent": "BACKTEST", "reply": "Укажи период для бэктеста: например, 1 год, 3 года или 5 лет.", "actions": ["1 год", "3 года", "5 лет"], "context": s.model_dump()}

        if "задать другой период" in mlow:
            s.pending_intent = "BACKTEST"
            s.pending_backtest_years = None
            return {"success": True, "intent": "BACKTEST", "reply": "Укажи период для бэктеста: 1 год, 3 года или 5 лет.", "actions": ["1 год", "3 года", "5 лет"], "context": s.model_dump()}
        if "что это значит" in mlow:
            return {"success": True, "intent": s.last_intent or "UNKNOWN", "reply": "Коэффициент Шарпа показывает эффективность с учетом риска: чем выше, тем лучше. Максимальная просадка — наибольшее снижение портфеля от локального пика.", "actions": ["Задать другой период", "Сравнить с другим портфелем"], "context": s.model_dump()}
        if "оформить портфель" in mlow:
            return {"success": True, "intent": s.last_intent or "UNKNOWN", "reply": "Отличный выбор! Я передам заявку вашему персональному менеджеру, он свяжется с вами для оформления.", "actions": ["Бэктест", "Сценарий"], "context": s.model_dump()}
        if "другой сценарий" in mlow or "выбрать другой сценарий" in mlow:
            s.pending_intent = "SCENARIO"
            s.pending_scenario_type = None
            s.pending_scenario_value = None
            return {"success": True, "intent": "SCENARIO", "reply": "Какой сценарий вас интересует? Рост ставки, падение индекса или ослабление рубля?", "actions": ["Рост ставки", "Падение индекса", "Ослабление рубля"], "context": s.model_dump()}
        if "что делать в этом случае" in mlow or "защитить портфель" in mlow:
            return {"success": True, "intent": s.last_intent or "UNKNOWN", "reply": "Для защиты портфеля мы обычно рекомендуем увеличить долю защитных активов. Обратитесь к менеджеру для подбора индивидуальной стратегии.", "actions": ["Другой сценарий", "Оформить портфель"], "context": s.model_dump()}

        intent = detect_intent(msg)
        years_hint = extract_period_years(msg)
        scenario_type_hint = detect_scenario_type(msg)
        scenario_value_hint = extract_scenario_value(msg)

        if intent == "UNKNOWN":
            if years_hint is not None and s.last_intent == "BACKTEST":
                intent = "BACKTEST"
            elif (scenario_type_hint is not None or scenario_value_hint is not None) and s.last_intent == "SCENARIO":
                intent = "SCENARIO"
            elif s.pending_intent in {"BACKTEST", "SCENARIO"} and (
                portfolio_hint is not None
                or years_hint is not None
                or scenario_type_hint is not None
                or scenario_value_hint is not None
                or is_yes(msg)
            ):
                intent = s.pending_intent

        if intent != "UNKNOWN":
            s.last_intent = intent

        if intent == "UNKNOWN":
            return self._contextual_unknown_reply(s)

        if not s.portfolio_id:
            s.pending_intent = intent
            if intent == "BACKTEST":
                s.pending_backtest_years = years_hint
            if intent == "SCENARIO":
                s.pending_scenario_type = scenario_type_hint
                s.pending_scenario_value = scenario_value_hint
            return {"success": True, "intent": intent, "reply": "Какой портфель вас интересует? Текущий или предложенный мной?", "actions": ["Текущий", "Предложенный"], "context": s.model_dump()}

        if intent == "BACKTEST":
            years = years_hint or s.pending_backtest_years or 3
            if years > 5:
                s.pending_intent = "BACKTEST"
                s.pending_backtest_years = 5
                return {"success": True, "intent": intent, "reply": "Максимальный период для бэктеста — 5 лет. Хотите посмотреть за 5 лет?", "actions": ["Да, 5 лет", "Другой период"], "context": s.model_dump()}
            if years < 1:
                years = 1
            return await self._build_backtest_result(s, years)

        scenario_type = scenario_type_hint or s.pending_scenario_type
        if not scenario_type:
            s.pending_intent = "SCENARIO"
            s.pending_scenario_value = scenario_value_hint
            return {"success": True, "intent": intent, "reply": "Пожалуйста, уточните. Я понимаю сценарии: рост ставки до X%, падение индекса на Y%, ослабление рубля на Z%.", "actions": ["Рост ставки", "Падение индекса", "Ослабление рубля"], "context": s.model_dump()}
        if scenario_type not in {"rate_hike", "market_drop", "currency_shock"}:
            return {"success": False, "intent": intent, "reply": "Этот сценарий пока недоступен. Могу показать рост ставки, падение индекса или ослабление рубля.", "actions": ["Рост ставки", "Падение индекса", "Ослабление рубля"], "context": s.model_dump()}

        scenario_value = scenario_value_hint or s.pending_scenario_value
        if scenario_value is None:
            s.pending_intent = "SCENARIO"
            s.pending_scenario_type = scenario_type
            prompt = self._scenario_value_prompt(scenario_type)
            return {"success": True, "intent": intent, "reply": prompt["reply"], "actions": prompt["actions"], "context": s.model_dump()}

        if scenario_type == "rate_hike" and scenario_value > 50:
            if not is_yes(msg):
                s.pending_intent = "SCENARIO"
                s.pending_scenario_type = scenario_type
                s.pending_scenario_value = scenario_value
                return {"success": True, "intent": intent, "reply": "Это маловероятный сценарий. Показать расчет с большой погрешностью?", "actions": ["Да, показать", "Выбрать другой сценарий"], "context": s.model_dump()}

        return await self._build_scenario_result(s, scenario_type, scenario_value)
