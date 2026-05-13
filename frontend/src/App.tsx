export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="container py-6">
          <h1 className="text-2xl font-semibold tracking-tight">LLM Arena</h1>
          <p className="text-sm text-muted-foreground">
            Polymarket × LLM prediction leaderboard
          </p>
        </div>
      </header>
      <main className="container py-12">
        <div className="rounded-lg border bg-muted/30 p-8 text-center">
          <p className="text-muted-foreground">
            Phase 0 skeleton is up. API + data coming soon.
          </p>
        </div>
      </main>
    </div>
  );
}
