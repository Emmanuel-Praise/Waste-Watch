import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Mic,
  Store,
  HandCoins,
  ArrowRight,
  ShieldCheck,
  Recycle,
  MapPin,
  Sparkles,
} from 'lucide-react';
import * as api from '../services/api';
import { MarketStats } from '../types';

export function LandingPage() {
  const [stats, setStats] = useState<MarketStats | null>(null);

  useEffect(() => {
    api
      .getMarketStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative overflow-hidden bg-forest-800 text-white">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 30%, #ffffff 0, transparent 40%), radial-gradient(circle at 80% 70%, #CDAD8C 0, transparent 45%)',
          }}
        />
        <div className="mx-auto max-w-6xl px-4 py-16 md:py-24">
          <div className="max-w-2xl">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-forest-100">
              <Sparkles className="h-3.5 w-3.5" />
              Powered by AI · Voice reports via ElevenLabs
            </span>
            <h1 className="mt-5 text-3xl font-bold leading-tight md:text-5xl">
              A cleaner Bamenda, and a living from its waste.
            </h1>
            <p className="mt-4 max-w-xl text-base text-forest-100 md:text-lg">
              Report waste in seconds — by voice or photo. Vendors buy the sorted
              materials, citizens earn commissions and collection jobs, and the
              community stays clean.
            </p>
          </div>

          {/* The two big choices */}
          <div className="mt-10 grid gap-4 md:grid-cols-2">
            <Link
              to="/report"
              className="group rounded-2xl bg-white p-6 text-ink shadow-lift transition hover:-translate-y-0.5 hover:shadow-xl"
            >
              <div className="flex items-start justify-between">
                <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-forest-100 text-forest-700">
                  <Mic className="h-6 w-6" />
                </span>
                <ArrowRight className="h-5 w-5 text-ink-faint transition group-hover:translate-x-1 group-hover:text-forest-600" />
              </div>
              <h2 className="mt-4 text-xl font-semibold">Report Waste</h2>
              <p className="mt-1.5 text-sm text-ink-mute">
                Speak or type what you see, drop a pin, done. Earn a commission
                when a vendor buys the waste you reported.
              </p>
            </Link>

            <Link
              to="/services"
              className="group rounded-2xl bg-earth-600 p-6 text-white shadow-lift transition hover:-translate-y-0.5 hover:shadow-xl"
            >
              <div className="flex items-start justify-between">
                <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/15">
                  <Store className="h-6 w-6" />
                </span>
                <ArrowRight className="h-5 w-5 text-white/60 transition group-hover:translate-x-1" />
              </div>
              <h2 className="mt-4 text-xl font-semibold">View Our Services</h2>
              <p className="mt-1.5 text-sm text-white/80">
                Join as a vendor and buy sorted materials, or become an
                EcoCollector and earn from every job you deliver.
              </p>
            </Link>
          </div>

          {/* Live numbers */}
          {stats && (
            <div className="mt-10 grid grid-cols-2 gap-3 md:grid-cols-4">
              {[
                { label: 'Waste listed', value: `${Math.round(stats.total_kg)} kg` },
                { label: 'Still available', value: `${Math.round(stats.available_kg)} kg` },
                { label: 'Jobs completed', value: stats.completed_claims },
                { label: 'Paid to citizens', value: `${Math.round(stats.paid_out_fcfa)} FCFA` },
              ].map((item) => (
                <div key={item.label} className="rounded-xl bg-white/10 px-4 py-3 backdrop-blur">
                  <p className="text-lg font-semibold md:text-2xl">{item.value}</p>
                  <p className="text-[11px] text-forest-100 md:text-xs">{item.label}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto w-full max-w-6xl px-4 py-14">
        <h2 className="text-center text-2xl font-semibold text-ink">How the circular economy works</h2>
        <p className="mx-auto mt-2 max-w-xl text-center text-sm text-ink-mute">
          Every bag of waste is a resource. Here is how Waste Watch connects the dots.
        </p>
        <div className="mt-10 grid gap-4 md:grid-cols-4">
          {[
            {
              icon: Mic,
              title: '1 · Citizens report',
              text: 'A voice note or photo with a location. The AI classifies the waste and lists it on the marketplace.',
            },
            {
              icon: Store,
              title: '2 · Vendors reserve',
              text: 'Vendors get alerted and reserve all — or just part — of the quantity they want, at a price per kg.',
            },
            {
              icon: HandCoins,
              title: '3 · Collectors deliver',
              text: 'EcoCollectors pick up, sort and deliver to the vendor, and get paid by the platform for the work.',
            },
            {
              icon: ShieldCheck,
              title: '4 · Everyone earns',
              text: 'The reporter earns a commission, the collector earns a payout, the community gets a cleaner city.',
            },
          ].map(({ icon: Icon, title, text }) => (
            <div key={title} className="rounded-2xl border border-earth-100 bg-white p-5 shadow-card">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-earth-100 text-earth-700">
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="mt-3 text-sm font-semibold text-ink">{title}</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-ink-mute">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA strip */}
      <section className="bg-earth-800 text-white">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-10 md:flex-row">
          <div className="flex items-center gap-3">
            <Recycle className="h-8 w-8 text-forest-200" />
            <div>
              <p className="text-lg font-semibold">Have waste to clear? Looking for work?</p>
              <p className="text-sm text-earth-100">
                The marketplace is open — check what is available right now.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <Link
              to="/market"
              className="inline-flex items-center gap-2 rounded-lg bg-forest-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-forest-400"
            >
              <MapPin className="h-4 w-4" />
              Browse Marketplace
            </Link>
            <Link
              to="/collector"
              className="inline-flex items-center gap-2 rounded-lg bg-white/10 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-white/20"
            >
              Find a Job
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
