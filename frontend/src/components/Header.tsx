import { RefreshCw, PanelLeft } from 'lucide-react';

interface HeaderProps {
  onRefresh: () => void;
  isLoading: boolean;
  title?: string;
  onMenu: () => void;
}

export function Header({ onRefresh, isLoading, title = 'Bamenda Waste Management', onMenu }: HeaderProps) {
  return (
    <header className="bg-forest-800 text-white px-4 md:px-6 py-3 shadow-lg sticky top-0 z-30">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onMenu}
            className="md:hidden p-2 rounded-lg hover:bg-white/10 -ml-1"
            aria-label="Open menu"
          >
            <PanelLeft className="w-5 h-5" />
          </button>
          <div className="min-w-0">
            <h1 className="text-lg md:text-xl font-semibold truncate">{title}</h1>
            <p className="text-[11px] text-forest-100/80 truncate hidden sm:block">
              Waste Watch · Council Operations
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className={`p-2 rounded-lg hover:bg-white/10 transition-colors ${
              isLoading ? 'animate-spin' : ''
            }`}
            title="Refresh data"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2 pl-3 border-l border-white/20">
            <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
              <span className="text-sm font-medium">A</span>
            </div>
            <div className="hidden md:block">
              <p className="text-sm font-medium">Admin</p>
              <p className="text-xs text-white/70">Operator</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}