import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type EventItem } from "../lib/api";
import { Layout, formatDate, formatMoney, polymarketUrl, tFilter } from "../components/layout";

function EventRow({ event }: { event: EventItem }) {
  const qc = useQueryClient();
  const trackMut = useMutation({
    mutationFn: () => (event.is_tracked ? api.untrack(event.id) : api.track(event.id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["events"] }),
  });
  const hasPredictions = event.predictions_count > 0;
  return (
    <tr className="border-b last:border-0 hover:bg-muted/40">
      <td className="px-4 py-3">
        <div className="flex items-baseline gap-2">
          <Link to={`/events/${event.id}`} className="font-medium text-foreground hover:underline">
            {event.title}
          </Link>
          {polymarketUrl(event.slug, event.polymarket_id) && (
            <a
              href={polymarketUrl(event.slug, event.polymarket_id) ?? "#"}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-700 hover:underline"
              title="Открыть на Polymarket"
            >
              ↗ polymarket
            </a>
          )}
        </div>
        <div className="text-xs text-muted-foreground">
          рынков: {event.markets_count} · до {formatDate(event.end_date)}
        </div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{formatMoney(event.liquidity)}</td>
      <td className="px-4 py-3 text-center">
        {event.is_tracked ? (
          <span className="inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
            следим
          </span>
        ) : (
          <span className="inline-flex rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            —
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-center">
        {hasPredictions ? (
          <Link
            to={`/events/${event.id}`}
            className="inline-flex rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 hover:bg-blue-200"
          >
            {event.predictions_count} прогнозов →
          </Link>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <button
          onClick={(e) => {
            e.preventDefault();
            trackMut.mutate();
          }}
          disabled={trackMut.isPending}
          className="rounded-md border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
        >
          {trackMut.isPending ? "…" : event.is_tracked ? "Снять" : "Следить"}
        </button>
      </td>
    </tr>
  );
}

function JobsPanel() {
  const { data, refetch } = useQuery({
    queryKey: ["jobs"],
    queryFn: api.listJobs,
    refetchInterval: 15_000,
  });
  const runMut = useMutation({
    mutationFn: (id: string) => api.runJob(id),
    onSuccess: () => refetch(),
  });
  const JOB_NAMES_RU: Record<string, string> = {
    sync_trending_events: "Загрузка трендов",
    auto_track_top_events: "Авто-выбор событий",
    refresh_tracked_events: "Обновление отслеживаемых",
    predictions: "Прогоны прогнозов",
  };
  return (
    <div className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3 text-sm font-semibold">Фоновые задачи</div>
      <div className="divide-y text-sm">
        {data?.items.map((j) => (
          <div key={j.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="font-medium">{JOB_NAMES_RU[j.id] ?? j.id}</div>
              <div className="text-xs text-muted-foreground">
                следующий запуск: {j.next_run_time ? new Date(j.next_run_time).toLocaleTimeString("ru-RU") : "—"}
              </div>
            </div>
            <button
              onClick={() => runMut.mutate(j.id)}
              disabled={runMut.isPending}
              className="rounded-md border px-3 py-1 text-xs hover:bg-muted disabled:opacity-50"
            >
              Запустить
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EventsPage() {
  const [trackedFilter, setTrackedFilter] = useState<"all" | "tracked" | "untracked">("tracked");
  const qc = useQueryClient();
  const params = {
    tracked: trackedFilter === "all" ? undefined : trackedFilter === "tracked",
    limit: 50,
  };
  const { data, isLoading, error } = useQuery({
    queryKey: ["events", params],
    queryFn: () => api.listEvents(params),
    refetchInterval: 30_000,
  });
  const syncMut = useMutation({
    mutationFn: () => api.syncPolymarket(100),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["events"] }),
  });
  const predictMut = useMutation({
    mutationFn: () => api.predictNow(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["events"] }),
  });

  return (
    <Layout>
      <div className="rounded-lg border bg-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => syncMut.mutate()}
            disabled={syncMut.isPending}
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            {syncMut.isPending ? "Загружаю…" : "1. Загрузить с Polymarket"}
          </button>
          <button
            onClick={() => predictMut.mutate()}
            disabled={predictMut.isPending}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {predictMut.isPending ? "Прогнозирую…" : "2. Запустить прогнозы по отслеживаемым"}
          </button>
          <div className="ml-auto text-xs text-muted-foreground">
            Возьми событие в работу → запусти прогнозы → кликни по строке, чтобы увидеть прогнозы каждой модели.
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-4 text-xs">
          {syncMut.data && (
            <span className="text-emerald-700">
              ✓ загружено: событий {syncMut.data.events}, рынков {syncMut.data.markets}
            </span>
          )}
          {predictMut.data && (
            <span className="text-emerald-700">
              ✓ прогнозы: {predictMut.data.ok} успешно, {predictMut.data.error} ошибок,{" "}
              {predictMut.data.skipped} пропущено (всего {predictMut.data.total})
            </span>
          )}
          {predictMut.error && (
            <span className="text-red-700">{(predictMut.error as Error).message}</span>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            {(["tracked", "all", "untracked"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setTrackedFilter(v)}
                className={`rounded-md border px-3 py-1 text-xs font-medium ${
                  trackedFilter === v ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                }`}
              >
                {tFilter(v)}
              </button>
            ))}
            {data && (
              <span className="ml-auto text-xs text-muted-foreground">
                показано {data.items.length} из {data.total}
              </span>
            )}
          </div>

          <div className="overflow-hidden rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Событие</th>
                  <th className="px-4 py-2 text-right">Ликвидность</th>
                  <th className="px-4 py-2 text-center">Статус</th>
                  <th className="px-4 py-2 text-center">Прогнозы</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {isLoading && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Загрузка…</td></tr>
                )}
                {error && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-red-700">{(error as Error).message}</td></tr>
                )}
                {data?.items.map((e) => <EventRow key={e.id} event={e} />)}
                {data?.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                      {trackedFilter === "tracked"
                        ? "Пока ничего не отслеживается. Запусти «Загрузить с Polymarket», подожди авто-выбор или возьми событие вручную."
                        : "Ничего не найдено. Попробуй «Загрузить с Polymarket»."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <JobsPanel />
      </div>
    </Layout>
  );
}
