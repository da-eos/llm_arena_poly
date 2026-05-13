# Промт для Claude Code: MVP «LLM Arena × Polymarket»

> Скопируй этот файл целиком в первое сообщение Claude Code. Дальше можно двигаться по фазам — давать ему сообщения вида «делаем Phase 2», и он будет идти строго в рамках уже согласованной архитектуры.

---

## КОНТЕКСТ ПРОЕКТА

Мы делаем MVP сервиса «LLM Arena на базе Polymarket». Идея:

1. Забираем трендовые события с Polymarket (через их публичный Gamma API).
2. По каждому событию просим несколько LLM (Claude, GPT, Gemini, опционально через OpenRouter) дать прогноз вероятности исхода.
3. Сохраняем прогнозы, ждём резолва события на Polymarket, считаем метрики (Brier score, log loss, P&L на условные $100).
4. Показываем во фронте: список событий, прогнозы моделей по каждому, leaderboard моделей.

Это именно MVP. Цель — рабочий end-to-end pipeline в Docker, без auth, без SSL, без production-grade нюансов. Деплоить будем на своём VPS просто `docker compose up`.

---

## ТЕХНОЛОГИЧЕСКИЙ СТЕК (фиксируем сразу, не отклоняйся)

**Backend:**
- Python 3.12
- FastAPI
- SQLAlchemy 2.0 (async, с `asyncpg`)
- Alembic для миграций (autogenerate)
- PostgreSQL 16
- httpx (async) для Polymarket и LLM API
- APScheduler (AsyncIOScheduler) для периодических задач
- pydantic-settings для конфига из `.env`
- uv как пакетный менеджер (быстрее poetry)
- ruff + mypy для линтинга

**Frontend:**
- Vite + React 18 + TypeScript
- TanStack Query для запросов к API
- Tailwind CSS для стилей
- shadcn/ui для готовых компонентов (минимум кастомного CSS)
- Recharts для графиков leaderboard

**Инфра:**
- Docker + docker-compose
- Контейнеры: `postgres`, `backend`, `frontend` (nginx + статика React)
- Без SSL, без reverse proxy сверху, порты наружу напрямую
- Все секреты через `.env`, в репо `.env.example`

**LLM провайдеры (всё через async httpx, без официальных SDK — чтоб контролировать запросы):**
- Anthropic Claude
- OpenAI GPT
- Google Gemini
- OpenRouter (как универсальный fallback / способ дёргать модели, для которых нет ключа)

---

## ОБЩИЕ ПРАВИЛА

- Структура репо: монорепа, на верхнем уровне `backend/`, `frontend/`, `docker/`, `docker-compose.yml`, `Makefile`, `.env.example`, `README.md`.
- Каждая фаза должна заканчиваться рабочим состоянием: `docker compose up` поднимает то, что уже сделано, без ошибок.
- В каждом коммите писать осмысленный message: `phase-N: краткое описание`.
- Не добавлять зависимости, которых нет в стеке выше, без явного спроса.
- Любые непонятные архитектурные развилки — спрашивать у меня, не угадывать.
- Не писать README/доки до Phase 8, не тратить токены на документацию посреди разработки.
- Тесты: на MVP — только smoke-тесты ключевых сервисов (pytest + httpx.AsyncClient), без 100% coverage.
- Все async — реально async, никаких blocking вызовов в event loop.

---

## ФАЗЫ

### Phase 0 — Скелет репозитория и инфра

**Цель:** `docker compose up` поднимает пустой backend (FastAPI с `/health`), пустой frontend (React «Hello world»), и Postgres.

Задачи:
1. Инициализировать монорепу со структурой выше.
2. `backend/`: `pyproject.toml` (uv), FastAPI app с одним эндпоинтом `GET /health` → `{"status": "ok"}`, конфиг через pydantic-settings, подключение к Postgres через SQLAlchemy async (создать `engine`, `async_session_factory`, проверить коннект на старте).
3. `backend/alembic/`: инициализировать Alembic, настроить `env.py` так, чтобы он работал с async SQLAlchemy и брал URL из `Settings`.
4. `frontend/`: Vite + React + TS + Tailwind + shadcn/ui (init), одна страница «LLM Arena» с заглушкой.
5. `docker/`: `Dockerfile.backend` (multi-stage с uv), `Dockerfile.frontend` (multi-stage: build → nginx).
6. `docker-compose.yml`: сервисы `postgres` (с volume), `backend` (depends_on postgres, прогоняет `alembic upgrade head` перед стартом), `frontend`.
7. `Makefile`: цели `up`, `down`, `migrate`, `revision name=...`, `logs`, `psql`.
8. `.env.example` со всеми переменными, которые потребуются дальше (пустые значения).

