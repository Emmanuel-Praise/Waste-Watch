import { Link, NavLink } from 'react-router-dom';
import { Trash2, Mic, Store, HandCoins, LayoutDashboard } from 'lucide-react';

const LINKS = [
  { to: '/report', label: 'Report Waste', icon: Mic },
  { to: '/market', label: 'Marketplace', icon: Store },
  { to: '/collector', label: 'Earn as Collector', icon: HandCoins },
];

export function PublicNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-earth-200/70 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-forest-600 text-white">
            <Trash2 className="h-5 w-5" />
          </span>
          <span className="leading-tight">
            <span className="block text-base font-semibold text-ink">Waste Watch</span>
            <span className="block text-[11px] text-ink-mute">Bamenda Municipality</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? 'bg-forest-50 text-forest-700'
                    : 'text-ink-soft hover:bg-earth-50 hover:text-ink'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
          <NavLink
            to="/services"
            className={({ isActive }) =>
              `inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? 'bg-earth-50 text-earth-700'
                  : 'text-ink-soft hover:bg-earth-50 hover:text-ink'
              }`
            }
          >
            Our Services
          </NavLink>
        </nav>

        <div className="flex items-center gap-2">
          <Link
            to="/report"
            className="hidden rounded-lg bg-forest-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-forest-700 sm:block"
          >
            Report Now
          </Link>
          <Link
            to="/admin"
            title="Council dashboard"
            className="inline-flex items-center gap-2 rounded-lg border border-earth-200 px-3 py-2 text-sm font-medium text-ink-soft transition hover:border-forest-400 hover:text-forest-700"
          >
            <LayoutDashboard className="h-4 w-4" />
            <span className="hidden sm:inline">Dashboard</span>
          </Link>
        </div>
      </div>

      {/* Mobile quick links */}
      <nav className="flex items-center gap-1 overflow-x-auto border-t border-earth-100 px-3 py-2 md:hidden">
        {LINKS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                isActive ? 'bg-forest-50 text-forest-700' : 'text-ink-soft'
              }`
            }
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </NavLink>
        ))}
        <NavLink
          to="/services"
          className={({ isActive }) =>
            `inline-flex shrink-0 items-center rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              isActive ? 'bg-earth-50 text-earth-700' : 'text-ink-soft'
            }`
          }
        >
          Our Services
        </NavLink>
      </nav>
    </header>
  );
}
