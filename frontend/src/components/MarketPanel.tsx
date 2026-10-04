import { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw, Scale, Wallet, MapPin, PackageCheck } from 'lucide-react';
import * as api from '../services/api';
import {
  Claim,
  Listing,
  MarketStats,
  WasteType,
  WASTE_TYPE_ICONS,
  WASTE_TYPE_LABELS,
  CLAIM_STATUS_LABELS,
  CLAIM_FLOW,
} from '../types';

const listingStatusBadge: Record<string, string> = {
  available: 'bg-forest-100 text-forest-800',
  partially_claimed: 'bg-earth-100 text-earth-800',
  reserved: 'bg-amber-100 text-amber-800',
  completed: 'bg-ink text-white',
};

const claimStatusBadge: Record<string, string> = {
  reserved: 'bg-amber-100 text-amber-800',
  collecting: 'bg-cyan-100 text-cyan-800',
  collected: 'bg-earth-100 text-earth-800',
  delivered: 'bg-forest-100 text-forest-800',
  paid: 'bg-forest-600 text-white',
  cancelled: 'bg-red-100 text-red-700',
};

const money = (value: number) => `${Math.round(value).toLocaleString()} FCFA`;

export function MarketPanel() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [stats, setStats] = useState<MarketStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [listingData, claimData, statsData] = await Promise.all([
        api.getListings(),
        api.getClaims(),
        api.getMarketStats(),
      ]);
      setListings(listingData);
      setClaims(claimData);
      setStats(statsData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 20000);
    return () => window.clearInterval(timer);
  }, [load]);

  const advance = async (claim: Claim, status: string) => {
    setBusyId(claim.id);
    try {
      await api.updateClaimStatus(claim.id, status);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Update failed');
    } finally {
      setBusyId(null);
    }
  };

  const activeClaims = claims.filter((c) => !['cancelled', 'paid'].includes(c.status));
  const pastClaims = claims.filter((c) => ['cancelled', 'paid'].includes(c.status));

  return (
    <div className="space-y-6">
      {/* Money strip */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: 'Waste listed', value: `${Math.round(stats?.total_kg ?? 0)} kg`, sub: `${stats?.listings ?? 0} listings` },
          { label: 'Available for pickup', value: `${Math.round(stats?.available_kg ?? 0)} kg`, sub: `${Math.round(stats?.reserved_kg ?? 0)} kg reserved` },
          { label: 'Sold & delivered', value: `${Math.round(stats?.sold_kg ?? 0)} kg`, sub: `${stats?.completed_claims ?? 0} completed deals` },
          { label: 'Paid to citizens', value: money(stats?.paid_out_fcfa ?? 0), sub: `${money(stats?.gmv_fcfa ?? 0)} total deal value` },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-earth-100 bg-white p-4 shadow-card">
            <p className="text-xs font-medium text-ink-mute">{item.label}</p>
            <p className="mt-1 text-xl font-bold text-ink">{item.value}</p>
            <p className="mt-0.5 text-[11px] text-ink-faint">{item.sub}</p>
          </div>
        ))}
      </div>

      {/* Active claims */}
      <section className="rounded-xl border border-earth-100 bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-earth-100 px-5 py-3.5">
          <h3 className="text-sm font-semibold text-ink">Active deals</h3>
          <button onClick={load} className="inline-flex items-center gap-1.5 text-xs font-medium text-forest-700 hover:underline">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
        {activeClaims.length === 0 ? (
          <p className="px-5 py-8 text-center text-xs text-ink-mute">
            No active deals. Vendor reservations on listings appear here for follow-up.
          </p>
        ) : (
          <div className="divide-y divide-earth-50">
            {activeClaims.map((claim) => {
              const nextStatus = CLAIM_FLOW[Math.min(CLAIM_FLOW.indexOf(claim.status) + 1, CLAIM_FLOW.length - 1)];
              const canAdvance = claim.status !== 'paid' && CLAIM_FLOW.indexOf(claim.status) >= 0 && claim.status !== 'delivered';
              return (
                <div key={claim.id} className="flex flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-ink">
                          {WASTE_TYPE_ICONS[(claim.listing?.waste_type ?? 'mixed') as WasteType]} {Math.round(claim.quantity_kg)} kg{' '}
                          {WASTE_TYPE_LABELS[(claim.listing?.waste_type ?? 'mixed') as WasteType]}
                        </span>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${claimStatusBadge[claim.status]}`}>
                        {CLAIM_STATUS_LABELS[claim.status]}
                      </span>
                    </div>
                    <p className="mt-1 flex items-center gap-1 text-xs text-ink-mute">
                      <MapPin className="h-3 w-3" />
                      {claim.listing?.report_address ?? '—'} · Vendor:{' '}
                      <span className="font-medium text-ink-soft">{claim.vendor?.business_name ?? '—'}</span>
                      {claim.collector && <> · Collector: <span className="font-medium text-ink-soft">{claim.collector.full_name}</span></>}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right text-xs">
                      <p className="font-semibold text-ink">{money(claim.total_value)}</p>
                      <p className="flex items-center justify-end gap-1 text-ink-mute">
                        <Wallet className="h-3 w-3" />
                        reporter {money(claim.reporter_commission)} · collector {money(claim.collector_payout)}
                      </p>
                    </div>
                    {canAdvance && (
                      <button
                        onClick={() => advance(claim, nextStatus)}
                        disabled={busyId === claim.id}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-forest-600 px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-forest-700 disabled:opacity-50"
                      >
                        {busyId === claim.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <PackageCheck className="h-3.5 w-3.5" />
                        )}
                        Mark {CLAIM_STATUS_LABELS[nextStatus]}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Listings */}
      <section className="rounded-xl border border-earth-100 bg-white shadow-card">
        <div className="border-b border-earth-100 px-5 py-3.5">
          <h3 className="text-sm font-semibold text-ink">Listings</h3>
          <p className="text-xs text-ink-mute">
            Auto-created from sellable reports. Partial reservations leave the rest open for the community.
          </p>
        </div>
        <div className="divide-y divide-earth-50">
          {listings.length === 0 && (
            <p className="px-5 py-8 text-center text-xs text-ink-mute">
              No listings yet — plastic, organic and mixed reports create them automatically.
            </p>
          )}
          {listings.map((listing) => {
            const claimedPct = Math.round(((listing.quantity_kg - listing.available_kg) / listing.quantity_kg) * 100);
            return (
              <div key={listing.id} className="px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink">
                      {WASTE_TYPE_ICONS[listing.waste_type]} {Math.round(listing.available_kg)} kg available
                    </span>
                    <span className="text-xs text-ink-mute">of {Math.round(listing.quantity_kg)} kg</span>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${listingStatusBadge[listing.status]}`}>
                      {listing.status.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="inline-flex items-center gap-1 text-ink-mute">
                      <Scale className="h-3 w-3" />
                      {listing.price_per_kg} FCFA/kg
                    </span>
                    <span className="font-medium text-earth-700">{listing.report.ticket_id}</span>
                  </div>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-earth-100">
                  <div className="h-full rounded-full bg-forest-500" style={{ width: `${Math.max(3, 100 - claimedPct)}%` }} />
                </div>
                {listing.claims.length > 0 && (
                  <p className="mt-1.5 text-[11px] text-ink-mute">
                    {listing.claims.filter((c) => c.status !== 'cancelled').length} reservation(s)
                    {' · '}community portion: {Math.round(listing.available_kg)} kg
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* History */}
      {pastClaims.length > 0 && (
        <section className="rounded-xl border border-earth-100 bg-white shadow-card">
          <div className="border-b border-earth-100 px-5 py-3.5">
            <h3 className="text-sm font-semibold text-ink">Deal history</h3>
          </div>
          <div className="divide-y divide-earth-50">
            {pastClaims.map((claim) => (
              <div key={claim.id} className="flex items-center justify-between px-5 py-3 text-xs">
                <span className="text-ink-soft">
                  {WASTE_TYPE_ICONS[(claim.listing?.waste_type ?? 'mixed') as WasteType]} {Math.round(claim.quantity_kg)} kg ·{' '}
                  {claim.vendor?.business_name ?? '—'}
                  {claim.collector ? ` → ${claim.collector.full_name}` : ''}
                </span>
                <span className="flex items-center gap-3">
                  <span className="font-semibold text-ink">{money(claim.total_value)}</span>
                  <span className={`rounded-full px-2 py-0.5 font-semibold ${claimStatusBadge[claim.status]}`}>
                    {CLAIM_STATUS_LABELS[claim.status]}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
