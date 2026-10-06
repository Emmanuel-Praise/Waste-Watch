import { useCallback, useEffect, useState } from 'react';
import { Store, HandCoins, Phone, MapPin, IdCard, Loader2, RefreshCw, Check, Ban } from 'lucide-react';
import * as api from '../services/api';
import { Collector, Vendor } from '../types';

const statusBadge: Record<string, string> = {
  active: 'bg-forest-100 text-forest-800',
  pending: 'bg-amber-100 text-amber-800',
  suspended: 'bg-red-100 text-red-700',
};

export function PartnersPanel({ isAdmin }: { isAdmin: boolean }) {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [collectors, setCollectors] = useState<Collector[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [vendorData, collectorData] = await Promise.all([api.getVendors(), api.getCollectors()]);
      setVendors(vendorData);
      setCollectors(collectorData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  const setStatus = async (
    kind: 'vendor' | 'collector',
    id: string,
    status: string
  ) => {
    setBusyId(id);
    try {
      if (kind === 'vendor') await api.setVendorStatus(id, status);
      else await api.setCollectorStatus(id, status);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Update failed');
    } finally {
      setBusyId(null);
    }
  };

  const actionButton = (
    kind: 'vendor' | 'collector',
    id: string,
    status: string
  ) => {
    if (!isAdmin) return null;
    const busy = busyId === id;
    if (status === 'pending') {
      return (
        <button
          onClick={() => setStatus(kind, id, 'active')}
          disabled={busy}
          className="inline-flex items-center gap-1 rounded-lg bg-forest-600 px-2.5 py-1.5 text-[11px] font-semibold text-white transition hover:bg-forest-700 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
          Approve
        </button>
      );
    }
    if (status === 'active') {
      return (
        <button
          onClick={() => setStatus(kind, id, 'suspended')}
          disabled={busy}
          className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-2.5 py-1.5 text-[11px] font-semibold text-red-600 transition hover:bg-red-50 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Ban className="h-3 w-3" />}
          Suspend
        </button>
      );
    }
    return (
      <button
        onClick={() => setStatus(kind, id, 'active')}
        disabled={busy}
        className="inline-flex items-center gap-1 rounded-lg border border-earth-200 px-2.5 py-1.5 text-[11px] font-semibold text-ink-soft transition hover:border-forest-400 hover:text-forest-700 disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
        Reactivate
      </button>
    );
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-7 w-7 animate-spin text-forest-500" />
      </div>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      {/* Vendors */}
      <section className="rounded-xl border border-earth-100 bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-earth-100 px-5 py-3.5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Store className="h-4 w-4 text-earth-600" />
            Waste Vendors
            <span className="rounded-full bg-earth-100 px-2 py-0.5 text-[11px] font-semibold text-earth-800">
              {vendors.length}
            </span>
          </h3>
          <button onClick={load} className="text-xs font-medium text-forest-700 hover:underline">
            <RefreshCw className="inline h-3.5 w-3.5" /> Refresh
          </button>
        </div>
        {vendors.length === 0 ? (
          <p className="px-5 py-8 text-center text-xs text-ink-mute">
            No vendors yet — they sign up via WhatsApp (message “sell” to join).
          </p>
        ) : (
          <div className="divide-y divide-earth-50">
            {vendors.map((vendor) => (
              <div key={vendor.id} className="px-5 py-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">{vendor.business_name}</p>
                  <span className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${statusBadge[vendor.status] ?? statusBadge.suspended}`}
                    >
                      {vendor.status}
                    </span>
                    {actionButton('vendor', vendor.id, vendor.status)}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-ink-mute">Owner: {vendor.owner_name}</p>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-mute">
                  <span className="inline-flex items-center gap-1">
                    <Phone className="h-3 w-3" />
                    {vendor.phone}
                  </span>
                  {vendor.zone && (
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {vendor.zone}
                    </span>
                  )}
                  {vendor.id_card_url && (
                    <a
                      href={vendor.id_card_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 font-medium text-forest-700 hover:underline"
                    >
                      <IdCard className="h-3 w-3" />
                      ID document
                    </a>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {vendor.waste_types.map((type) => (
                    <span key={type} className="rounded-full bg-forest-50 px-2 py-0.5 text-[11px] font-medium capitalize text-forest-700">
                      {type}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Collectors */}
      <section className="rounded-xl border border-earth-100 bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-earth-100 px-5 py-3.5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <HandCoins className="h-4 w-4 text-forest-600" />
            EcoCollectors
            <span className="rounded-full bg-forest-100 px-2 py-0.5 text-[11px] font-semibold text-forest-800">
              {collectors.length}
            </span>
          </h3>
          <button onClick={load} className="text-xs font-medium text-forest-700 hover:underline">
            <RefreshCw className="inline h-3.5 w-3.5" /> Refresh
          </button>
        </div>
        {collectors.length === 0 ? (
          <p className="px-5 py-8 text-center text-xs text-ink-mute">
            No collectors yet — citizens join via WhatsApp (message “earn” to join).
          </p>
        ) : (
          <div className="divide-y divide-earth-50">
            {collectors.map((collector) => (
              <div key={collector.id} className="px-5 py-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">{collector.full_name}</p>
                  <span className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${statusBadge[collector.status] ?? statusBadge.suspended}`}
                    >
                      {collector.status}
                    </span>
                    {actionButton('collector', collector.id, collector.status)}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-mute">
                  <span className="inline-flex items-center gap-1">
                    <Phone className="h-3 w-3" />
                    {collector.phone}
                  </span>
                  {collector.zone && (
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {collector.zone}
                    </span>
                  )}
                  {collector.id_card_url && (
                    <a
                      href={collector.id_card_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 font-medium text-forest-700 hover:underline"
                    >
                      <IdCard className="h-3 w-3" />
                      ID document
                    </a>
                  )}
                </div>
                <div className="mt-2 flex gap-4 text-xs">
                  <span className="rounded-lg bg-earth-50 px-2.5 py-1">
                    <span className="font-semibold text-ink">{collector.jobs_completed}</span>{' '}
                    <span className="text-ink-mute">jobs</span>
                  </span>
                  <span className="rounded-lg bg-forest-50 px-2.5 py-1">
                    <span className="font-semibold text-forest-700">
                      {Math.round(collector.total_earnings).toLocaleString()} FCFA
                    </span>{' '}
                    <span className="text-ink-mute">earned</span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
