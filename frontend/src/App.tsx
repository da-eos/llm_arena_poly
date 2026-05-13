import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type EventItem } from "./lib/api";

function formatMoney(v: number | null): string {
  if (v === null) return "—";
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function formatDate(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return d.toISOString().slice(0, 10);
}

function EventRow({ event }: { event: EventItem }) {
  const qc = useQueryClient();
  const trackMut = useMutation({
    mutationFn: () => (event.is_tracked ? api.untrack(event.id) : api.track(event.id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["events"] }),
  });
  return (
    <tr className="border-b last:border-0 hover:bg-muted/40">
      <td className="px-4 py-3">
        <div className="font-medium">{event.title}</div>
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
          onClick={() => trackMut.mutate()}
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
        {data?.items.length === 0 && (
          <div className="px-4 py-3 text-muted-foreground">No jobs registered.</div>
        )}
      </div>
    </div>
  );
}

export default function App() {
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
    mutationFn: () => api.syncPolymarket(30),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["events"] }),
  });

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="container flex items-center justify-between py-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">LLM Arena</h1>
            <p className="text-sm text-muted-foreground">
              Polymarket × LLM prediction leaderboard
            </p>
          </div>
          <button
            onClick={() => syncMut.mutate()}
            disabled={syncMut.isPending}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {syncMut.isPending ? "Syncing…" : "Sync Polymarket"}
          </button>
        </div>
      </header>

      <main className="container space-y-6 py-8">
        {syncMut.data && (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
            Synced {syncMut.data.events} events / {syncMut.data.markets} markets
          </div>
        )}
        {syncMut.error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
            Sync failed: {(syncMut.error as Error).message}
          </div>
        )}

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
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                        Loading…
                      </td>
                    </tr>
                  )}
                  {error && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-red-700">
                        {(error as Error).message}
                      </td>
                    </tr>
                  )}
                  {data?.items.map((e) => <EventRow key={e.id} event={e} />)}
                  {data?.items.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                        No events yet — click “Sync Polymarket”.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <JobsPanel />
        </div>
      </main>
    </div>
  );
}