**Definition of done:** `make up` → открывается фронт на `localhost:5173`, `curl localhost:8000/health` отвечает 200, в Postgres есть таблица `alembic_version`.

---

### Phase 1 — Модели данных и миграции

**Цель:** в БД есть все таблицы, нужные для дальнейшей работы. Никакой бизнес-логики ещё нет.

Сущности:
- `events` — события Polymarket. Поля: `id` (uuid), `polymarket_id` (unique), `slug`, `title`, `description`, `category`, `volume`, `liquidity`, `end_date`, `created_at`, `updated_at`, `is_tracked` (bool — следим ли мы за ним), `raw` (JSONB — сырой ответ Polymarket для отладки).
- `markets` — отдельные исходы внутри события (Polymarket events содержат N markets). Поля: `id`, `event_id` (FK), `polymarket_id`, `question`, `outcomes` (JSONB, обычно `["Yes","No"]`), `current_price` (float), `is_resolved` (bool), `resolved_outcome` (nullable string), `resolved_at` (nullable), `raw` (JSONB).
- `llm_models` — реестр моделей, доступных для прогнозов. Поля: `id`, `slug` (unique, например `claude-sonnet-4-6`), `provider` (enum: anthropic / openai / google / openrouter), `display_name`, `model_id_at_provider` (точная строка модели для API), `is_enabled`, `created_at`.
- `predictions` — прогнозы. Поля: `id`, `market_id` (FK), `llm_model_id` (FK), `predicted_probability_yes` (float 0..1), `reasoning` (text), `confidence` (float, 0..1, опционально), `prompt_used` (text), `raw_response` (JSONB), `latency_ms` (int), `cost_usd` (float, nullable), `created_at`. Уникальность: `(market_id, llm_model_id)` — один прогноз на пару (можно перезаписывать через upsert или хранить версии — для MVP просто один прогноз на пару).
- `scores` — посчитанные метрики после резолва. Поля: `id`, `prediction_id` (FK, unique), `brier_score` (float), `log_loss` (float), `pnl_demo_usd` (float), `was_correct` (bool), `created_at`.

Задачи:
1. Описать SQLAlchemy модели в `backend/app/models/`.
2. Сгенерировать первую миграцию `alembic revision --autogenerate -m "init schema"`.
3. Применить миграцию, проверить схему в psql.

**Definition of done:** `\dt` в psql показывает все 5 таблиц с правильными типами и FK.

---

### Phase 2 — Polymarket клиент и ingestion

**Цель:** есть рабочий сервис, который умеет тянуть трендовые события с Polymarket и складывать их в БД (upsert).

Задачи:
1. `backend/app/clients/polymarket.py` — async клиент на httpx:
   - `async def fetch_trending_events(limit: int = 50, min_volume: float = 10000) -> list[dict]` — дёргает `GET https://gamma-api.polymarket.com/events` с сортировкой по volume desc, фильтром по `closed=false` и `active=true`.
   - `async def fetch_event_by_id(polymarket_id: str) -> dict` — для обновления конкретного события.
   - Retry с экспоненциальным бэкоффом (tenacity) на 429 / 5xx, max 3 попытки.
   - Лимит по нашему мнению: не больше 5 req/s на этот клиент (semaphore).
2. `backend/app/services/ingestion.py`:
   - `async def sync_trending_events(session)` — тянет трендовые, делает upsert в `events` + связанные `markets`. Для уже существующих обновляет `volume`, `liquidity`, `current_price`, `is_resolved`, `resolved_outcome`. По умолчанию новым событиям ставит `is_tracked = False` (трекать будем явно или по правилу из Phase 3).
3. Эндпоинт `POST /admin/sync/polymarket` — ручной триггер `sync_trending_events`. Без auth (MVP).
4. Эндпоинты для просмотра:
   - `GET /events?tracked=true|false&limit=...&offset=...` — пагинированный список событий.
   - `GET /events/{event_id}` — событие с вложенными markets.
   - `POST /events/{event_id}/track` — выставить `is_tracked = True`.
   - `POST /events/{event_id}/untrack` — выставить `is_tracked = False`.

**Definition of done:** `curl -X POST localhost:8000/admin/sync/polymarket` → в БД появляются события и markets, `GET /events` их возвращает.

---

### Phase 3 — Scheduler

**Цель:** фоновые задачи запускаются автоматически по расписанию.

Задачи:
1. Подключить `APScheduler` (AsyncIOScheduler) в lifespan FastAPI приложения.
2. Зарегистрировать джобы (интервалы захардкодить пока в `Settings`):
   - `sync_trending_events_job` — каждые 30 минут: тянет трендовые, апдейтит БД.
   - `auto_track_top_events_job` — каждый час: автоматически ставит `is_tracked = True` топ-10 событиям по объёму, у которых `end_date` в будущем и которые ещё не tracked. (Это чтоб не приходилось руками тыкать в начале.)
   - `refresh_tracked_events_job` — каждые 15 минут: обходит все `is_tracked` события, обновляет их состояние через `fetch_event_by_id`, и если `is_resolved` стало `True` — триггерит расчёт scores (на этой фазе ещё нет scoring, поэтому просто логируем — расчёт добавим в Phase 6).
