import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Store,
  MapPin,
  Scale,
  Coins,
  Loader2,
  X,
  CheckCircle2,
  Info,
  PackageSearch,
} from 'lucide-react';
import * as api from '../services/api';
import { Listing, Vendor, WASTE_TYPE_ICONS, WASTE_TYPE_LABELS } from '../types';

const inputClass =
  'w-full rounded-lg border border-earth-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-forest-500 focus:ring-2 focus:ring-forest-100';

function AvailabilityBar({ listing }: { listing: Listing }) {
  const claimedPct = Math.round(((listing.quantity_kg - listing.available_kg) / listing.quantity_kg) * 100);
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-ink-soft">
          {Math.round(listing.available_kg)} kg available
        </span>
        <span className="text-ink-mute">of {Math.round(listing.quantity_kg)} kg</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-earth-100">
        <div
          className="h-full rounded-full bg-forest-500 transition-all"
          style={{ width: `${Math.max(4, 100 - claimedPct)}%` }}
        />
      </div>
      {claimedPct > 0 && claimedPct < 100 && (
        <p className="mt-1.5 flex items-center gap-1 text-[11px] text-earth-700">
          <Info className="h-3 w-3" />
          {claimedPct}% reserved by vendors — the rest stays open for community pickup
        </p>
      )}
      {claimedPct >= 100 && (
        <p className="mt-1.5 text-[11px] font-medium text-earth-700">
          Fully reserved — awaiting collection & delivery
        </p>
      )}
    </div>
  );
}

interface ReserveModalProps {
  listing: Listing;
  vendors: Vendor[];
  onClose: () => void;
  onReserved: () => void;
}

