import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from .asset_llm import ASSET_DISCLAIMER, AssetLlmClient
from .asset_policy import check_asset_type_supported, check_recent_news_required
from .asset_stabilizer import stabilize_passport
from .asset_text import sanitize_factors, strip_citation_markers
from .clients import ExternalApiClient
from .metric_format import normalize_metric_values
from .metric_values import is_concrete_metric
from .official_sources import OfficialDataCollector
from .product_metrics import metrics_labels_for_kind, metrics_keys, normalize_key_metrics
from .product_reference import is_stable_kind, resolve_product_id, uses_reference_metrics_without_parser
from .products import product_by_id, product_by_name
from .source_validator import candidate_limit, filter_display_sources, select_reachable_sources

_SUMMARY_MAX_CHARS = 130
_SUMMARY_MAX_SENTENCES = 2
_FACTOR_MAX_ITEMS = 3
_FACTOR_MAX_CHARS = 100
_FACTOR_BULLET_PREFIX_RE = re.compile(r"^[-•*]\s*")


def _clean_text_list(items: List[Any]) -> List[Any]:
    return [strip_citation_markers(x) if isinstance(x, str) else x for x in items]


def _truncate_text(text: str, max_len: int) -> str:
    t = text.strip()
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1]
    for sep in (". ", "! ", "? ", "; "):
        idx = cut.rfind(sep)
        if idx >= int(max_len * 0.55):
            return cut[: idx + 1].strip()
    return cut.rstrip(" ,;—-") + "…"


