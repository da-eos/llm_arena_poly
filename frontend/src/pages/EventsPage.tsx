import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type EventItem } from "../lib/api";
import { Layout, formatDate, formatMoney } from "../components/layout";

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
        <Link to={`/events/${event.id}`} className="font-medium text-foreground hover:underline">
          {event.title}
        </Link>
        <div className="text-xs text-muted-foreground">
          {event.markets_count} markets · ends {formatDate(event.end_date)}
        </div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{formatMoney(event.liquidity)}</td>
      <td className="px-4 py-3 text-center">
        {event.is_tracked ? (
          <span className="inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
            tracked
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
            {event.predictions_count} predictions →
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
          {trackMut.isPending ? "…" : event.is_tracked ? "Untrack" : "Track"}
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
  return (
    <div className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3 text-sm font-semibold">Scheduled jobs</div>
      <div className="divide-y text-sm">
        {data?.items.map((j) => (
          <div key={j.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="font-medium">{j.id}</div>
              <div className="text-xs text-muted-foreground">
                next: {j.next_run_time ? new Date(j.next_run_time).toLocaleTimeString() : "—"}
              </div>
            </div>
            <button
              onClick={() => runMut.mutate(j.id)}
              disabled={runMut.isPending}
              className="rounded-md border px-3 py-1 text-xs hover:bg-muted disabled:opacity-50"
            >
              Run
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EventsPage() {
  // Default to tracked — those are the events with (or that will have) predictions.
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
            {syncMut.isPending ? "Syncing…" : "1. Sync Polymarket"}
          </button>
          <button
            onClick={() => predictMut.mutate()}
            disabled={predictMut.isPending}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {predictMut.isPending ? "Predicting…" : "2. Predict on tracked events"}
          </button>
          <div className="ml-auto text-xs text-muted-foreground">
            Track an event → run predictions → click row to view per-model forecasts.
          </div>
        </div>
        <div className="mt-2 flex gap-4 text-xs">
          {syncMut.data && (
            <span className="text-emerald-700">
              ✓ synced {syncMut.data.events} events / {syncMut.data.markets} markets
            </span>
          )}
          {predictMut.data && (
            <span className="text-emerald-700">
              ✓ predictions: {predictMut.data.ok} ok, {predictMut.data.error} err,{" "}
              {predictMut.data.skipped} skipped (of {predictMut.data.total})
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
                {v}
              </button>
            ))}
            {data && (
              <span className="ml-auto text-xs text-muted-foreground">
                showing {data.items.length} of {data.total}
              </span>
            )}
          </div>

          <div className="overflow-hidden rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Event</th>
                  <th className="px-4 py-2 text-right">Liquidity</th>
                  <th className="px-4 py-2 text-center">Tracked</th>
                  <th className="px-4 py-2 text-center">Predictions</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {isLoading && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Loading…</td></tr>
                )}
                {error && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-red-700">{(error as Error).message}</td></tr>
                )}
                {data?.items.map((e) => <EventRow key={e.id} event={e} />)}
                {data?.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                      {trackedFilter === "tracked"
                        ? "No tracked events. Wait for auto-track or run “Sync Polymarket” first, then track manually."
                        : "No events match. Try “Sync Polymarket”."}
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