3. Эндпоинт `GET /admin/jobs` — список зарегистрированных джоб с next_run_time.

**Definition of done:** в логах видно, что джобы тикают по расписанию; через час после старта в БД появились события с `is_tracked=True` без ручных действий.

---

### Phase 4 — LLM провайдеры (абстракция)

**Цель:** есть единый интерфейс, через который можно дёрнуть любого провайдера и получить структурированный прогноз.

Задачи:
1. `backend/app/llm/base.py`:
   ```python
   class PredictionResult(BaseModel):
       probability_yes: float  # 0..1
       reasoning: str
       confidence: float | None = None
       raw_response: dict
       latency_ms: int
       cost_usd: float | None = None

   class LLMProvider(ABC):
       @abstractmethod
       async def predict(self, prompt: str, model_id: str) -> PredictionResult: ...
   ```
2. Реализации в `backend/app/llm/providers/`:
   - `anthropic.py` — Claude Messages API.
   - `openai.py` — OpenAI Chat Completions.
   - `google.py` — Gemini API.
   - `openrouter.py` — OpenRouter (тот же интерфейс, что OpenAI compat).
3. Все провайдеры читают ключ из `Settings`. Если ключ не задан — провайдер `disabled`, и попытка предикта возвращает явную ошибку.
4. У всех — структурированный вывод: просим модель ответить **строго JSON** вида `{"probability_yes": float, "reasoning": str, "confidence": float}`. Парсим и валидируем через pydantic. Если модель не отдала валидный JSON — одна повторная попытка с уточняющим хвостом промта, потом ошибка.
5. `backend/app/llm/registry.py` — маппинг `provider` (enum) → класс провайдера.
6. CLI-команда / эндпоинт `POST /admin/test-provider` с body `{"provider": "anthropic", "model_id": "...", "prompt": "..."}` — для дебага без всей цепочки.

**Definition of done:** `curl POST /admin/test-provider` с любым из 4 провайдеров возвращает валидный `PredictionResult` (при наличии ключа в `.env`).

---

### Phase 5 — Prediction engine

**Цель:** для каждого tracked события + каждой enabled модели генерируется один прогноз и пишется в БД.

Задачи:
1. `backend/app/services/prompting.py` — функция `build_prompt(event, market) -> str`. Промт должен включать: title, description, current_price (как индикатор консенсуса рынка), end_date, и инструкцию вернуть JSON. Не показывать модели current_price явно — она должна формировать мнение независимо. (Это важно для чистоты эксперимента.)
2. `backend/app/services/predictor.py`:
   - `async def predict_for_market(market_id, llm_model_id, force=False)` — берёт market + модель, строит промт, дёргает провайдера, сохраняет в `predictions`. Если прогноз уже есть и `force=False` — скип.
   - `async def run_predictions_for_tracked()` — обходит все `is_tracked` события + все `is_enabled` модели и зовёт `predict_for_market` где ещё нет. Параллелит через `asyncio.gather` с semaphore (например 5 одновременных вызовов LLM).
3. Джоба в scheduler: `predictions_job` — каждый час зовёт `run_predictions_for_tracked`.
4. Эндпоинты:
   - `POST /admin/predict-now` — синхронно запустить `run_predictions_for_tracked`.
   - `POST /predictions/market/{market_id}/model/{model_slug}` — точечно сгенерировать прогноз.
   - `GET /predictions?event_id=...&model_slug=...` — список с фильтрами.
   - `GET /events/{event_id}/predictions` — все прогнозы по событию, сгруппированные по моделям.
5. Сидинг: при первом старте, если таблица `llm_models` пустая, заполнить её базовым набором (Claude, GPT, Gemini, опц. парой моделей через OpenRouter) — прописать в Alembic data migration.

**Definition of done:** после `POST /admin/predict-now` в `predictions` появляются записи по всем tracked × enabled, в `/events/{id}/predictions` видно прогноз каждой модели с reasoning.

---

### Phase 6 — Resolution и scoring

**Цель:** когда событие резолвится, мы считаем метрики и обновляем leaderboard.

