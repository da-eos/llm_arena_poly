import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  api,
  type EventPredictions,
  type MarketWithPredictions,
  type PredictionWithModel,
} from "../lib/api";
import { Layout, formatDate, formatPercent, polymarketUrl } from "../components/layout";

const MODEL_COLORS: Record<string, string> = {
  "openrouter-gpt-4o-mini":      "bg-emerald-500",
  "openrouter-claude-haiku-3-5": "bg-orange-500",
  "openrouter-gemini-flash-2-5": "bg-blue-500",
  "openrouter-llama-4-maverick": "bg-violet-500",
  "openrouter-deepseek-v3":      "bg-pink-500",
};

function modelColor(slug: string): string {
  return MODEL_COLORS[slug] ?? "bg-slate-500";
}

function YesNoBadge({ p_yes, size = "md" }: { p_yes: number; size?: "md" | "lg" }) {
  const isYes = p_yes >= 0.5;
  const sizeCls = size === "lg" ? "px-4 py-1.5 text-base" : "px-3 py-1 text-sm";
  return (
    <span
      className={`inline-flex items-center rounded-md font-bold uppercase tracking-wide ${sizeCls} ${
        isYes ? "bg-emerald-600 text-white" : "bg-red-600 text-white"
      }`}
      title={`P(Yes) = ${(p_yes * 100).toFixed(1)}%`}
    >
      {isYes ? "ДА" : "НЕТ"}
    </span>
  );
}

