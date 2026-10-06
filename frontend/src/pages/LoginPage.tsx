import { useState } from 'react';
import { Trash2, LogIn, Loader2 } from 'lucide-react';
import * as api from '../services/api';
import { AppUser } from '../types';

export function LoginPage({ onLoggedIn }: { onLoggedIn: (user: AppUser) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await api.login(email.trim(), password);
      onLoggedIn(data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-2xl border border-earth-200 bg-white p-8 shadow-card">
        <div className="flex flex-col items-center text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-forest-600 text-white">
            <Trash2 className="h-6 w-6" />
          </span>
          <h1 className="mt-4 text-xl font-bold text-ink">Waste Watch</h1>
          <p className="mt-1 text-xs text-ink-mute">Bamenda Municipality · Staff login</p>
        </div>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-ink-soft">Email</span>
            <input
              type="email"
              autoComplete="username"
              className="w-full rounded-lg border border-earth-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-forest-500 focus:ring-2 focus:ring-forest-100"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@bamenda.cm"
              required
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-ink-soft">Password</span>
            <input
              type="password"
              autoComplete="current-password"
              className="w-full rounded-lg border border-earth-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-forest-500 focus:ring-2 focus:ring-forest-100"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </label>

          {error && (
            <p className="rounded-lg bg-red-50 px-3.5 py-2.5 text-xs text-red-700">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-forest-600 py-3 text-sm font-semibold text-white transition hover:bg-forest-700 disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
            Log in
          </button>
        </form>

        <p className="mt-5 text-center text-[11px] leading-relaxed text-ink-faint">
          Admin and council accounts only.
          <br />
          Citizens, vendors and collectors use WhatsApp — no login needed.
        </p>
      </div>
    </div>
  );
}
