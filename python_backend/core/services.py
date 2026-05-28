from datetime import datetime
from typing import Any, Dict

from .clients import VtbModelClient
from .models import SessionContext
from .nlu import (
    detect_intent,
    detect_scenario_type,
    extract_period_years,
    extract_portfolio,
    extract_scenario_value,
    is_other_period,
    is_yes,
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

    async def handle_chat(self, session_id: str, message: str) -> Dict[str, Any]:
        s = self.get_session(session_id)
        s.history.append(message)
        s.history = s.history[-5:]
        msg = message.strip()
        mlow = msg.lower()

        portfolio_hint = extract_portfolio(msg)
        if portfolio_hint:
            s.portfolio_id = portfolio_hint
            if portfolio_hint == "proposed" and s.proposed_portfolio is None:
                s.proposed_portfolio = (await self.vtb_model.generate_portfolio(None)).get("data")

            # Если мы в режиме "сравнить на другом портфеле" — делаем пересчёт напрямую
            # (без повторного NLU), сохраняя те же настройки.
            if s.pending_compare_intent == "BACKTEST" and s.last_backtest_years:
                years = s.last_backtest_years
                result = await self.vtb_model.backtest(s.portfolio_id, years, "IMOEX")
                s.pending_compare_intent = None
                if not result.get("success"):
                    if result.get("error_code") == "insufficient_data":
                        return {"success": False, "intent": "BACKTEST", "reply": "Истории портфеля пока недостаточно для расчета. Попробуйте через пару месяцев.", "context": s.model_dump()}
                    return {"success": False, "intent": "BACKTEST", "reply": "Не удалось рассчитать бэктест. Попробуйте позже или выберите другой период", "context": s.model_dump()}

                m = result["data"]["metrics"]
                worst_date = m["portfolio"].get("worst_drawdown_date")
                worst_date_text = ""
                if worst_date:
                    try:
                        dt = datetime.fromisoformat(str(worst_date))
                        worst_date_text = dt.strftime("%m.%Y")
                    except ValueError:
                        worst_date_text = str(worst_date)
                return {
                    "success": True,
                    "intent": "BACKTEST",
                    "reply": f"Я проверил ваш портфель за последние {years} {years_word(years)}. Годовая доходность портфеля {(m['portfolio']['annual_return'] * 100):.1f}% (IMOEX: {(m['benchmark']['annual_return'] * 100):.1f}%). Максимальная просадка {(m['portfolio']['max_drawdown'] * 100):.1f}%{f' (пик просадки: {worst_date_text})' if worst_date_text else ''}. Коэффициент Шарпа {m['portfolio']['sharpe_ratio']}.",
                    "data": result["data"],
                    "portfolio": self._portfolio_for_session(s),
                    "actions": ["Задать другой период", "Сравнить с другим портфелем", "Что это значит?", "Оформить портфель"],
                    "context": s.model_dump(),
                }

            if s.pending_compare_intent == "SCENARIO" and s.last_scenario:
                t = s.last_scenario.get("type")
                v = s.last_scenario.get("value")
                if t and v is not None:
                    result = await self.vtb_model.scenario(s.portfolio_id, t, float(v))
                    s.pending_compare_intent = None
                    if not result.get("success"):
                        if result.get("error_code") == "unsupported_scenario":
                            return {"success": False, "intent": "SCENARIO", "reply": "Этот сценарий пока недоступен. Могу показать рост ставки, падение индекса или ослабление рубля.", "actions": ["Рост ставки", "Падение индекса", "Ослабление рубля"], "context": s.model_dump()}
                        return {"success": False, "intent": "SCENARIO", "reply": "Не удалось рассчитать сценарий. Попробуйте другую величину или обратитесь к менеджеру", "context": s.model_dump()}

                    return {
                        "success": True,
                        "intent": "SCENARIO",
                        "reply": (
                            f"Если ключевая ставка вырастет до {float(v):.1f}%, общий эффект по портфелю может составить {result['data']['total_impact_percent']}%."
                            if t == "rate_hike"
                            else (
                                f"Если индекс снизится на {float(v):.1f}%, общий эффект по портфелю может составить {result['data']['total_impact_percent']}%."
                                if t == "market_drop"
                                else f"Если рубль ослабнет на {float(v):.1f}%, общий эффект по портфелю может составить {result['data']['total_impact_percent']}%."
                            )
                        ),
                        "data": result["data"],
                        "portfolio": self._portfolio_for_session(s),
                        "actions": ["Сравнить с другим портфелем", "Другой сценарий", "Что делать в этом случае?", "Защитить портфель", "Оформить портфель"],
                        "context": s.model_dump(),
                    }

        if s.pending_intent == "BACKTEST" and s.pending_backtest_years == 5 and is_yes(msg):
            msg = f"{msg} 5 лет"
        if s.pending_intent == "BACKTEST" and is_other_period(msg):
            return {"success": True, "intent": "BACKTEST", "reply": "Укажи период для бэктеста: например, 1 год, 3 года или 5 лет.", "actions": ["1 год", "3 года", "5 лет"], "context": s.model_dump()}

        # Реакция "перевести/сравнить на другом портфеле" без привязки к точной фразе.
        if "задать другой период" in mlow:
            s.pending_intent = "BACKTEST"
            s.pending_backtest_years = None
            return {"success": True, "intent": "BACKTEST", "reply": "Укажи период для бэктеста: 1 год, 3 года или 5 лет.", "actions": ["1 год", "3 года", "5 лет"], "context": s.model_dump()}
        compare_other_portfolio = (
            "другом портфел" in mlow
            or "на другом портфел" in mlow
            or "сравним другой портфел" in mlow
            or "сравнить другой портфел" in mlow
            or ("другой портфел" in mlow and "сравн" in mlow)
            or "сравнить с другим портфелем" in mlow
        )
        if compare_other_portfolio:
            if s.last_intent == "SCENARIO":
                if not s.last_scenario:
                    return {"success": True, "intent": "SCENARIO", "reply": "Сначала запустите сценарий, а затем я смогу сравнить его на другом портфеле.", "actions": ["Другой сценарий"], "context": s.model_dump()}
                s.pending_compare_intent = "SCENARIO"
                return {"success": True, "intent": "SCENARIO", "reply": "Хорошо, выбери портфель для сравнения: текущий или предложенный.", "actions": ["Текущий", "Предложенный"], "context": s.model_dump()}

            if not s.last_backtest_years:
                s.pending_intent = "BACKTEST"
                return {"success": True, "intent": "BACKTEST", "reply": "Сначала сделай бэктест (например, за 3 года), и я смогу сравнить с другим портфелем.", "actions": ["1 год", "3 года", "5 лет"], "context": s.model_dump()}

            s.pending_compare_intent = "BACKTEST"
            return {"success": True, "intent": "BACKTEST", "reply": "Хорошо, выбери портфель для сравнения: текущий или предложенный.", "actions": ["Текущий", "Предложенный"], "context": s.model_dump()}
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
            elif s.pending_intent in {"BACKTEST", "SCENARIO"} and (portfolio_hint is not None or years_hint is not None or scenario_type_hint is not None or scenario_value_hint is not None or is_yes(msg)):
                intent = s.pending_intent

        s.last_intent = intent

        if intent == "UNKNOWN":
            return {"success": True, "intent": intent, "reply": "Извините, я не понял. Вы хотите посмотреть историю портфеля (бэктест) или проверить его реакцию на сценарий (например, рост ставки)?", "actions": ["Бэктест", "Сценарий"], "context": s.model_dump()}

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
            result = await self.vtb_model.backtest(s.portfolio_id, years, "IMOEX")
            if not result.get("success"):
                if result.get("error_code") == "insufficient_data":
                    return {"success": False, "intent": intent, "reply": "Истории портфеля пока недостаточно для расчета. Попробуйте через пару месяцев.", "context": s.model_dump()}
                return {"success": False, "intent": intent, "reply": "Не удалось рассчитать бэктест. Попробуйте позже или выберите другой период", "context": s.model_dump()}
            m = result["data"]["metrics"]
            s.pending_intent = None
            s.pending_backtest_years = None
            s.last_backtest_years = years
            worst_date = m["portfolio"].get("worst_drawdown_date")
            worst_date_text = ""
            if worst_date:
                try:
                    dt = datetime.fromisoformat(str(worst_date))
                    worst_date_text = dt.strftime("%m.%Y")
                except ValueError:
                    worst_date_text = str(worst_date)
            return {
                "success": True,
                "intent": intent,
                "reply": f"Я проверил ваш портфель за последние {years} {years_word(years)}. Годовая доходность портфеля {(m['portfolio']['annual_return'] * 100):.1f}% (IMOEX: {(m['benchmark']['annual_return'] * 100):.1f}%). Максимальная просадка {(m['portfolio']['max_drawdown'] * 100):.1f}%{f' (пик просадки: {worst_date_text})' if worst_date_text else ''}. Коэффициент Шарпа {m['portfolio']['sharpe_ratio']}.",
                "data": result["data"],
                "portfolio": self._portfolio_for_session(s),
                "actions": ["Задать другой период", "Сравнить с другим портфелем", "Что это значит?", "Оформить портфель"],
                "context": s.model_dump(),
            }

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

        result = await self.vtb_model.scenario(s.portfolio_id, scenario_type, scenario_value)
        if not result.get("success"):
            if result.get("error_code") == "unsupported_scenario":
                return {"success": False, "intent": intent, "reply": "Этот сценарий пока недоступен. Могу показать рост ставки, падение индекса или ослабление рубля.", "actions": ["Рост ставки", "Падение индекса", "Ослабление рубля"], "context": s.model_dump()}
            return {"success": False, "intent": intent, "reply": "Не удалось рассчитать сценарий. Попробуйте другую величину или обратитесь к менеджеру", "context": s.model_dump()}

        s.last_scenario = {"type": scenario_type, "value": scenario_value}
        s.pending_intent = None
        s.pending_scenario_type = None
        s.pending_scenario_value = None
        return {
            "success": True,
            "intent": intent,
            "reply": (
                f"Если ключевая ставка вырастет до {scenario_value:.1f}%, общий эффект по портфелю может составить {result['data']['total_impact_percent']}%."
                if scenario_type == "rate_hike"
                else (
                    f"Если индекс снизится на {scenario_value:.1f}%, общий эффект по портфелю может составить {result['data']['total_impact_percent']}%."
                    if scenario_type == "market_drop"
                    else f"Если рубль ослабнет на {scenario_value:.1f}%, общий эффект по портфелю может составить {result['data']['total_impact_percent']}%."
                )
            ),
            "data": result["data"],
            "portfolio": self._portfolio_for_session(s),
            "actions": ["Сравнить с другим портфелем", "Другой сценарий", "Что делать в этом случае?", "Защитить портфель", "Оформить портфель"],
            "context": s.model_dump(),
        }