def _first_sentences(text: str, max_sentences: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    picked = [p.strip() for p in parts if p.strip()][:max_sentences]
    if not picked:
        return text.strip()
    out = " ".join(picked)
    if out and out[-1] not in ".!?":
        out += "."
    return out


def _compact_summary(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = strip_citation_markers(text)
    short = _first_sentences(cleaned, _SUMMARY_MAX_SENTENCES)
    return _truncate_text(short, _SUMMARY_MAX_CHARS)


def _compact_factors(items: List[Any]) -> List[str]:
    out: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        line = _FACTOR_BULLET_PREFIX_RE.sub("", strip_citation_markers(item)).strip()
        if not line:
            continue
        out.append(_truncate_text(line, _FACTOR_MAX_CHARS))
        if len(out) >= _FACTOR_MAX_ITEMS:
            break
    return out


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source_url(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("url") or "").strip()
    return ""


def _official_display_sources(
    official_sources: List[Any],
    *,
    product_id: str | None = None,
    limit: int = 3,
) -> List[Any]:
    """Только URL из белого списка — карточки инструментов, без generic/home/API."""
    ranked = _top_sources(official_sources, limit=candidate_limit())
    return filter_display_sources(ranked, product_id=product_id)[:limit]


def _merge_key_metrics(
    official_metrics: Dict[str, Any],
    llm_metrics_raw: Any,
    asset_type: str,
) -> Dict[str, Any]:
    _empty_tokens = {"unknown", "нет данных", "н/д", "n/a", "-", "—", "null", ""}
    merged = normalize_key_metrics(official_metrics, asset_type)
    llm_part = normalize_key_metrics(llm_metrics_raw, asset_type)
    for key, val in llm_part.items():
        if merged.get(key) is not None:
            continue
        if val is None:
            continue
        if isinstance(val, str) and val.strip().lower() in _empty_tokens:
            continue
        merged[key] = val
    return merged


def _parse_iso_date(value: str) -> datetime | None:
    try:
        # Accept both date and datetime forms from LLM.
        if len(value) == 10:
            return datetime.fromisoformat(f"{value}T00:00:00+00:00")
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _source_score(item: Any) -> float:
    # String URLs are allowed, but structured dict sources are considered more informative.
    if isinstance(item, str):
        try:
            host = urlparse(item).netloc.lower()
        except Exception:
            host = ""
        score = 10.0
        if any(d in host for d in ("moex.com", "cbr.ru", "vtb.ru", "e-disclosure.ru")):
            score += 8.0
        return score

    if not isinstance(item, dict):
        return -1.0

    score = 20.0
    source_type = str(item.get("type") or "").lower()
    if source_type in {"official", "regulator", "issuer_report", "exchange", "reporting"}:
        score += 10.0
    elif source_type in {"news", "media"}:
        score += 3.0

    url = str(item.get("url") or "")
    host = urlparse(url).netloc.lower() if url else ""
    if any(d in host for d in ("moex.com", "cbr.ru", "vtb.ru", "e-disclosure.ru")):
        score += 8.0

    updated_raw = str(item.get("updatedAt") or item.get("updated_at") or "").strip()
    if updated_raw:
        dt = _parse_iso_date(updated_raw)
        if dt:
            age_days = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).days
            # Fresher sources get slightly higher score.
            if age_days <= 7:
                score += 6.0
            elif age_days <= 30:
                score += 4.0
            elif age_days <= 90:
                score += 2.0
    return score


def _top_sources(items: List[Any], limit: int) -> List[Any]:
    ranked = sorted(items, key=_source_score, reverse=True)
    return ranked[:limit]


def _metric_has_value(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        s = val.strip().lower()
        return bool(s) and s not in {
            "unknown",
            "нет данных",
            "н/д",
            "n/a",
            "-",
            "—",
            "null",
        }
    return True


def _analysis_is_viable(
    raw: Dict[str, Any],
    ranked_sources: List[Any],
    asset_type: str,
    official_metrics: Dict[str, Any],
) -> bool:
    if str(raw.get("summary") or "").strip():
        return True
    pos = _as_list(raw.get("positive_factors"))
    neg = _as_list(raw.get("negative_factors"))
    if any(isinstance(x, str) and x.strip() for x in pos + neg):
        return True
    if ranked_sources:
        return True
    merged = _merge_key_metrics(official_metrics, raw.get("key_metrics"), asset_type)
    return any(_metric_has_value(v) for v in merged.values())


def _official_parsers_verified(coverage: Dict[str, bool], asset_type: str) -> bool:
    k = (asset_type or "").strip().lower()
    if k == "bpif":
        return bool(coverage.get("investing") or coverage.get("moex"))
    if k in ("opif", "zpif"):
        return bool(coverage.get("investing"))
    if k == "precious_metal":
        return bool(coverage.get("investing") or coverage.get("cbr"))
    return bool(coverage.get("moex") or coverage.get("vtb_card"))


def _merge_stable_precious_metrics(
    official_metrics: Dict[str, Any],
    llm_metrics: Dict[str, Any],
    reference_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Цена/доходность — из ЦБ; банковские условия — из эталона, без LLM-цифр."""
    out: Dict[str, Any] = {}
    ref = reference_metrics or {}
    llm = llm_metrics or {}
    official = official_metrics or {}

    for key in ("bid_price", "ask_price", "bank_spread", "period_change_pct"):
        for bucket in (official, llm, ref):
            val = bucket.get(key)
            if is_concrete_metric(val):
                out[key] = val
                break

    for key in ("daily_range",):
        for bucket in (ref, official, llm):
            val = bucket.get(key)
            if val is not None and str(val).strip():
                out[key] = val
                break

    return out


def _metrics_from_official_and_reference(
    official_metrics: Dict[str, Any],
    reference_metrics: Dict[str, Any],
    asset_type: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    ref = reference_metrics or {}
    for key in metrics_keys(asset_type):
        off_val = official_metrics.get(key)
        if is_concrete_metric(off_val):
            out[key] = off_val
        elif ref.get(key):
            out[key] = ref[key]
        else:
            out[key] = None
    return normalize_metric_values(out, asset_type)


def _llm_failure_response(exc: Exception) -> Dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 402:
            message = (
                "Не удалось подготовить анализ. На API-ключе aitunnel закончился баланс "
                "(402 Payment Required). Пополните счёт или укажите другой LLM_PROVIDER."
            )
        elif code in (401, 403):
            message = "Не удалось подготовить анализ. Проверьте LLM_API_KEY и доступ к провайдеру."
        elif code == 429:
            message = "Не удалось подготовить анализ. Превышен лимит запросов к ИИ, попробуйте позже."
        elif code >= 500:
            message = "Не удалось подготовить анализ. Сервис ИИ временно недоступен, попробуйте позже."
        else:
            message = "Не удалось подготовить анализ. Попробуйте позже"
        return {"success": False, "message": message, "error_code": f"llm_http_{code}"}

    if isinstance(exc, HTTPException):
        detail = exc.detail
        message = detail if isinstance(detail, str) else "Не удалось подготовить анализ. Попробуйте позже"
        return {"success": False, "message": message, "error_code": "llm_error"}

    if isinstance(exc, httpx.TimeoutException):
        return {
            "success": False,
            "message": (
                "Не удалось подготовить анализ. Истекло время ожидания ответа ИИ "
                "(модели deep-research отвечают долго). Увеличьте LLM_TIMEOUT_SEC в .env "
                "(например 600) и перезапустите сервер."
            ),
            "error_code": "llm_timeout",
        }

    if isinstance(exc, httpx.HTTPError):
        return {
            "success": False,
            "message": "Не удалось подготовить анализ. Ошибка соединения с сервисом ИИ, попробуйте позже.",
            "error_code": "llm_network",
        }

    return {
        "success": False,
        "message": "Не удалось подготовить анализ. Попробуйте позже",
        "error_code": "llm_unknown",
    }


class AssetService:
    def __init__(self, llm: AssetLlmClient, api: ExternalApiClient | None = None) -> None:
        self.llm = llm
        self.official = OfficialDataCollector(api or ExternalApiClient())

    async def analyze(self, asset_id: str, asset_type: str, period_days: int) -> Dict[str, Any]:
        unsupported = check_asset_type_supported(asset_type)
        if unsupported:
            return unsupported

        official = await self.official.collect(asset_id, asset_type, period_days)
        stable_profile = self.official.stable_profile_for(asset_id, asset_type)
        product = product_by_name(asset_id) or product_by_id(asset_id)
        catalog_product_id = resolve_product_id(asset_id, product)
        official_ctx = {
            "prefilled_key_metrics": official.metrics,
            "context_text": official.context_text(),
            "coverage": official.coverage,
            "source_errors": official.errors,
            "stable_profile": stable_profile,
            "search_queries": official.search_queries,
        }

        try:
            raw = await self.llm.analyze_asset(asset_id, asset_type, period_days, official_ctx)
        except (httpx.HTTPStatusError, httpx.HTTPError, HTTPException) as exc:
            return _llm_failure_response(exc)
        except Exception as exc:
            return _llm_failure_response(exc)

        raw.pop("sources", None)

        no_news = check_recent_news_required(raw, asset_type, stable_profile, official.coverage)
        if no_news:
            return no_news

        source_candidates = _official_display_sources(
            official.sources,
            product_id=catalog_product_id,
            limit=candidate_limit(),
        )
        viable = _analysis_is_viable(raw, source_candidates, asset_type, official.metrics) or bool(
            stable_profile.get("summary")
        )

        # Отказ только если нет ни текста анализа, ни метрик (официальных + LLM), ни источников.
        if not viable:
            return {
                "success": False,
                "message": "По этому инструменту пока недостаточно данных для ИИ-анализа",
                "error_code": "no_data_overall",
            }

        ranked_sources = await select_reachable_sources(
            source_candidates,
            limit=3,
            product_id=catalog_product_id,
        )
        ranked_sources = [
            s
            for s in ranked_sources
            if isinstance(s, dict)
            and str(s.get("parser_origin") or "").lower() in {"moex", "investing", "cbr", "vtb", "wealthim"}
        ]

        merged_metrics = normalize_metric_values(
            _merge_key_metrics(official.metrics, raw.get("key_metrics"), asset_type),
            asset_type,
        )
        parsers_verified = _official_parsers_verified(official.coverage, asset_type)
        ref_metrics = stable_profile.get("metrics") or {}

        if is_stable_kind(asset_type) and asset_type == "precious_metal":
            merged_metrics = normalize_metric_values(
                _merge_stable_precious_metrics(official.metrics, merged_metrics, ref_metrics),
                asset_type,
            )
            missing_keys = []
            compact_summary = _compact_summary(stable_profile.get("summary") or raw.get("summary"))
            compact_pos = _compact_factors(
                sanitize_factors(_clean_text_list(_as_list(stable_profile.get("positive_factors") or raw.get("positive_factors"))))
            )
            compact_neg = _compact_factors(
                sanitize_factors(_clean_text_list(_as_list(stable_profile.get("negative_factors") or raw.get("negative_factors"))))
            )
        elif uses_reference_metrics_without_parser(asset_type) and not parsers_verified:
            merged_metrics = _metrics_from_official_and_reference(
                official.metrics,
                ref_metrics,
                asset_type,
            )
            missing_keys: List[str] = []
            compact_summary = _compact_summary(stable_profile.get("summary") or raw.get("summary"))
            compact_pos = _compact_factors(
                sanitize_factors(_clean_text_list(_as_list(stable_profile.get("positive_factors") or raw.get("positive_factors"))))
            )
            compact_neg = _compact_factors(
                sanitize_factors(_clean_text_list(_as_list(stable_profile.get("negative_factors") or raw.get("negative_factors"))))
            )
        else:
            missing_keys = [k for k, v in merged_metrics.items() if not is_concrete_metric(v)]
            compact_summary = _compact_summary(raw.get("summary"))
            compact_pos = _compact_factors(
                sanitize_factors(_clean_text_list(_as_list(raw.get("positive_factors"))))
            )
            compact_neg = _compact_factors(
                sanitize_factors(_clean_text_list(_as_list(raw.get("negative_factors"))))
            )

        if len(missing_keys) >= 2:
            try:
                gap_metrics = await self.llm.fill_metric_gaps(
                    asset_id,
                    asset_type,
                    merged_metrics,
                    missing_keys,
                    official_ctx,
                )
                if gap_metrics:
                    patched = dict(raw.get("key_metrics") or {})
                    patched.update(gap_metrics)
                    merged_metrics = normalize_metric_values(
                        _merge_key_metrics(official.metrics, patched, asset_type),
                        asset_type,
                    )
            except Exception:
                pass

        stable = stabilize_passport(
            asset_id=asset_id,
            asset_type=asset_type,
            raw=raw,
            official_metrics=official.metrics,
            merged_metrics=merged_metrics,
            summary=compact_summary,
            positive_factors=compact_pos,
            negative_factors=compact_neg,
        )

        data: Dict[str, Any] = {
            "asset_name": strip_citation_markers(stable["asset_name"]),
            "ticker": strip_citation_markers(stable.get("ticker")),
            "asset_type": asset_type,
            "summary": _compact_summary(stable["summary"]),
            "positive_factors": _compact_factors(stable["positive_factors"]),
            "negative_factors": _compact_factors(stable["negative_factors"]),
            "key_metrics": stable["key_metrics"],
            "key_metrics_labels": metrics_labels_for_kind(asset_type),
            "sources": ranked_sources,
            "data_sources_coverage": official.coverage,
            "updated_at": raw.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            "disclaimer": ASSET_DISCLAIMER,
        }
        return {"success": True, "data": data}
