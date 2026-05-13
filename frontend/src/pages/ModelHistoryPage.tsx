import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api";
import { Layout, formatPercent } from "../components/layout";

export default function ModelHistoryPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["model-history", slug],
    queryFn: () => api.modelHistory(slug),
    refetchInterval: 60_000,
    enabled: !!slug,
  });

  const rows = data ?? [];
  const chartData = rows.map((r, i) => ({
    idx: i + 1,
    cum_pnl: r.cum_pnl_usd,
    event: r.event_title,
  }));
  const totalPnl = rows.reduce((s, r) => s + r.pnl_demo_usd, 0);
  const correct = rows.filter((r) => r.was_correct).length;

  return (
    <Layout>
      <Link to="/leaderboard" className="text-sm text-blue-700 hover:underline">← К лидерборду</Link>

      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-xl font-semibold">История модели: {slug}</h2>
        <div className="mt-1 text-sm text-muted-foreground">
          зарезолвлено прогнозов: {rows.length} · попаданий: {correct} · суммарный P&L:{" "}
          <span className={totalPnl >= 0 ? "text-emerald-700" : "text-red-700"}>
            {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
          </span>
        </div>
      </div>

      {isLoading && <div className="text-muted-foreground">Загрузка…</div>}
      {error && <div className="text-red-700">{(error as Error).message}</div>}

      {rows.length === 0 && !isLoading && (
        <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm text-muted-foreground">
          У этой модели пока нет зарезолвленных прогнозов.
        </div>
      )}

      {rows.length > 0 && (
        <>
          <div className="rounded-lg border bg-card">
            <div className="border-b px-4 py-3 text-sm font-semibold">Накопленный P&L</div>
            <div className="h-72 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="idx" label={{ value: "прогноз №", position: "insideBottom", offset: -5 }} />
                  <YAxis />
                  <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                  <Line type="monotone" dataKey="cum_pnl" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-lg border bg-card">
            <div className="border-b px-4 py-3 text-sm font-semibold">Все зарезолвленные прогнозы</div>
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Событие / рынок</th>
                  <th className="px-4 py-2 text-center">Результат</th>
                  <th className="px-4 py-2 text-right">P(Yes) модели</th>
                  <th className="px-4 py-2 text-right">Рынок</th>
                  <th className="px-4 py-2 text-right">Brier</th>
                  <th className="px-4 py-2 text-right">P&L</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.score_id} className="border-b last:border-0">
                    <td className="px-4 py-2">
                      <Link to={`/events/${r.event_id}`} className="font-medium hover:underline">
                        {r.event_title}
                      </Link>
                      <div className="text-xs text-muted-foreground">{r.market_question}</div>
                    </td>
                    <td className="px-4 py-2 text-center">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          r.was_correct ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
                        }`}
                      >
                        {r.resolved_outcome ?? "?"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">{formatPercent(r.predicted_probability_yes)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{formatPercent(r.market_price)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{r.brier_score.toFixed(3)}</td>
                    <td className={`px-4 py-2 text-right tabular-nums ${r.pnl_demo_usd >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                      {r.pnl_demo_usd >= 0 ? "+" : ""}${r.pnl_demo_usd.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Layout>
  );
}