function PredictionBar({
  prediction,
  marketPrice,
}: {
  prediction: PredictionWithModel;
  marketPrice: number | null;
}) {
  const p = prediction.predicted_probability_yes;
  const m = prediction.llm_model;
  const barColor = modelColor(m.slug);

  if (prediction.error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-3">
        <div className="flex items-center justify-between">
          <div className="font-medium text-sm">{m.display_name}</div>
          <div className="text-xs text-red-700">ошибка</div>
        </div>
        <div className="mt-1 text-xs text-red-700">{prediction.error}</div>
      </div>
    );
  }

  const marketIsYes = marketPrice != null && marketPrice >= 0.5;
  const modelIsYes = p >= 0.5;
  const agreesWithMarket = marketPrice != null && marketIsYes === modelIsYes;

  return (
    <div className="rounded-md border bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`inline-block h-3 w-3 rounded-sm ${barColor}`} />
          <span className="font-medium text-sm truncate" title={m.model_id_at_provider}>
            {m.display_name}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <YesNoBadge p_yes={p} size="lg" />
          {marketPrice != null && (
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                agreesWithMarket
                  ? "bg-muted text-muted-foreground"
                  : "bg-amber-100 text-amber-800"
              }`}
              title={`Рынок сейчас: ${marketIsYes ? "ДА" : "НЕТ"}`}
            >
              {agreesWithMarket ? "= с рынком" : "≠ с рынком"}
            </span>
          )}
        </div>
      </div>

      <div className="mt-2 flex items-baseline justify-between text-xs text-muted-foreground tabular-nums">
        <span>уверенность модели: <span className="font-medium text-foreground">{formatPercent(p)}</span></span>
        {marketPrice != null && (
          <span>цена рынка (Yes): <span className="font-medium text-foreground">{formatPercent(marketPrice)}</span></span>
        )}
      </div>

      {prediction.reasoning && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            обоснование · {prediction.latency_ms ?? "—"} мс
          </summary>
          <div className="mt-2 whitespace-pre-wrap text-foreground/80">{prediction.reasoning}</div>
        </details>
      )}
    </div>
  );
}

function MarketCard({
  market,
  onPredict,
  predictingPair,
}: {
  market: MarketWithPredictions;
  onPredict: (marketId: string, slug: string) => void;
  predictingPair: string | null;
}) {
  // Sort predictions by p_yes desc so highest forecasts are on top.
  const sorted = [...market.predictions].sort(
    (a, b) => b.predicted_probability_yes - a.predicted_probability_yes
  );

  return (
    <div className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-medium">{market.question}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {market.is_resolved && (
                <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-700">
                  результат:
                  <YesNoBadge p_yes={market.resolved_outcome?.toLowerCase() === "yes" ? 1 : 0} />
                </span>
              )}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">мнение рынка</div>
            {market.current_price != null ? (
              <div className="flex items-baseline justify-end gap-2">
                <YesNoBadge p_yes={market.current_price} size="lg" />
                <div className="text-sm tabular-nums text-muted-foreground">
                  {formatPercent(market.current_price >= 0.5 ? market.current_price : 1 - market.current_price)}
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">—</div>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-2 p-4">
        {sorted.length === 0 && (
          <div className="rounded-md border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground">
            Прогнозов по этому рынку ещё нет.
          </div>
        )}
        {sorted.map((p) => {
          const key = `${market.id}:${p.llm_model.slug}`;
          const isPending = predictingPair === key;
          return (
            <div key={p.id} className="relative">
              <PredictionBar prediction={p} marketPrice={market.current_price} />
              <button
                onClick={() => onPredict(market.id, p.llm_model.slug)}
                disabled={isPending || market.is_resolved}
                className="absolute right-2 top-2 rounded border bg-white/80 px-1.5 py-0.5 text-[10px] hover:bg-muted disabled:opacity-40"
                title="Перегнать прогноз этой модели"
              >
                {isPending ? "…" : "↻"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function EventDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [predictingPair, setPredictingPair] = useState<string | null>(null);

  const eventQ = useQuery({
    queryKey: ["event-predictions", id],
    queryFn: () => api.eventPredictions(id),
    refetchInterval: 30_000,
    enabled: !!id,
  });
  const modelsQ = useQuery({
    queryKey: ["models"],
    queryFn: api.listModels,
  });

  const predictAllMut = useMutation({
    mutationFn: async () => {
      const data = eventQ.data as EventPredictions | undefined;
      const models = modelsQ.data ?? [];
      if (!data) return [] as PredictionWithModel[];
      const enabled = models.filter((m) => m.is_enabled);
      const tasks: Promise<PredictionWithModel>[] = [];
      for (const m of data.markets) {
        if (m.is_resolved) continue;
        for (const mod of enabled) {
          const has = m.predictions.some((p) => p.llm_model.slug === mod.slug && !p.error);
          if (!has) tasks.push(api.predictOne(m.id, mod.slug, true));
        }
      }
      return Promise.all(tasks);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["event-predictions", id] }),
  });

  const predictOneMut = useMutation({
    mutationFn: async ({ marketId, slug }: { marketId: string; slug: string }) => {
      setPredictingPair(`${marketId}:${slug}`);
      try {
        return await api.predictOne(marketId, slug, true);
      } finally {
        setPredictingPair(null);
      }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["event-predictions", id] }),
  });

  if (eventQ.isLoading) {
    return <Layout><div className="text-muted-foreground">Загрузка…</div></Layout>;
  }
  if (eventQ.error) {
    return <Layout><div className="text-red-700">{(eventQ.error as Error).message}</div></Layout>;
  }
  const ev = eventQ.data;
  if (!ev) return <Layout><div>Не найдено.</div></Layout>;

  const totalPreds = ev.markets.reduce((s, m) => s + m.predictions.length, 0);
  const enabledModels = (modelsQ.data ?? []).filter((m) => m.is_enabled);
  const missingPairs = ev.markets.reduce((s, m) => {
    if (m.is_resolved) return s;
    return s + enabledModels.filter(
      (mod) => !m.predictions.some((p) => p.llm_model.slug === mod.slug && !p.error)
    ).length;
  }, 0);

  // Sort markets: those with predictions first, then by name.
  const sortedMarkets = [...ev.markets].sort((a, b) => {
    const ap = a.predictions.length > 0 ? 0 : 1;
    const bp = b.predictions.length > 0 ? 0 : 1;
    if (ap !== bp) return ap - bp;
    return a.question.localeCompare(b.question);
  });
  const visibleMarkets = sortedMarkets.slice(0, 30);

  return (
    <Layout>
      <Link to="/" className="text-sm text-blue-700 hover:underline">← К списку событий</Link>

      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-2xl font-semibold">{ev.title}</h2>
          {polymarketUrl(ev.slug, ev.polymarket_id) && (
            <a
              href={polymarketUrl(ev.slug, ev.polymarket_id) ?? "#"}
              target="_blank"
              rel="noreferrer"
              className="shrink-0 rounded-md border px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50"
            >
              Открыть на Polymarket ↗
            </a>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          <span>рынков: {ev.markets.length}</span>
          <span>·</span>
          <span>прогнозов: {totalPreds}</span>
          {ev.end_date && (
            <>
              <span>·</span>
              <span>до {formatDate(ev.end_date)}</span>
            </>
          )}
          {missingPairs > 0 && (
            <>
              <span>·</span>
              <span className="text-amber-700">не хватает прогнозов: {missingPairs}</span>
            </>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={() => predictAllMut.mutate()}
            disabled={predictAllMut.isPending || missingPairs === 0}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {predictAllMut.isPending
              ? "Прогнозирую…"
              : missingPairs > 0
              ? `Спрогнозировать недостающие (${missingPairs})`
              : "Все модели отработали"}
          </button>
          {predictAllMut.data && (
            <span className="text-xs text-emerald-700">
              ✓ создано прогнозов: {predictAllMut.data.length}
            </span>
          )}
        </div>

        {/* Legend */}
        {enabledModels.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>Модели:</span>
            {enabledModels.map((m) => (
              <span key={m.slug} className="inline-flex items-center gap-1">
                <span className={`inline-block h-2 w-2 rounded-sm ${modelColor(m.slug)}`} />
                {m.display_name}
              </span>
            ))}
            <span className="ml-2 inline-flex items-center gap-1">
              <span className="inline-flex rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-bold text-white">ДА</span>
              <span className="inline-flex rounded bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white">НЕТ</span>
              <span>= ответ модели</span>
            </span>
          </div>
        )}
      </div>

      <div className="space-y-3">
        {visibleMarkets.map((m) => (
          <MarketCard
            key={m.id}
            market={m}
            onPredict={(marketId, slug) => predictOneMut.mutate({ marketId, slug })}
            predictingPair={predictingPair}
          />
        ))}
        {sortedMarkets.length > visibleMarkets.length && (
          <div className="text-center text-xs text-muted-foreground">
            показано {visibleMarkets.length} из {sortedMarkets.length} рынков
          </div>
        )}
      </div>
    </Layout>
  );
}