Задачи:
1. `backend/app/services/scoring.py`:
   - `def brier_score(p_yes: float, outcome: bool) -> float` — `(p - o)^2`.
   - `def log_loss(p_yes: float, outcome: bool) -> float` — стандартный, с клиппингом p в `[1e-6, 1-1e-6]`.
   - `def pnl_demo(p_yes: float, market_price: float, outcome: bool, stake: float = 100.0) -> float` — простая модель: модель «покупает» сторону, в которой её probability расходится с market price больше всего, ставит `stake` целиком, P&L = `stake * (1/price - 1)` если выиграла, `-stake` если проиграла.
   - `async def score_resolved_market(market_id)` — для каждой prediction по этому market создаёт/обновляет запись в `scores`.
2. Доработать `refresh_tracked_events_job` (из Phase 3): когда видим `is_resolved` впервые — зовём `score_resolved_market`.
3. Эндпоинты:
   - `GET /leaderboard?metric=brier|logloss|pnl&category=...` — возвращает модели, отсортированные по агрегированной метрике (среднее по всем scored предикшенам). Сразу с фильтром по категории.
   - `GET /models/{slug}/history` — все scored предикшены модели с метаданными для графика «накопленный P&L во времени».
4. Smoke test: создать в тестовой БД несколько фейковых predictions + резолвнутых markets, проверить что метрики считаются корректно.

**Definition of done:** `GET /leaderboard?metric=brier` возвращает осмысленный список после резолва хотя бы одного события.

---

### Phase 7 — Frontend

**Цель:** простой, но опрятный UI поверх готового API.

Страницы (React Router):
1. `/` — **Dashboard:**
   - Топ карточек: «Активных событий», «Прогнозов сделано», «Резолвнуто», «Лучшая модель за 7 дней».
   - Краткий leaderboard (топ-5 моделей по brier).
2. `/events` — **Список событий:**
   - Таблица (Grid.js или shadcn data-table): title, category, end_date, volume, current price, статус (tracked / resolved), кол-во предикшенов.
   - Фильтры: только tracked, по категории, поиск по title.
   - Кнопка «Sync now» → `POST /admin/sync/polymarket`.
3. `/events/:id` — **Детальная карточка события:**
   - Шапка с title, описанием, end_date, current price.
   - Таблица прогнозов: модель, predicted_probability_yes, разница с market price, reasoning (collapsible), latency, score (если резолвнуто).
   - Кнопка «Predict now» если ещё не все модели предсказали.
4. `/leaderboard` — **Leaderboard:**
   - Селектор метрики (brier / log loss / P&L) и категории.
   - Таблица + бар-чарт (Recharts).
   - При клике на модель — переход на `/models/:slug` с графиком накопленного P&L во времени (line chart).
5. `/models/:slug` — **История модели:**
   - График накопленного P&L.
   - Таблица последних предикшенов с результатами.

Технические правила:
- Все запросы через `TanStack Query` с базовым refetch interval 30s на dashboard.
- API base URL — из env `VITE_API_BASE_URL`.
- shadcn/ui компоненты по максимуму, кастомный CSS только если иначе никак.
- Никаких роутерных гвардов, auth, форм логина — для MVP всё открыто.

**Definition of done:** все 5 страниц работают, данные подтягиваются с backend, leaderboard рисует графики.

---

### Phase 8 — Финализация деплоя

Задачи:
1. `docker-compose.yml` довести до прод-готового вида:
   - Healthchecks для всех сервисов.
   - Restart policy: `unless-stopped`.
   - Volume для Postgres сохраняется между перезапусками.
   - Backend ждёт healthy postgres перед стартом.
   - Frontend (nginx) проксирует `/api` на `backend:8000` (чтобы фронту не нужно знать о CORS).
2. `Makefile` дополнить целями `prod-up`, `backup-db`, `restore-db`.
3. `README.md` — короткий: prereq (Docker, .env), как поднять, как обновить, переменные окружения.
4. Логи: structured JSON logging в backend, отдельная джоба не нужна, просто `docker compose logs -f backend` должен быть читаемым.
5. Опционально: добавить `make seed-demo` — джоба, которая делает первый sync + auto-track + первый раунд предикшенов, чтобы при свежем поднятии было что показать.

**Definition of done:** `git clone → cp .env.example .env → заполнить ключи → make up → подождать 5 минут → открыть фронт → видим события и прогнозы.`

---

## ПРИОРИТИЗАЦИЯ И ПОРЯДОК

Идти строго по фазам. Не прыгать вперёд. После каждой фазы — короткий апдейт мне: что сделано, что в БД, что наружу, какие принял мелкие архитектурные решения. Я говорю «ок, дальше» — едем в следующую фазу.

Если на любой фазе встречаешь развилку, которая повлияет на следующие фазы (например: схема таблицы не покрывает кейс, или промт-формат не парсится у одного из провайдеров) — стопаешься, описываешь развилку, ждёшь решения.

---

## ПЕРВЫЙ ШАГ

Начинай с **Phase 0**. После того как `make up` поднимает все три контейнера и health-check зелёный — отчитайся и жди команду на Phase 1.
