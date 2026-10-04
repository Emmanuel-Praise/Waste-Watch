import { LayoutDashboard, FileText, MapPin, Store, Users, Trash2, X } from 'lucide-react';

export type SidebarView = 'overview' | 'reports' | 'map' | 'market' | 'partners';

interface SidebarProps {
  active: SidebarView;
  onNavigate: (view: SidebarView) => void;
  live?: boolean;
  open: boolean;
  onClose: () => void;
}

const NAV: { id: SidebarView; label: string; icon: typeof LayoutDashboard; group: string }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, group: 'Operations' },
  { id: 'reports', label: 'Reports', icon: FileText, group: 'Operations' },
  { id: 'map', label: 'Waste Map', icon: MapPin, group: 'Operations' },
  { id: 'market', label: 'Marketplace', icon: Store, group: 'Business' },
  { id: 'partners', label: 'Vendors & Collectors', icon: Users, group: 'Business' },
];

export function Sidebar({ active, onNavigate, live = false, open, onClose }: SidebarProps) {
  let lastGroup = '';

  return (
    <>
      <div
        className={`fixed inset-0 bg-black/40 z-40 md:hidden ${open ? 'block' : 'hidden'}`}
        onClick={onClose}
      />
      <aside
        className={`fixed md:sticky top-0 z-50 md:z-auto h-screen w-64 shrink-0 flex-col bg-ink text-white ${
          open ? 'flex' : 'hidden'
        } md:flex`}
      >
        <div className="p-5 flex items-center gap-3">
          <div className="p-2 bg-forest-500 rounded-lg shadow-lg">
            <Trash2 className="w-6 h-6" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold leading-tight truncate">Waste Watch</h1>
            <p className="text-[11px] text-white/50">Bamenda Municipality</p>
          </div>
          <button
            onClick={onClose}
            className="ml-auto md:hidden p-1 rounded-lg hover:bg-white/10"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
          {NAV.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.id;
            const showGroup = item.group !== lastGroup;
            lastGroup = item.group;
            return (
              <div key={item.id}>
                {showGroup && (
                  <p className="px-3 pt-4 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-white/35">
                    {item.group}
                  </p>
                )}
                <button
                  onClick={() => {
                    onNavigate(item.id);
                    onClose();
                  }}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-forest-600/90 text-white shadow-sm'
                      : 'text-white/65 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  {item.label}
                </button>
              </div>
            );
          })}
        </nav>

        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-2 px-1 mb-3">
            <span className={`w-2 h-2 rounded-full ${live ? 'bg-forest-400' : 'bg-white/30'}`} />
            <span className="text-xs text-white/60">
              {live ? 'WhatsApp connected' : 'WhatsApp not connected'}
            </span>
          </div>
          <div className="flex items-center gap-3 bg-white/5 rounded-lg p-3">
            <div className="w-9 h-9 bg-forest-600 rounded-full flex items-center justify-center text-sm font-medium shrink-0">
              A
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">Council Admin</p>
              <p className="text-xs text-white/50">Operations</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
