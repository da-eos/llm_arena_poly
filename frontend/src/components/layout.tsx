import { Link } from "react-router-dom";

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="container flex items-center justify-between py-6">
          <Link to="/" className="hover:opacity-80">
            <h1 className="text-2xl font-semibold tracking-tight">LLM Арена</h1>
            <p className="text-sm text-muted-foreground">
              Лидерборд LLM-прогнозов на рынках Polymarket
            </p>
          </Link>
        </div>
      </header>
      <main className="container space-y-6 py-8">{children}</main>
    </div>
  );
}

export function formatMoney(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

export function formatDate(s: string | null | undefined): string {
  if (!s) return "—";
  return new Date(s).toISOString().slice(0, 10);
}

const RU_LABELS = {
  tracked: "отслеживается",
  untracked: "не отслеживается",
  all: "все",
} as const;

export function tFilter(k: "tracked" | "untracked" | "all"): string {
  return RU_LABELS[k];
}

export function formatPercent(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

export function polymarketUrl(slug: string | null | undefined, polymarketId?: string): string | null {
  if (slug) return `https://polymarket.com/event/${slug}`;
  if (polymarketId) return `https://polymarket.com/event/${polymarketId}`;
  return null;
}
