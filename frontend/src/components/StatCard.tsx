import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: number;
  icon: LucideIcon;
  color: string;
}
export function StatCard({ title, value, icon: Icon, color }: StatCardProps) {
  const colorClasses: Record<string, { card: string; icon: string }> = {
    'bg-forest-600': { card: 'border-forest-100 bg-white', icon: 'bg-forest-600' },
    'bg-forest-500': { card: 'border-forest-100 bg-white', icon: 'bg-forest-500' },
    'bg-amber-500': { card: 'border-amber-100 bg-white', icon: 'bg-amber-500' },
    'bg-earth-500': { card: 'border-earth-100 bg-white', icon: 'bg-earth-500' },
  };
  const colors = colorClasses[color] ?? colorClasses['bg-forest-600'];
  return (
    <div className={`rounded-xl border p-5 shadow-card transition-shadow duration-200 hover:shadow-lift ${colors.card}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-mute mb-1">{title}</p>
          <p className="text-3xl font-semibold text-ink">{value}</p>
        </div>
        <div className={`rounded-xl p-3 shadow-sm ${colors.icon}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
      </div>
    </div>
  );
}
