import { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  ChevronDown,
  Database,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import * as api from '../services/api';
import { Insights, InsightQueryLog } from '../types';

const barColors = ['bg-forest-600', 'bg-amber-500', 'bg-earth-500', 'bg-ink'];

function BreakdownCard({
  title,
  counts,
}: {
  title: string;
  counts: Record<string, number>;
}) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = entries.reduce((sum, [, value]) => sum + value, 0) || 1;

  return (
    <section className="rounded-xl border border-earth-100 bg-white shadow-card">
      <div className="border-b border-earth-100 px-5 py-3.5">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
      </div>
      {entries.length === 0 ? (
        <p className="px-5 py-6 text-center text-xs text-ink-mute">No data yet.</p>
      ) : (
        <div className="space-y-3 px-5 py-4">
          {entries.map(([label, value], index) => (
            <div key={label}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="capitalize text-ink-soft">{label.replace('_', ' ')}</span>
                <span className="font-semibold text-ink">{value}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-earth-100">
                <div
                  className={`h-full rounded-full ${barColors[index % barColors.length]}`}
                  style={{ width: `${Math.max(4, Math.round((value / max) * 100))}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function QueryRow({ query }: { query: InsightQueryLog }) {
  return (
    <div className="px-5 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold text-ink">{query.name}</span>
        <span className="flex items-center gap-3 text-[11px] text-ink-mute">
          <span>{query.rows} rows</span>
          <span>{query.time_used}s</span>
          <span
            className={`rounded-full px-2 py-0.5 font-semibold ${
              query.ok ? 'bg-forest-100 text-forest-800' : 'bg-red-100 text-red-700'
            }`}
          >
            {query.ok ? 'ok' : 'failed'}
          </span>
        </span>
      </div>
      <pre className="mt-1.5 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-earth-50 px-3 py-2 text-[11px] leading-relaxed text-ink-soft">
        {query.sql}
      </pre>
      {query.error && <p className="mt-1 text-[11px] text-red-600">{query.error}</p>}
    </div>
  );
}

export function InsightsPanel() {
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSql, setShowSql] = useState(false);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getInsights({ refresh });
      setInsights(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load insights');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => load(), 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-white p-6 shadow-card">
        <div className="flex items-center gap-2 text-red-600">
          <AlertCircle className="h-5 w-5" />
          <h3 className="text-sm font-semibold">Analytics query failed</h3>
        </div>
        <p className="mt-2 text-sm text-ink-mute">{error}</p>
        <button
          onClick={() => load(true)}
          className="mt-4 rounded-lg bg-forest-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-forest-700"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!loading && !insights) {
    return (
      <div className="rounded-xl border border-earth-100 bg-white p-8 shadow-card">
        <div className="flex items-center gap-2 text-ink">
          <Sparkles className="h-5 w-5 text-earth-500" />
          <h3 className="text-sm font-semibold">Zetaris is not connected</h3>
        </div>
        <p className="mt-2 max-w-xl text-sm text-ink-mute">
          The analytics gateway is not configured on the server. Set
          ZETARIS_BASE_URL, ZETARIS_EMAIL, ZETARIS_PASSWORD and ZETARIS_DATABASE
          in <code className="rounded bg-earth-50 px-1">backend/.env</code>, then
          register the MySQL datasource in Zetaris.
        </p>
        <button
          onClick={() => load()}
          className="mt-4 rounded-lg border border-earth-200 px-4 py-2 text-xs font-semibold text-forest-700 transition hover:border-forest-400 hover:bg-forest-50"
        >
          Check again
        </button>
      </div>
    );
  }

  if (!insights) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-mute">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading insights…
      </div>
    );
  }

  const pending = insights.by_status.pending ?? 0;

  return (
    <div className="space-y-6">
      {/* Source strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-earth-100 bg-white px-4 py-3 shadow-card">
        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-mute">
          <Database className="h-4 w-4 text-forest-600" />
          <span className="font-semibold text-ink-soft">{insights.source.engine}</span>
          <span className="text-ink-faint">·</span>
          <span>{insights.source.database}</span>
          <span className="text-ink-faint">·</span>
          <span>updated {insights.generated_at.replace('T', ' ')}</span>
          {insights.cached && (
            <span className="rounded-full bg-earth-100 px-2 py-0.5 text-[11px] font-semibold text-ink-soft">
              cached
            </span>
          )}
        </div>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-forest-700 hover:underline disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: 'Total reports', value: insights.total, sub: 'all time' },
          { label: 'Pending', value: pending, sub: 'awaiting action' },
          { label: 'Critical & high', value: insights.critical_high, sub: 'priority' },
          { label: 'Last 24 hours', value: insights.recent_24h, sub: 'new reports' },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-earth-100 bg-white p-4 shadow-card"
          >
            <p className="text-xs font-medium text-ink-mute">{item.label}</p>
            <p className="mt-1 text-2xl font-bold text-ink">{item.value}</p>
            <p className="mt-0.5 text-[11px] text-ink-faint">{item.sub}</p>
          </div>
        ))}
      </div>

      {/* Breakdowns */}
      <div className="grid gap-4 md:grid-cols-3">
        <BreakdownCard title="By status" counts={insights.by_status} />
        <BreakdownCard title="By priority" counts={insights.by_priority} />
        <BreakdownCard title="By waste type" counts={insights.by_waste_type} />
      </div>

      {/* Top areas */}
      <section className="rounded-xl border border-earth-100 bg-white shadow-card">
        <div className="border-b border-earth-100 px-5 py-3.5">
          <h3 className="text-sm font-semibold text-ink">Top areas</h3>
          <p className="text-xs text-ink-mute">
            Where reports cluster, joined from the locations table.
          </p>
        </div>
        {insights.top_areas.length === 0 ? (
          <p className="px-5 py-6 text-center text-xs text-ink-mute">
            No locations recorded yet.
          </p>
        ) : (
          <div className="divide-y divide-earth-50">
            {insights.top_areas.map((area) => (
              <div
                key={area.area}
                className="flex items-center justify-between px-5 py-3 text-xs"
              >
                <span className="truncate text-ink-soft">{area.area}</span>
                <span className="ml-3 shrink-0 font-semibold text-ink">
                  {area.count} report{area.count === 1 ? '' : 's'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* SQL log */}
      <section className="rounded-xl border border-earth-100 bg-white shadow-card">
        <button
          onClick={() => setShowSql((open) => !open)}
          className="flex w-full items-center justify-between border-b border-earth-100 px-5 py-3.5 text-left"
        >
          <div>
            <h3 className="text-sm font-semibold text-ink">SQL log</h3>
            <p className="text-xs text-ink-mute">
              Read-only statements Zetaris ran for this view.
            </p>
          </div>
          <ChevronDown
            className={`h-4 w-4 text-ink-mute transition-transform ${
              showSql ? 'rotate-180' : ''
            }`}
          />
        </button>
        {showSql && (
          <div className="divide-y divide-earth-50">
            {insights.queries.map((query) => (
              <QueryRow key={query.name} query={query} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
