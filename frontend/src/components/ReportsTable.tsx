import { useState } from 'react';
import { WasteReport, STATUS_LABELS, PRIORITY_LABELS, WASTE_TYPE_LABELS, WASTE_TYPE_ICONS } from '../types';
import { mediaUrl } from '../services/api';
import { MapPin, Clock, ChevronUp, ChevronDown, Inbox, ImageIcon } from 'lucide-react';

interface ReportsTableProps {
  reports: WasteReport[];
  onSelectReport: (report: WasteReport) => void;
  selectedReportId?: string;
}

type SortKey = 'ticket_id' | 'location' | 'waste_type' | 'priority' | 'status' | 'created_at';
type SortDirection = 'asc' | 'desc';

const statusColors: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-800',
  verified: 'bg-cyan-100 text-cyan-800',
  assigned: 'bg-earth-100 text-earth-800',
  cleared: 'bg-forest-100 text-forest-800',
};

const priorityColors: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-red-100 text-red-700',
  critical: 'bg-red-200 text-red-800',
};

const priorityRank: Record<string, number> = { low: 0, medium: 1, high: 2, critical: 3 };
const statusRank: Record<string, number> = { pending: 0, verified: 1, assigned: 2, cleared: 3 };

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));

  if (hours < 1) return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'Yesterday';
  return `${days} days ago`;
}

interface Column {
  key: SortKey;
  label: string;
  align?: 'left' | 'right';
}

const columns: Column[] = [
  { key: 'ticket_id', label: 'Ticket' },
  { key: 'location', label: 'Location' },
  { key: 'waste_type', label: 'Type' },
  { key: 'priority', label: 'Priority' },
  { key: 'status', label: 'Status' },
  { key: 'created_at', label: 'Reported' },
];

function sortValue(report: WasteReport, key: SortKey): string | number {
  switch (key) {
    case 'ticket_id':
      return report.ticket_id;
    case 'location':
      return report.location.address;
    case 'waste_type':
      return report.waste_type;
    case 'priority':
      return priorityRank[report.priority];
    case 'status':
      return statusRank[report.status];
    case 'created_at':
      return new Date(report.created_at).getTime();
  }
}

export function ReportsTable({ reports, onSelectReport, selectedReportId }: ReportsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<SortDirection>('desc');

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sorted = [...reports].sort((a, b) => {
    const aVal = sortValue(a, sortKey);
    const bVal = sortValue(b, sortKey);
    const result = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return sortDir === 'asc' ? result : -result;
  });

  return (
    <div className="bg-white rounded-lg shadow-card border border-earth-100 overflow-hidden lg:max-h-[calc(100vh-15rem)] lg:overflow-y-auto">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-earth-50 border-b border-earth-100">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-ink-mute uppercase tracking-wider">
                Photo
              </th>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left text-xs font-semibold text-ink-mute uppercase tracking-wider cursor-pointer select-none hover:text-ink"
                  onClick={() => handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {sortKey === col.key ? (
                      sortDir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-ink-faint" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-earth-50">
            {sorted.map((report) => (
              <tr
                key={report.id}
                onClick={() => onSelectReport(report)}
                className={`cursor-pointer transition-colors duration-150 ${
                  selectedReportId === report.id
                    ? 'bg-forest-50 hover:bg-forest-100/70'
                    : 'hover:bg-earth-50'
                }`}
              >
                <td className="px-4 py-3">
                  {report.image_url ? (
                    <img
                      src={mediaUrl(report.image_url)}
                      alt=""
                      loading="lazy"
                      className="w-12 h-12 rounded-md object-cover border border-earth-200"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-md bg-earth-50 border border-earth-100 flex items-center justify-center">
                      <ImageIcon className="w-4 h-4 text-ink-faint" />
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm font-medium text-ink">
                    {report.ticket_id}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-ink-faint flex-shrink-0" />
                    <span className="text-sm text-ink-soft truncate max-w-[150px]" title={report.location.address}>
                      {report.location.address}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm text-ink-soft">
                    {WASTE_TYPE_ICONS[report.waste_type]} {WASTE_TYPE_LABELS[report.waste_type]}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${priorityColors[report.priority]}`}>
                    {PRIORITY_LABELS[report.priority]}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[report.status]}`}>
                    {STATUS_LABELS[report.status]}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5 text-ink-mute">
                    <Clock className="w-3.5 h-3.5" />
                    <span className="text-sm">{formatDate(report.created_at)}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {reports.length === 0 && (
        <div className="p-12 text-center">
          <Inbox className="w-10 h-10 text-ink-faint mx-auto mb-3" />
          <p className="text-sm font-medium text-ink-soft mb-1">No reports yet</p>
          <p className="text-xs text-ink-faint">
            Voice, photo and WhatsApp reports will appear here automatically.
          </p>
        </div>
      )}
    </div>
  );
}