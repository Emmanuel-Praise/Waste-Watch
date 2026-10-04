import { useState } from 'react';
import {
  Store,
  HandCoins,
  BadgeCheck,
  Loader2,
  CheckCircle2,
  Phone,
  User,
  Building2,
  MapPin,
  IdCard,
  Recycle,
  Leaf,
  Trash2,
  Package,
} from 'lucide-react';
import * as api from '../services/api';
import { Vendor, Collector } from '../types';

const WASTE_TYPE_OPTIONS = [
  { id: 'plastic', label: 'Plastic', icon: Package },
  { id: 'organic', label: 'Organic', icon: Leaf },
  { id: 'mixed', label: 'Mixed', icon: Trash2 },
];

const inputClass =
  'w-full rounded-lg border border-earth-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-forest-500 focus:ring-2 focus:ring-forest-100';

function Field({ icon: Icon, label, children }: { icon: typeof User; label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-ink-soft">
        <Icon className="h-3.5 w-3.5 text-earth-500" />
        {label}
      </span>
      {children}
    </label>
  );
}

function VendorSignup({ onRegistered }: { onRegistered: (vendor: Vendor) => void }) {
  const [form, setForm] = useState({
    business_name: '',
    owner_name: '',
    phone: '',
    zone: '',
    id_number: '',
  });
  const [types, setTypes] = useState<string[]>(['plastic']);
  const [idCard, setIdCard] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleType = (id: string) =>
    setTypes((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));

  const submit = async () => {
    setError(null);
    if (!form.business_name.trim() || !form.owner_name.trim() || form.phone.trim().length < 8) {
      setError('Business name, owner name and a valid phone are required.');
      return;
    }
    if (types.length === 0) {
      setError('Pick at least one waste type you are interested in.');
      return;
    }
    setBusy(true);
    try {
      const vendor = await api.registerVendor({ ...form, waste_types: types, id_card: idCard });
      onRegistered(vendor);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Field icon={Building2} label="Business / buyer name">
        <input
          className={inputClass}
          value={form.business_name}
          onChange={(e) => setForm({ ...form, business_name: e.target.value })}
          placeholder="e.g. GreenPlast Recyclers"
        />
      </Field>
      <Field icon={User} label="Owner name">
        <input
          className={inputClass}
          value={form.owner_name}
          onChange={(e) => setForm({ ...form, owner_name: e.target.value })}
          placeholder="e.g. Ngwa Emmanuel"
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field icon={Phone} label="Phone (WhatsApp)">
          <input
            className={inputClass}
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="+237 6XX XXX XXX"
          />
        </Field>
        <Field icon={MapPin} label="Zone / area">
          <input
            className={inputClass}
            value={form.zone}
            onChange={(e) => setForm({ ...form, zone: e.target.value })}
            placeholder="e.g. Nkwen, Bamenda"
          />
        </Field>
      </div>
      <Field icon={Recycle} label="Waste types you are interested in">
        <div className="flex flex-wrap gap-2">
          {WASTE_TYPE_OPTIONS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => toggleType(id)}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-medium transition ${
                types.includes(id)
                  ? 'border-forest-500 bg-forest-50 text-forest-700'
                  : 'border-earth-200 bg-white text-ink-mute hover:border-earth-400'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>
      </Field>
      <Field icon={IdCard} label="ID card / document">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            className={inputClass}
            value={form.id_number}
            onChange={(e) => setForm({ ...form, id_number: e.target.value })}
            placeholder="ID number"
          />
          <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-earth-200 px-4 py-2.5 text-xs font-medium text-ink-soft transition hover:border-forest-400 hover:text-forest-700">
            {idCard ? idCard.name.slice(0, 22) : 'Upload photo of ID'}
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => setIdCard(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>
      </Field>
      {error && <p className="rounded-lg bg-red-50 px-3.5 py-2.5 text-xs text-red-700">{error}</p>}
      <button
        onClick={submit}
        disabled={busy}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-earth-600 py-3 text-sm font-semibold text-white transition hover:bg-earth-700 disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
        Sign up as Vendor
      </button>
    </div>
  );
}

function CollectorSignup({ onRegistered }: { onRegistered: (collector: Collector) => void }) {
  const [form, setForm] = useState({ full_name: '', phone: '', zone: '', id_number: '' });
  const [idCard, setIdCard] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!form.full_name.trim() || form.phone.trim().length < 8) {
      setError('Full name and a valid phone are required.');
      return;
    }
    setBusy(true);
    try {
      const collector = await api.registerCollector({ ...form, id_card: idCard });
      onRegistered(collector);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Field icon={User} label="Full name">
        <input
          className={inputClass}
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          placeholder="e.g. Achu Blessing"
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field icon={Phone} label="Phone (WhatsApp)">
          <input
            className={inputClass}
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="+237 6XX XXX XXX"
          />
        </Field>
        <Field icon={MapPin} label="Zone you can work">
          <input
            className={inputClass}
            value={form.zone}
            onChange={(e) => setForm({ ...form, zone: e.target.value })}
            placeholder="e.g. Bamenda Central"
          />
        </Field>
      </div>
      <Field icon={IdCard} label="ID card / document">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            className={inputClass}
            value={form.id_number}
            onChange={(e) => setForm({ ...form, id_number: e.target.value })}
            placeholder="ID number"
          />
          <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-earth-200 px-4 py-2.5 text-xs font-medium text-ink-soft transition hover:border-forest-400 hover:text-forest-700">
            {idCard ? idCard.name.slice(0, 22) : 'Upload photo of ID'}
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => setIdCard(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>
      </Field>
      {error && <p className="rounded-lg bg-red-50 px-3.5 py-2.5 text-xs text-red-700">{error}</p>}
      <button
        onClick={submit}
        disabled={busy}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-forest-600 py-3 text-sm font-semibold text-white transition hover:bg-forest-700 disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
        Sign up as EcoCollector
      </button>
    </div>
  );
}

export function ServicesPage() {
  const [registeredVendor, setRegisteredVendor] = useState<Vendor | null>(null);
  const [registeredCollector, setRegisteredCollector] = useState<Collector | null>(null);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <div className="mb-10 text-center">
        <h1 className="text-2xl font-bold text-ink md:text-3xl">Our Services</h1>
        <p className="mx-auto mt-2 max-w-2xl text-sm text-ink-mute">
          Waste Watch turns waste into income. Whether you buy recycled materials or
          you are looking for work, there is a place for you in the loop.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Vendor program */}
        <section className="overflow-hidden rounded-2xl border border-earth-200 bg-white shadow-card">
          <div className="bg-earth-600 px-6 py-5 text-white">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/15">
                <Store className="h-6 w-6" />
              </span>
              <div>
                <h2 className="text-lg font-semibold">Waste Vendor</h2>
                <p className="text-xs text-earth-100">Buy sorted materials at market price</p>
              </div>
            </div>
            <ul className="mt-4 space-y-1.5 text-xs text-earth-50">
              <li>• Get WhatsApp alerts when the waste you buy is reported nearby</li>
              <li>• Reserve all of a listing — or only the part you want (e.g. just the plastic)</li>
              <li>• Uncollected quantities stay open for community pickup</li>
            </ul>
          </div>
          <div className="p-6">
            {registeredVendor ? (
              <div className="rounded-xl border border-forest-200 bg-forest-50 p-5 text-center">
                <CheckCircle2 className="mx-auto h-10 w-10 text-forest-600" />
                <h3 className="mt-3 font-semibold text-ink">Welcome, {registeredVendor.business_name}!</h3>
                <p className="mt-1 text-xs text-ink-mute">
                  You will be alerted when {registeredVendor.waste_types.join(' / ')} waste is reported.
                  Your vendor ID:
                </p>
                <code className="mt-2 inline-block rounded bg-white px-2.5 py-1 text-xs font-semibold text-earth-800">
                  {registeredVendor.id}
                </code>
                <p className="mt-3 text-xs text-ink-mute">
                  Head to the <a href="/market" className="font-medium text-forest-700 underline">marketplace</a> to make your first reservation.
                </p>
              </div>
            ) : (
              <VendorSignup onRegistered={setRegisteredVendor} />
            )}
          </div>
        </section>

        {/* Collector program */}
        <section className="overflow-hidden rounded-2xl border border-earth-200 bg-white shadow-card">
          <div className="bg-forest-700 px-6 py-5 text-white">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/15">
                <HandCoins className="h-6 w-6" />
              </span>
              <div>
                <h2 className="text-lg font-semibold">EcoCollector</h2>
                <p className="text-xs text-forest-100">Earn for every job you deliver</p>
              </div>
            </div>
            <ul className="mt-4 space-y-1.5 text-xs text-forest-50">
              <li>• Pick up reserved waste, sort it, deliver to the vendor</li>
              <li>• The platform pays you <strong>55%</strong> of every deal you complete</li>
              <li>• Build your job history and earnings on your profile</li>
            </ul>
          </div>
          <div className="p-6">
            {registeredCollector ? (
              <div className="rounded-xl border border-forest-200 bg-forest-50 p-5 text-center">
                <CheckCircle2 className="mx-auto h-10 w-10 text-forest-600" />
                <h3 className="mt-3 font-semibold text-ink">Welcome, {registeredCollector.full_name}!</h3>
                <p className="mt-1 text-xs text-ink-mute">Your collector ID:</p>
                <code className="mt-2 inline-block rounded bg-white px-2.5 py-1 text-xs font-semibold text-earth-800">
                  {registeredCollector.id}
                </code>
                <p className="mt-3 text-xs text-ink-mute">
                  Go to <a href="/collector" className="font-medium text-forest-700 underline">Earn as Collector</a> to find your first job.
                </p>
              </div>
            ) : (
              <CollectorSignup onRegistered={setRegisteredCollector} />
            )}
          </div>
        </section>
      </div>

      {/* Community note */}
      <div className="mt-8 rounded-2xl border border-earth-200 bg-earth-50 p-6 text-center">
        <h3 className="text-sm font-semibold text-ink">What about dangerous waste?</h3>
        <p className="mx-auto mt-1.5 max-w-2xl text-xs leading-relaxed text-ink-mute">
          Hazardous and medical waste never enters the marketplace. Those reports are
          escalated straight to the <strong className="text-earth-700">community head</strong> and the
          municipal response teams for safe, licensed handling.
        </p>
      </div>
    </div>
  );
}
