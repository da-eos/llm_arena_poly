import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  api,
  type EventPredictions,
  type MarketWithPredictions,
  type PredictionWithModel,
} from "../lib/api";
import { Layout, formatDate, formatPercent } from "../components/layout";

function ReasoningCell({ p }: { p: PredictionWithModel }) {
  const [open, setOpen] = useState(false);
  if (!p.reasoning) return <span className="text-muted-foreground">—</span>;
  const preview = p.reasoning.length > 120 ? p.reasoning.slice(0, 120) + "…" : p.reasoning;
  return (
    <div className="max-w-xl">
      <div className="whitespace-pre-wrap text-xs text-muted-foreground">
        {open ? p.reasoning : preview}
      </div>
      {p.reasoning.length > 120 && (
        <button
          onClick={() => setOpen((v) => !v)}
          className="mt-1 text-xs text-blue-700 hover:underline"
        >
          {open ? "less" : "more"}
        </button>
      )}
    </div>
  );
}

function diffBadge(predicted: number, market: number | null) {
  if (market == null) return null;
  const d = predicted - market;
  const sign = d > 0 ? "+" : "";
  const color =
    Math.abs(d) < 0.05
      ? "bg-muted text-muted-foreground"
      : d > 0
      ? "bg-amber-100 text-amber-800"
      : "bg-sky-100 text-sky-800";
  return (
    <span className={`ml-1 inline-flex rounded px-1.5 py-0.5 text-[10px] tabular-nums ${color}`}>
      {sign}{(d * 100).toFixed(1)} pp
    </span>
  );
}

function MarketBlock({
  market,
  onPredict,
  predictingPair,
}: {
  market: MarketWithPredictions;
  onPredict: (marketId: string, slug: string) => void;
  predictingPair: string | null;
}) {
  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="flex items-baseline justify-between gap-4 border-b px-4 py-3">
        <div>
          <div className="font-medium">{market.question}</div>
          <div className="text-xs text-muted-foreground">
            Outcomes: {market.outcomes?.join(", ") ?? "—"}
            {market.is_resolved && (
              <span className="ml-2 inline-flex rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-700">
                resolved: {market.resolved_outcome ?? "?"}
              </span>
            )}
          </div>
        </div>
        <div className="text-right tabular-nums">
          <div className="text-xs text-muted-foreground">market price (Yes)</div>
          <div className="text-lg font-semibold">{formatPercent(market.current_price)}</div>
        </div>
      </div>

      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-2 text-left">Model</th>
            <th className="px-4 py-2 text-right">P(Yes)</th>
            <th className="px-4 py-2 text-right">vs market</th>
            <th className="px-4 py-2 text-right">Conf.</th>
            <th className="px-4 py-2 text-left">Reasoning</th>
            <th className="px-4 py-2 text-right">Latency</th>
            <th className="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {market.predictions.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                No predictions yet for this market.
              </td>
            </tr>
          )}
          {market.predictions.map((p) => {
            const key = `${market.id}:${p.llm_model.slug}`;
            const isPending = predictingPair === key;
            return (
              <tr key={p.id} className="border-b last:border-0">
                <td className="px-4 py-2">
                  <div className="font-medium">{p.llm_model.display_name}</div>
                  <div className="text-xs text-muted-foreground">{p.llm_model.slug}</div>
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {p.error ? (
                    <span className="text-red-700">err</span>
                  ) : (
                    formatPercent(p.predicted_probability_yes)
                  )}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {!p.error && diffBadge(p.predicted_probability_yes, market.current_price)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {formatPercent(p.confidence)}
                </td>
                <td className="px-4 py-2">
                  {p.error ? (
                    <span className="text-xs text-red-700">{p.error}</span>
                  ) : (
                    <ReasoningCell p={p} />
                  )}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-xs text-muted-foreground">
                  {p.latency_ms ? `${p.latency_ms} ms` : "—"}
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    onClick={() => onPredict(market.id, p.llm_model.slug)}
                    disabled={isPending || market.is_resolved}
                    className="rounded-md border px-2 py-0.5 text-xs hover:bg-muted disabled:opacity-50"
                  >
                    {isPending ? "…" : "Re-predict"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
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
          const has = m.predictions.some((p) => p.llm_model.slug === mod.slug);
          if (!has) tasks.push(api.predictOne(m.id, mod.slug));
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
    return <Layout><div className="text-muted-foreground">Loading…</div></Layout>;
  }
  if (eventQ.error) {
    return <Layout><div className="text-red-700">{(eventQ.error as Error).message}</div></Layout>;
  }
  const ev = eventQ.data;
  if (!ev) return <Layout><div>Not found.</div></Layout>;

  const totalPreds = ev.markets.reduce((s, m) => s + m.predictions.length, 0);
  const visibleMarkets = ev.markets.slice(0, 30);

  return (
    <Layout>
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/" className="text-sm text-blue-700 hover:underline">← Back to events</Link>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-xl font-semibold">{ev.title}</h2>
        <div className="mt-1 text-sm text-muted-foreground">
          {ev.markets.length} markets · {totalPreds} predictions ·
          {" "}ends {formatDate(ev.markets[0]?.resolved_at)}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={() => predictAllMut.mutate()}
            disabled={predictAllMut.isPending}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {predictAllMut.isPending ? "Running…" : "Predict missing"}
          </button>
          {predictAllMut.data && (
            <span className="text-xs text-emerald-700">
              ✓ created {predictAllMut.data.length} predictions
            </span>
          )}
          {predictAllMut.error && (
            <span className="text-xs text-red-700">{(predictAllMut.error as Error).message}</span>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {visibleMarkets.map((m) => (
          <MarketBlock
            key={m.id}
            market={m}
            onPredict={(marketId, slug) => predictOneMut.mutate({ marketId, slug })}
            predictingPair={predictingPair}
          />
        ))}
        {ev.markets.length > visibleMarkets.length && (
          <div className="text-center text-xs text-muted-foreground">
            showing first {visibleMarkets.length} of {ev.markets.length} markets
          </div>
        )}
      </div>
    </Layout>
  );
}
