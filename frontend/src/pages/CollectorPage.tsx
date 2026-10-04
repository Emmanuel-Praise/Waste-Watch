import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  HandCoins,
  MapPin,
  Scale,
  Wallet,
  Loader2,
  Briefcase,
  PackageCheck,
  Truck,
  BadgeCheck,
} from 'lucide-react';
import * as api from '../services/api';
import {
  Claim,
  ClaimStatus,
  Collector,
  WasteType,
  WASTE_TYPE_ICONS,
  WASTE_TYPE_LABELS,
  CLAIM_STATUS_LABELS,
} from '../types';

const inputClass =
  'w-full rounded-lg border border-earth-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-forest-500 focus:ring-2 focus:ring-forest-100';

const claimStatusBadge: Record<string, string> = {
  reserved: 'bg-amber-100 text-amber-800',
  collecting: 'bg-cyan-100 text-cyan-800',
  collected: 'bg-earth-100 text-earth-800',
  delivered: 'bg-forest-100 text-forest-800',
  paid: 'bg-forest-600 text-white',
  cancelled: 'bg-red-100 text-red-700',
};

function JobCard({
  claim,
  action,
  actionLabel,
  actionIcon: ActionIcon,
  busy,
}: {
  claim: Claim;
  action?: () => void;
  actionLabel?: string;
  actionIcon?: typeof Truck;
  busy?: boolean;
}) {
  return (
    <article className="flex flex-col rounded-2xl border border-earth-100 bg-white p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <span className="inline-flex items-center gap-2 rounded-full bg-forest-50 px-3 py-1 text-xs font-semibold text-forest-700">
          <span>{WASTE_TYPE_ICONS[(claim.listing?.waste_type ?? 'mixed') as WasteType] ?? '🗑️'}</span>
          {WASTE_TYPE_LABELS[(claim.listing?.waste_type ?? 'mixed') as WasteType] ?? claim.listing?.waste_type}
        </span>
        <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${claimStatusBadge[claim.status]}`}>
          {CLAIM_STATUS_LABELS[claim.status]}
        </span>
      </div>

      <p className="mt-3 flex items-start gap-1.5 text-sm text-ink-soft">
        <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-earth-500" />
        <span className="line-clamp-2">{claim.listing?.report_address ?? 'Location on dashboard'}</span>
      </p>

      <div className="mt-3 flex items-center gap-4 text-xs text-ink-mute">
        <span className="inline-flex items-center gap-1">
          <Scale className="h-3.5 w-3.5" />
          {Math.round(claim.quantity_kg)} kg
        </span>
        <span className="inline-flex items-center gap-1 font-semibold text-forest-700">
          <Wallet className="h-3.5 w-3.5" />
          You earn {Math.round(claim.collector_payout)} FCFA
        </span>
      </div>

      {action && actionLabel && (
        <button
          onClick={action}
          disabled={busy}
          className="mt-4 inline-flex items-center justify-center gap-2 rounded-lg bg-forest-600 py-2.5 text-xs font-semibold text-white transition hover:bg-forest-700 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : ActionIcon && <ActionIcon className="h-3.5 w-3.5" />}
          {actionLabel}
        </button>
      )}
    </article>
  );
}

export function CollectorPage() {
  const [collectors, setCollectors] = useState<Collector[]>([]);
  const [meId, setMeId] = useState('');
  const [availableClaims, setAvailableClaims] = useState<Claim[]>([]);
  const [myClaims, setMyClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyClaimId, setBusyClaimId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [collectorData, reserved] = await Promise.all([
        api.getCollectors(),
        api.getClaims({ status: 'reserved' }),
      ]);
      setCollectors(collectorData);
      setAvailableClaims(reserved);
      if (meId) {
        setMyClaims(await api.getClaims({ collector_id: meId }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, [meId]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  const me = useMemo(() => collectors.find((c) => c.id === meId) ?? null, [collectors, meId]);

  const takeJob = async (claim: Claim) => {
    if (!meId) return;
    setBusyClaimId(claim.id);
    setError(null);
    try {
      await api.takeCollectorJob(claim.id, meId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not take this job');
    } finally {
      setBusyClaimId(null);
    }
  };

  const advance = async (claim: Claim, status: ClaimStatus) => {
    setBusyClaimId(claim.id);
    setError(null);
    try {
      await api.updateClaimStatus(claim.id, status);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed');
    } finally {
      setBusyClaimId(null);
    }
  };

  const totalEarnedOnPlatform = myClaims
    .filter((c) => ['delivered', 'paid'].includes(c.status))
    .reduce((sum, c) => sum + (c.collector_payout || 0), 0);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <div className="mb-8">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-ink md:text-3xl">
          <HandCoins className="h-7 w-7 text-forest-600" />
          Earn as EcoCollector
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-ink-mute">
          Pick up reserved waste, sort it, deliver it to the vendor — and get paid 55% of
          every deal you complete. Sign up first on the Services page.
        </p>
      </div>

      {/* Identity picker + earnings */}
      <div className="mb-8 grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-earth-100 bg-white p-5 shadow-card md:col-span-2">
          <label className="text-xs font-medium text-ink-soft">
            <span className="mb-1.5 flex items-center gap-1.5">
              <BadgeCheck className="h-3.5 w-3.5 text-forest-600" />
              I am collecting as
            </span>
            <select className={inputClass} value={meId} onChange={(e) => setMeId(e.target.value)}>
              <option value="">Select your collector account…</option>
              {collectors.map((collector) => (
                <option key={collector.id} value={collector.id}>
                  {collector.full_name} ({collector.phone})
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="rounded-2xl bg-forest-700 p-5 text-white shadow-card">
          <p className="text-xs text-forest-100">
            {me ? `${me.full_name} · lifetime earnings` : 'Select an account to see earnings'}
          </p>
          <p className="mt-1 text-2xl font-bold">
            {me ? `${Math.round(me.total_earnings).toLocaleString()} FCFA` : '—'}
          </p>
          <p className="mt-1 text-xs text-forest-100">
            {me ? `${me.jobs_completed} job${me.jobs_completed === 1 ? '' : 's'} completed` : ' '} ·{' '}
            {Math.round(totalEarnedOnPlatform).toLocaleString()} FCFA on current deliveries
          </p>
        </div>
      </div>

      {error && (
        <p className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-7 w-7 animate-spin text-forest-500" />
        </div>
      ) : (
        <div className="space-y-10">
          {/* Available jobs */}
          <section>
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-soft">
              <Briefcase className="h-4 w-4 text-earth-500" />
              Open pickup jobs
            </h2>
            {availableClaims.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-earth-200 bg-white py-12 text-center">
                <PackageCheck className="mx-auto h-9 w-9 text-ink-faint" />
                <p className="mt-2 text-sm text-ink-mute">
                  No open jobs right now — check back shortly, new reservations arrive in real time.
                </p>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {availableClaims.map((claim) => (
                  <JobCard
                    key={claim.id}
                    claim={claim}
                    action={meId ? () => takeJob(claim) : undefined}
                    actionLabel={meId ? 'Take this job' : 'Select an account first'}
                    actionIcon={Truck}
                    busy={busyClaimId === claim.id}
                  />
                ))}
              </div>
            )}
          </section>

          {/* My jobs */}
          {meId && (
            <section>
              <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-soft">
                <Truck className="h-4 w-4 text-earth-500" />
                My jobs
              </h2>
              {myClaims.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-earth-200 bg-white py-12 text-center">
                  <p className="text-sm text-ink-mute">Take your first job above to start earning.</p>
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {myClaims.map((claim) => {
                    let actionLabel: string | undefined;
                    let next: ClaimStatus | undefined;
                    if (claim.status === 'collecting') {
                      actionLabel = 'Mark as collected';
                      next = 'collected';
                    } else if (claim.status === 'collected') {
                      actionLabel = 'Mark as delivered to vendor';
                      next = 'delivered';
                    }
                    return (
                      <JobCard
                        key={claim.id}
                        claim={claim}
                        action={next ? () => advance(claim, next) : undefined}
                        actionLabel={actionLabel}
                        actionIcon={PackageCheck}
                        busy={busyClaimId === claim.id}
                      />
                    );
                  })}
                </div>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
