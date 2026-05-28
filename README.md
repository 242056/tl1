# VTB MVP (Python)

Backend полностью на Python (FastAPI), frontend статический (`frontend/src/index.html`).

## Что реализовано
- `POST /api/chat` — Диалоговое окно по ТЗ Ксюши (BACKTEST/SCENARIO, контекст, fallback)
- `POST /api/portfolio/generate` — генерация предложенного портфеля (заглушки модели ВТБ)
- `GET /api/products/universe` — вселенная продуктов ВТБ для UI и тестов
- `POST /api/asset-analysis` — Анти-Гугл через Perplexity
- `GET /api/health` — healthcheck
- `GET /api/config-check` — проверка конфигурации

## Ключевой принцип
- Модель ВТБ: заглушки (портфель/backtest/scenario)
- Анти-Гугл: только `LLM_PROVIDER=perplexity`
- Источники в ответе пользователю: только из `citations` Perplexity

## Структура
- `python_backend/main.py` — точка входа FastAPI
- `python_backend/core/models.py` — pydantic-модели и типы
- `python_backend/core/config.py` — конфигурация и env
- `python_backend/core/nlu.py` — NLU/утилиты диалога
- `python_backend/core/products.py` — вселенная продуктов, тестовые портфели, сценарии
- `python_backend/core/clients.py` — клиенты интеграций и заглушки ВТБ-модели
- `python_backend/core/services.py` — бизнес-логика диалога и анти-гугл
- `python_backend/core/api.py` — API-роуты
- `frontend/src/index.html` — UI
- `.env.example` — обязательные переменные
- `requirements.txt` — зависимости Python

## Установка
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Конфигурация
1. Скопируй `.env.example` в `.env`
2. Заполни:
- `LLM_PROVIDER=perplexity`
- `LLM_BASE_URL=https://api.perplexity.ai`
- `LLM_API_KEY=...`
- `LLM_MODEL=sonar`
- `LLM_ENDPOINT=/chat/completions`

## Запуск
```bash
uvicorn python_backend.main:app --host 0.0.0.0 --port ${PORT:-3000}
```

Открыть: `http://localhost:3000`

## Быстрая проверка конфига
```bash
curl -sS http://localhost:3000/api/config-check
```

## Примеры вызовов

### Диалог
```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"s1","message":"покажи бэктест текущего портфеля за 3 года"}'
```

### Генерация портфеля
```bash
curl -X POST http://localhost:3000/api/portfolio/generate \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"s1","variant":1}'
```

### Анти-Гугл
```bash
curl -X POST http://localhost:3000/api/asset-analysis \
  -H "Content-Type: application/json" \
  -d '{"asset_id":"БПИФ «Индекс МосБиржи»","asset_type":"bpif","user_id":"current","period_days":30}'
```

## Вселенная продуктов
Заглушки портфеля, сценариев и анти-гугла используют продукты ВТБ (БПИФ, ОПИФ, ЗПИФ, вклады, ИСЖ/НСЖ, драгметаллы, Интеллект, ПДС и др.) — см. `core/products.py`.

Тестовый **текущий** портфель (2,5 млн ₽): БПИФ «Ликвидность», «Российские облигации», «Индекс МосБиржи», «Золото.Биржевой», Накопительный ВТБ Счет, ОПИФ «ВИМ - Сбережения».

```bash
curl -sS http://localhost:3000/api/products/universe
```

## Что на заглушках
- Генерация портфеля модели ВТБ (`/api/portfolio/generate`) — 5 вариантов из вселенной продуктов
- Backtest и Scenario для диалогового окна — deterministic stub-логика

### Пример ответа `/api/portfolio/generate` (заглушка ВТБ)
Заглушка модели возвращает портфель в поле `data`. Пример структуры:

```json
{
  "portfolioId": "portfolio_784512",
  "portfolioName": "Сбалансированный мультипродукт",
  "generatedAt": "2026-05-24T12:45:00Z",
  "currency": "RUB",
  "investmentHorizon": "5_years",
  "placementAmount": 3000000,
  "expectedReturn": {
    "target": 14.5,
    "inflationAdjusted": true
  },
  "riskProfile": "medium",
  "summary": {
    "description": "Портфель сформирован с учетом долгосрочного роста капитала, умеренной допустимой просадки и необходимости сохранить часть средств в ликвидных инструментах."
  },
  "products": [
    {
      "productId": "bpif_ru_bonds",
      "productName": "БПИФ «Российские облигации»",
      "category": "Фонды",
      "kind": "bpif",
      "weight": 0.35,
      "amount": 1050000
    },
    {
      "productId": "bpif_moex_index",
      "productName": "БПИФ «Индекс МосБиржи»",
      "category": "Фонды",
      "kind": "bpif",
      "weight": 0.25,
      "amount": 750000
    },
    {
      "productId": "bpif_liquidity",
      "productName": "БПИФ «Ликвидность»",
      "category": "Фонды",
      "kind": "bpif",
      "weight": 0.15,
      "amount": 450000
    },
    {
      "productId": "bpif_gold_exchange",
      "productName": "БПИФ «Золото.Биржевой»",
      "category": "Фонды",
      "kind": "bpif",
      "weight": 0.10,
      "amount": 300000
    },
    {
      "productId": "account_vtb",
      "productName": "Накопительный ВТБ Счет",
      "category": "Денежные продукты",
      "kind": "account",
      "weight": 0.10,
      "amount": 300000
    },
    {
      "productId": "opif_vim_save",
      "productName": "ОПИФ \"ВИМ - Сбережения\"",
      "category": "Фонды",
      "kind": "opif",
      "weight": 0.10,
      "amount": 300000
    }
  ],
  "goal": {
    "enabled": true,
    "goalName": "Образование ребенка",
    "targetAmount": 5000000,
    "currentInvestment": 1500000,
    "investmentTermYears": 10,
    "goalAchievable": false,
    "recommendedMonthlyContribution": 25000
  },
  "rebalance": {
    "enabled": true,
    "frequency": "quarterly"
  }
}
```
