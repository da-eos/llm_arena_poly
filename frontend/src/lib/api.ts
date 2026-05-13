import { API_BASE_URL } from "./utils";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${text}`.trim());
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface EventItem {
  id: string;
  polymarket_id: string;
  slug: string | null;
  title: string;
  description: string | null;
  category: string | null;
  volume: number | null;
  liquidity: number | null;
  end_date: string | null;
  is_tracked: boolean;
  created_at: string;
  updated_at: string;
  markets_count: number;
  predictions_count: number;
}

export interface EventList {
  items: EventItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface Market {
  id: string;
  polymarket_id: string;
  question: string;
  outcomes: string[] | null;
  current_price: number | null;
  is_resolved: boolean;
  resolved_outcome: string | null;
  resolved_at: string | null;
}

export interface EventDetail extends EventItem {
  markets: Market[];
}

export interface LLMModelRead {
  id: string;
  slug: string;
  provider: string;
  display_name: string;
  model_id_at_provider: string;
  is_enabled: boolean;
}

export interface PredictionWithModel {
  id: string;
  market_id: string;
  llm_model_id: string;
  predicted_probability_yes: number;
  reasoning: string | null;
  confidence: number | null;
  latency_ms: number | null;
  cost_usd: number | null;
  error: string | null;
  created_at: string;
  llm_model: LLMModelRead;
}

export interface MarketWithPredictions extends Market {
  predictions: PredictionWithModel[];
}

export interface EventPredictions {
  event_id: string;
  title: string;
  slug: string | null;
  polymarket_id: string;
  end_date: string | null;
  markets: MarketWithPredictions[];
}

export interface PredictRunResult {
  total: number;
  ok: number;
  error: number;
  skipped: number;
  fail: number;
}

export interface JobInfo {
  id: string;
  name: string;
  next_run_time: string | null;
  trigger: string;
}

export const api = {
  listEvents: (params: { tracked?: boolean; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.tracked !== undefined) qs.set("tracked", String(params.tracked));
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    if (params.offset !== undefined) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<EventList>(`/events${suffix}`);
  },
  getEvent: (id: string) => request<EventDetail>(`/events/${id}`),
  track: (id: string) => request<{ ok: boolean }>(`/events/${id}/track`, { method: "POST" }),
  untrack: (id: string) => request<{ ok: boolean }>(`/events/${id}/untrack`, { method: "POST" }),
  syncPolymarket: (limit = 30) =>
    request<{ events: number; markets: number }>(
      `/admin/sync/polymarket?limit=${limit}`,
      { method: "POST" }
    ),
  predictNow: (force = false) =>
    request<PredictRunResult>(
      `/admin/predict-now${force ? "?force=true" : ""}`,
      { method: "POST" }
    ),
  listJobs: () => request<{ items: JobInfo[] }>(`/admin/jobs`),
  runJob: (id: string) =>
    request<{ status: string; job: string }>(`/admin/jobs/${id}/run`, { method: "POST" }),
  listModels: () => request<LLMModelRead[]>(`/models`),
  eventPredictions: (id: string) => request<EventPredictions>(`/events/${id}/predictions`),
  predictOne: (marketId: string, modelSlug: string, force = false) =>
    request<PredictionWithModel>(
      `/predictions/market/${marketId}/model/${modelSlug}${force ? "?force=true" : ""}`,
      { method: "POST" }
    ),
  leaderboard: (metric: "brier" | "logloss" | "pnl" = "brier", category?: string) => {
    const qs = new URLSearchParams({ metric });
    if (category) qs.set("category", category);
    return request<LeaderboardResponse>(`/leaderboard?${qs}`);
  },
  modelHistory: (slug: string) => request<HistoryRow[]>(`/models/${slug}/history`),
  scoreNow: () => request<{ markets: number; scored: number; skipped: number }>(`/admin/score-now`, { method: "POST" }),
};

export interface LeaderboardRow {
  slug: string;
  display_name: string;
  provider: string;
  n: number;
  avg_brier: number | null;
  avg_log_loss: number | null;
  total_pnl: number;
  accuracy: number | null;
}

export interface LeaderboardResponse {
  metric: string;
  rows: LeaderboardRow[];
}

export interface HistoryRow {
  score_id: string;
  prediction_id: string;
  market_id: string;
  event_id: string;
  event_title: string;
  market_question: string;
  resolved_outcome: string | null;
  predicted_probability_yes: number;
  market_price: number | null;
  brier_score: number;
  log_loss: number;
  pnl_demo_usd: number;
  cum_pnl_usd: number;
  was_correct: boolean;
  created_at: string;
}
