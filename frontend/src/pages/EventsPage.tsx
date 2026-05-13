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
  return (
    <tr className="border-b last:border-0 hover:bg-muted/40">
      <td className="px-4 py-3">
        <Link to={`/events/${event.id}`} className="font-medium hover:underline">
          {event.title}
        </Link>
        <div className="text-xs text-muted-foreground">
          {event.slug ?? event.polymarket_id}
        </div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{formatMoney(event.volume)}</td>
      <td className="px-4 py-3 text-right tabular-nums">{formatMoney(event.liquidity)}</td>
      <td className="px-4 py-3 text-right">{formatDate(event.end_date)}</td>
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
              Run now
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EventsPage() {
  const [trackedFilter, setTrackedFilter] = useState<"all" | "tracked" | "untracked">("all");
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
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={() => syncMut.mutate()}
          disabled={syncMut.isPending}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {syncMut.isPending ? "Syncing…" : "Sync Polymarket"}
        </button>
        <button
          onClick={() => predictMut.mutate()}
          disabled={predictMut.isPending}
          className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
        >
          {predictMut.isPending ? "Predicting…" : "Predict now"}
        </button>
        {syncMut.data && (
          <span className="text-xs text-emerald-700">
            ✓ {syncMut.data.events} events / {syncMut.data.markets} markets
          </span>
        )}
        {predictMut.data && (
          <span className="text-xs text-emerald-700">
            ✓ predictions: {predictMut.data.ok} ok / {predictMut.data.error} err /{" "}
            {predictMut.data.skipped} skipped (total {predictMut.data.total})
          </span>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            {(["all", "tracked", "untracked"] as const).map((v) => (
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
                {data.items.length} of {data.total}
              </span>
            )}
          </div>

          <div className="overflow-hidden rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Event</th>
                  <th className="px-4 py-2 text-right">Volume</th>
                  <th className="px-4 py-2 text-right">Liquidity</th>
                  <th className="px-4 py-2 text-right">Ends</th>
                  <th className="px-4 py-2 text-center">Tracked</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {isLoading && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">Loading…</td></tr>
                )}
                {error && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-red-700">{(error as Error).message}</td></tr>
                )}
                {data?.items.map((e) => <EventRow key={e.id} event={e} />)}
                {data?.items.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No events yet — click “Sync Polymarket”.
                  </td></tr>
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
