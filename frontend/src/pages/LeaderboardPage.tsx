import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type LeaderboardRow } from "../lib/api";
import { Layout } from "../components/layout";

type Metric = "brier" | "logloss" | "pnl";

const METRIC_LABEL: Record<Metric, string> = {
  brier: "Brier (меньше = лучше)",
  logloss: "Log-loss (меньше = лучше)",
  pnl: "P&L $ (больше = лучше)",
};

const MODEL_COLORS: Record<string, string> = {
  "openrouter-gpt-4o-mini":      "#10b981",
  "openrouter-claude-haiku-3-5": "#f97316",
  "openrouter-gemini-flash-2-5": "#3b82f6",
  "openrouter-llama-4-maverick": "#8b5cf6",
  "openrouter-deepseek-v3":      "#ec4899",
};

function metricValue(row: LeaderboardRow, metric: Metric): number {
  if (metric === "brier") return row.avg_brier ?? 0;
  if (metric === "logloss") return row.avg_log_loss ?? 0;
  return row.total_pnl;
}

export default function LeaderboardPage() {
  const [metric, setMetric] = useState<Metric>("brier");
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["leaderboard", metric],
    queryFn: () => api.leaderboard(metric),
    refetchInterval: 60_000,
  });
  const scoreMut = useMutation({
    mutationFn: () => api.scoreNow(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leaderboard"] }),
  });

  const rows = data?.rows ?? [];
  const chartData = rows.map((r) => ({
    name: r.display_name,
    slug: r.slug,
    value: metricValue(r, metric),
  }));

  return (
    <Layout>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">Лидерборд моделей</h2>
        <div className="ml-auto flex items-center gap-2">
          {(["brier", "logloss", "pnl"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              className={`rounded-md border px-3 py-1 text-xs font-medium ${
                metric === m ? "bg-primary text-primary-foreground" : "hover:bg-muted"
              }`}
            >
              {METRIC_LABEL[m]}
            </button>
          ))}
          <button
            onClick={() => scoreMut.mutate()}
            disabled={scoreMut.isPending}
            className="rounded-md border px-3 py-1 text-xs hover:bg-muted disabled:opacity-50"
            title="Пересчитать метрики для всех уже зарезолвленных рынков"
          >
            {scoreMut.isPending ? "Считаю…" : "Пересчитать"}
          </button>
        </div>
      </div>

      {isLoading && <div className="text-muted-foreground">Загрузка…</div>}
      {error && <div className="text-red-700">{(error as Error).message}</div>}
      {scoreMut.data && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-800">
          ✓ обработано рынков: {scoreMut.data.markets}, посчитано прогнозов: {scoreMut.data.scored}, пропущено: {scoreMut.data.skipped}
        </div>
      )}

      {rows.length === 0 && !isLoading && (
        <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm text-muted-foreground">
          Пока нечего сравнивать — нужны зарезолвленные рынки с прогнозами.
          <div className="mt-2 text-xs">
            Когда событие резолвнется на Polymarket, фоновая задача «Обновление отслеживаемых»
            автоматически посчитает метрики. Или нажми «Пересчитать» если уже есть закрытые рынки.
          </div>
        </div>
      )}

      {rows.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-lg border bg-card">
            <div className="border-b px-4 py-3 text-sm font-semibold">Таблица</div>
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">#</th>
                  <th className="px-4 py-2 text-left">Модель</th>
                  <th className="px-4 py-2 text-right">Прогнозов</th>
                  <th className="px-4 py-2 text-right">Brier</th>
                  <th className="px-4 py-2 text-right">LogLoss</th>
                  <th className="px-4 py-2 text-right">P&L $</th>
                  <th className="px-4 py-2 text-right">Точность</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.slug} className="border-b last:border-0">
                    <td className="px-4 py-2 text-muted-foreground">{i + 1}</td>
                    <td className="px-4 py-2">
                      <Link to={`/models/${r.slug}`} className="flex items-center gap-2 font-medium hover:underline">
                        <span
                          className="inline-block h-3 w-3 rounded-sm"
                          style={{ backgroundColor: MODEL_COLORS[r.slug] ?? "#64748b" }}
                        />
                        {r.display_name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">{r.n}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {r.avg_brier == null ? "—" : r.avg_brier.toFixed(4)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {r.avg_log_loss == null ? "—" : r.avg_log_loss.toFixed(4)}
                    </td>
                    <td className={`px-4 py-2 text-right tabular-nums ${r.total_pnl >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                      {r.total_pnl >= 0 ? "+" : ""}{r.total_pnl.toFixed(0)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {r.accuracy == null ? "—" : `${(r.accuracy * 100).toFixed(0)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="rounded-lg border bg-card">
            <div className="border-b px-4 py-3 text-sm font-semibold">
              {METRIC_LABEL[metric]}
            </div>
            <div className="h-80 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ left: 30, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="name" width={120} />
                  <Tooltip
                    formatter={(v: number) => (metric === "pnl" ? `$${v.toFixed(2)}` : v.toFixed(4))}
                  />
                  <Bar dataKey="value">
                    {chartData.map((d) => (
                      <Cell key={d.slug} fill={MODEL_COLORS[d.slug] ?? "#64748b"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
