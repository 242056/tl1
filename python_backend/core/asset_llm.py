import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .clients import ExternalApiClient
from .config import llm_timeout_sec, required_env
from .product_metrics import metrics_schema_for_prompt, metrics_keys

log = logging.getLogger("vtb.asset_llm")

# Обязательный дисклеймер по ТЗ (не аналитические данные).
ASSET_DISCLAIMER = (
    "Информация сформирована автоматически на основе доступных данных и не является "
    "индивидуальной инвестиционной рекомендацией. Перед совершением сделки оцените риски "
    "самостоятельно или обратитесь к аналитикам ВТБ."
)


class AssetLlmClient:
    def __init__(self, api: ExternalApiClient) -> None:
        self.api = api

    def _extract_json(self, text: str) -> Dict[str, Any]:
        raw = text.strip()
        try:
            return json.loads(raw)
        except Exception:
            pass
        l, r = raw.find("{"), raw.rfind("}")
        if l != -1 and r != -1 and r > l:
            return json.loads(raw[l : r + 1])
        raise HTTPException(status_code=502, detail="LLM не вернула JSON")

    async def analyze_asset(
        self,
        asset_id: str,
        asset_type: str,
        period_days: int,
        official_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        base = required_env("LLM_BASE_URL")
        token = required_env("LLM_API_KEY")
        model = required_env("LLM_MODEL")
        endpoint = os.getenv("LLM_ENDPOINT", "/chat/completions").strip() or "/chat/completions"
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        metrics_schema = metrics_schema_for_prompt(asset_type)
        prompt = {
            "task": "Сформируй лаконичный математический паспорт продукта ВТБ на русском языке.",
            "product_kind": asset_type,
            "output_style": {
                "tone": "нейтральный, аналитический, без воды и повторов",
                "summary": "1–2 коротких предложения, максимум 130 символов, только главный вывод без деталей расчёта индекса и расписания",
                "positive_factors": "ровно 3 пункта, каждый до 100 символов — только качественный драйвер (макро, регуляторика, спрос)",
                "negative_factors": "ровно 3 пункта, каждый до 100 символов — только качественный риск (без цифр и метрик)",
                "format": "каждый пункт — одно короткое предложение без вводных «следует отметить», «важно понимать»",
            },
            "rules": [
                "Опирайся только на официальные источники, биржевые данные и надежные новости.",
                "Игнорируй форумы, соцсети и слухи.",
                "Не выдумывай числовые показатели. unknown/null — только если в источниках действительно нет ни числа, ни однозначного качественного факта.",
                "Сначала извлеки факты из источников, затем заполни key_metrics. Не пиши «нет данных», если факт есть в другой формулировке (0%, «не выплачивает», «продавать» — это данные).",
                f"В key_metrics заполни РОВНО 5 полей для типа {asset_type} (без других ключей): {list(metrics_schema.keys())}.",
                "Числа указывай как в источнике (проценты можно строкой «52%» или числом 0.52 для долей — будь последователен).",
                "Не ставь has_any_data: false для продуктов из каталога ВТБ только из-за отсутствия биржевого тикера.",
                "ОПИФ и ЗПИФ УК ВИМ: ищи данные на сайте УК, e-disclosure, открытых отчётах фонда; null в метриках — только если число не найдено.",
                "Не давай прямых рекомендаций покупать/продавать — нейтральные формулировки.",
                "ЗАПРЕЩЕНО дублировать key_metrics в positive_factors/negative_factors: никаких %, СЧА, TER, доходности, комиссий, альфы, цены пая.",
                "Не вставляй ссылочные метки [1], [2], [5] ни в summary, ни в key_metrics, ни в факторы — источники только в sources.",
                "В sources укажи реальные URL и человекочитаемые title для каждого источника, который использовал.",
            ],
            "schema": {
                "asset_name": "string — полное наименование продукта (как в линейке ВТБ)",
                "ticker": "string — внутренний код или краткий идентификатор продукта (если есть)",
                "summary": "string (1–2 предложения, ≤130 символов)",
                "positive_factors": ["string (ровно 3 пункта, ≤100 символов каждый)"],
                "negative_factors": ["string (ровно 3 пункта, ≤100 символов каждый)"],
                "key_metrics": metrics_schema,
                "data_status": {
                    "has_any_data": "boolean — true, если есть summary, факторы или хотя бы 2 заполненных key_metrics; для продуктов каталога ВТБ (ОПИФ, ЗПИФ, страхование, вклады) ставь true при любой публичной информации об УК/продукте",
                    "has_recent_30d_data": "boolean — ставь true, если сформированы summary/факторы/метрики/источники; false только если анализ полностью невозможен",
                },
                "sources": [
                    {
                        "title": "string",
                        "url": "string",
                        "type": "string (опционально)",
                        "updatedAt": "string ISO date (опционально)",
                    }
                ],
                "updated_at": "string ISO 8601 — момент актуальности сводки по твоей оценке",
            },
            "asset_id": asset_id,
            "asset_type": asset_type,
            "period_days": period_days,
        }
        if official_context:
            prompt["verified_official_data"] = official_context
            if official_context.get("prefilled_key_metrics"):
                prompt["rules"].append(
                    "Поле prefilled_key_metrics уже заполнено официальными источниками — скопируй в key_metrics без изменений; дополняй только null."
                )
            if official_context.get("context_text"):
                prompt["rules"].append(
                    "Используй verified_official_data.context_text как приоритетные факты; строка «Каталог ВТБ» — точное имя продукта для поиска."
                )
            if official_context.get("search_queries"):
                prompt["rules"].append(
                    "Обязательно выполни поиск по verified_official_data.search_queries и recommended_sources."
                )
            stable = official_context.get("stable_profile") or {}
            if stable.get("stable_kind"):
                prompt["deterministic_mode"] = True
                prompt["rules"].extend(
                    [
                        "deterministic_mode: summary и факторы будут взяты из stable_profile на сервере — не трать на них усилия.",
                        "Главная задача: заполнить key_metrics — для каждого null в prefilled_key_metrics найди значение на vtb.ru / cbr.ru / viminvest.ru.",
                        "Не оставляй null, если на официальном сайте есть число, процент, срок или сумма.",
                        "Добавь 1–3 реальных URL в sources.",
                    ]
                )
        body: Dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты инвестиционный аналитический помощник ВТБ. Верни только один JSON-объект по схеме. "
                        "Пиши максимально кратко и стабильно: фиксированная структура, без лишних деталей. "
                        "summary — 1–2 предложения и не длиннее 130 символов; positive_factors и negative_factors — по 3 коротких пункта. "
                        "key_metrics — ровно 5 полей по product_kind. "
                        "positive/negative — только качественные тезисы без цифр из метрик."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0")),
        }
        seed_raw = os.getenv("LLM_SEED", "").strip()
        if seed_raw:
            try:
                body["seed"] = int(seed_raw)
            except ValueError:
                pass
        llm_timeout = llm_timeout_sec()
        log.info("LLM request timeout=%ss model=%s", llm_timeout, model)
        resp = await self.api.post(
            f"{base.rstrip('/')}{endpoint}",
            body,
            token,
            timeout=llm_timeout,
        )

        text = None
        choices = resp.get("choices") if isinstance(resp, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict):
                    text = msg.get("content")
        if not text:
            raise HTTPException(status_code=502, detail="LLM не вернула текст ответа")

        analysis = self._extract_json(text)
        if not isinstance(analysis, dict):
            raise HTTPException(status_code=502, detail="LLM вернула некорректный JSON")

        log.info("Asset analysis keys: %s", list(analysis.keys()))
        return analysis

    async def fill_metric_gaps(
        self,
        asset_id: str,
        asset_type: str,
        known_metrics: Dict[str, Any],
        missing_keys: List[str],
        official_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not missing_keys:
            return {}

        base = required_env("LLM_BASE_URL")
        token = required_env("LLM_API_KEY")
        model = os.getenv("LLM_GAP_MODEL", os.getenv("LLM_MODEL", "")).strip() or required_env("LLM_MODEL")
        endpoint = os.getenv("LLM_ENDPOINT", "/chat/completions").strip() or "/chat/completions"
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        schema = {k: metrics_schema_for_prompt(asset_type).get(k, "") for k in missing_keys}
        prompt = {
            "task": "Найди в официальных источниках значения ТОЛЬКО для перечисленных пустых полей key_metrics.",
            "asset_id": asset_id,
            "asset_type": asset_type,
            "missing_keys": missing_keys,
            "already_known_metrics": known_metrics,
            "key_metrics_schema": schema,
            "rules": [
                "Верни JSON вида {\"key_metrics\": {...}} только с ключами из missing_keys.",
                "Используй search_queries и recommended_sources из verified_official_data.",
                "Приоритет: vtb.ru, viminvest.ru, e-disclosure.ru, cbr.ru.",
                "Если точного числа нет — null, не выдумывай.",
                "Проценты строкой с символом %, суммы с ₽.",
            ],
        }
        if official_context:
            prompt["verified_official_data"] = official_context

        body: Dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты помощник по извлечению числовых метрик. Верни только JSON с key_metrics.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "temperature": 0,
        }
        resp = await self.api.post(
            f"{base.rstrip('/')}{endpoint}",
            body,
            token,
            timeout=llm_timeout_sec(),
        )
        text = None
        choices = resp.get("choices") if isinstance(resp, dict) else None
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict):
                text = msg.get("content")
        if not text:
            return {}
        try:
            parsed = self._extract_json(text)
        except Exception:
            return {}
        km = parsed.get("key_metrics") if isinstance(parsed, dict) else None
        if not isinstance(km, dict):
            return {}
        allowed = set(metrics_keys(asset_type))
        return {k: v for k, v in km.items() if k in allowed and k in missing_keys}