function ReserveModal({ listing, vendors, onClose, onReserved }: ReserveModalProps) {
  const [vendorId, setVendorId] = useState('');
  const [quantity, setQuantity] = useState<number>(Math.round(listing.available_kg));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ total: number; commission: number; payout: number } | null>(null);

  const clamped = Math.max(0.1, Math.min(quantity || 0, listing.available_kg));
  const total = clamped * listing.price_per_kg;

  const submit = async () => {
    if (!vendorId) {
      setError('Select your vendor account first (sign up on the Services page if new).');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const claim = await api.reserveListingQuantity(listing.id, vendorId, clamped);
      setDone({ total: claim.total_value, commission: claim.reporter_commission, payout: claim.collector_payout });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reservation failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        {done ? (
          <div className="text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-forest-600" />
            <h3 className="mt-3 text-lg font-bold text-ink">Quantity reserved!</h3>
            <p className="mt-1 text-sm text-ink-mute">
              {Math.round(clamped)} kg of {WASTE_TYPE_LABELS[listing.waste_type].toLowerCase()} waste is now yours.
              An EcoCollector can now take the pickup job.
            </p>
            <div className="mt-4 space-y-1.5 rounded-xl bg-cream p-4 text-left text-xs">
              <div className="flex justify-between"><span className="text-ink-mute">Deal value</span><span className="font-semibold">{Math.round(done.total)} FCFA</span></div>
              <div className="flex justify-between"><span className="text-ink-mute">Reporter commission</span><span className="font-semibold">{Math.round(done.commission)} FCFA</span></div>
              <div className="flex justify-between"><span className="text-ink-mute">Collector payout</span><span className="font-semibold">{Math.round(done.payout)} FCFA</span></div>
            </div>
            <button
              onClick={() => { onReserved(); onClose(); }}
              className="mt-5 w-full rounded-lg bg-forest-600 py-2.5 text-sm font-semibold text-white hover:bg-forest-700"
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-ink">
                  Reserve {WASTE_TYPE_LABELS[listing.waste_type]} waste
                </h3>
                <p className="text-xs text-ink-mute">
                  {listing.report.ticket_id} · {listing.price_per_kg} FCFA/kg
                </p>
              </div>
              <button onClick={onClose} className="rounded-lg p-1 text-ink-faint hover:bg-earth-100">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-5 space-y-4">
              <label className="block">
                <span className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-ink-soft">
                  <Store className="h-3.5 w-3.5 text-earth-500" />
                  Your vendor account
                </span>
                <select className={inputClass} value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
                  <option value="">Select your account…</option>
                  {vendors.map((vendor) => (
                    <option key={vendor.id} value={vendor.id}>
                      {vendor.business_name} ({vendor.phone})
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-ink-soft">
                  <Scale className="h-3.5 w-3.5 text-earth-500" />
                  Quantity you want (kg) — you can take only part
                </span>
                <input
                  type="number"
                  min={0.1}
                  max={listing.available_kg}
                  step={1}
                  className={inputClass}
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                />
                <span className="mt-1.5 block text-[11px] text-ink-mute">
                  Up to {Math.round(listing.available_kg)} kg available
                </span>
              </label>

              <div className="rounded-xl bg-forest-50 px-4 py-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-ink-mute">
                    <Coins className="h-4 w-4 text-earth-500" />
                    Deal value
                  </span>
                  <span className="font-bold text-forest-700">{Math.round(total).toLocaleString()} FCFA</span>
                </div>
              </div>

              {error && <p className="rounded-lg bg-red-50 px-3.5 py-2.5 text-xs text-red-700">{error}</p>}

              <button
                onClick={submit}
                disabled={busy || !vendorId}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-earth-600 py-3 text-sm font-semibold text-white transition hover:bg-earth-700 disabled:opacity-50"
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                Confirm Reservation
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function MarketPage() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'open' | 'all'>('open');
  const [reserving, setReserving] = useState<Listing | null>(null);

  const load = useCallback(async () => {
    try {
      const [listingData, vendorData] = await Promise.all([api.getListings(), api.getVendors()]);
      setListings(listingData);
      setVendors(vendorData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 20000);
    return () => window.clearInterval(timer);
  }, [load]);

  const visible = useMemo(
    () => (filter === 'open' ? listings.filter((l) => l.available_kg > 0 && l.status !== 'completed') : listings),
    [listings, filter]
  );

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-bold text-ink md:text-3xl">Waste Marketplace</h1>
          <p className="mt-2 max-w-xl text-sm text-ink-mute">
            Reported waste, priced per kg and ready for pickup. Reserve all of it — or only
            the quantity you need. The rest remains for the community.
          </p>
        </div>
        <div className="flex rounded-lg border border-earth-200 bg-white p-1">
          {(['open', 'all'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`rounded-md px-3.5 py-1.5 text-xs font-medium transition ${
                filter === tab ? 'bg-forest-600 text-white' : 'text-ink-mute hover:text-ink'
              }`}
            >
              {tab === 'open' ? 'Open listings' : 'All listings'}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-7 w-7 animate-spin text-forest-500" />
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-earth-200 bg-white py-16 text-center">
          <PackageSearch className="mx-auto h-10 w-10 text-ink-faint" />
          <p className="mt-3 text-sm font-medium text-ink-soft">No listings right now</p>
          <p className="mt-1 text-xs text-ink-mute">
            New voice and photo reports appear here automatically once classified by AI.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((listing) => (
            <article
              key={listing.id}
              className="flex flex-col rounded-2xl border border-earth-100 bg-white p-5 shadow-card transition hover:shadow-lift"
            >
              <div className="flex items-start justify-between">
                <span className="inline-flex items-center gap-2 rounded-full bg-forest-50 px-3 py-1 text-xs font-semibold text-forest-700">
                  <span>{WASTE_TYPE_ICONS[listing.waste_type]}</span>
                  {WASTE_TYPE_LABELS[listing.waste_type]}
                </span>
                <span className="text-[11px] font-medium text-ink-faint">{listing.report.ticket_id}</span>
              </div>

              <p className="mt-3 flex items-start gap-1.5 text-sm text-ink-soft">
                <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-earth-500" />
                <span className="line-clamp-2">{listing.report.location.address}</span>
              </p>

              <div className="mt-4">
                <AvailabilityBar listing={listing} />
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-earth-100 pt-4">
                <div>
                  <p className="text-[11px] text-ink-mute">Price per kg</p>
                  <p className="text-sm font-bold text-earth-700">{listing.price_per_kg} FCFA</p>
                </div>
                <button
                  onClick={() => setReserving(listing)}
                  disabled={listing.available_kg <= 0}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-forest-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-forest-700 disabled:opacity-40"
                >
                  <Store className="h-3.5 w-3.5" />
                  Reserve quantity
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {reserving && (
        <ReserveModal
          listing={reserving}
          vendors={vendors}
          onClose={() => setReserving(null)}
          onReserved={load}
        />
      )}
    </div>
  );
}
