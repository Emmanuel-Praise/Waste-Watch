import { useState } from 'react';
import { WasteReport, Team, STATUS_LABELS, PRIORITY_LABELS, WASTE_TYPE_LABELS, HAZARD_LABELS, SIZE_LABELS, STATUS_ORDER, Status } from '../types';
import { mediaUrl } from '../services/api';
import { X, MapPin, Clock, ArrowRight, Sparkles, ShieldAlert, Users } from 'lucide-react';

interface ReportDetailPanelProps {
  report: WasteReport;
  teams: Team[];
  onClose: () => void;
  onStatusChange: (status: Status) => void;
  onAssignTeam: (teamId: string) => void;
}

const statusColors: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-800 border-amber-200',
  verified: 'bg-cyan-100 text-cyan-800 border-cyan-200',
  assigned: 'bg-earth-100 text-earth-800 border-earth-200',
  cleared: 'bg-forest-100 text-forest-800 border-forest-200',
};

const priorityColors: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700 border-gray-200',
  medium: 'bg-amber-100 text-amber-700 border-amber-200',
  high: 'bg-red-100 text-red-700 border-red-200',
  critical: 'bg-red-200 text-red-800 border-red-300',
};

const hazardBadgeColors: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function ReportDetailPanel({
  report,
  teams,
  onClose,
  onStatusChange,
  onAssignTeam
}: ReportDetailPanelProps) {
  const [showStatusDropdown, setShowStatusDropdown] = useState(false);
  const [showTeamDropdown, setShowTeamDropdown] = useState(false);

  const currentIndex = STATUS_ORDER.indexOf(report.status);
  const nextStatuses: Status[] = STATUS_ORDER.slice(currentIndex);
  const isCleared = report.status === 'cleared';
  const assignedTeam = teams.find(t => t.id === report.assigned_team_id);

  return (
    <div className="fixed inset-y-0 right-0 w-[420px] bg-white shadow-2xl z-[1000] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{report.ticket_id}</h2>
          <p className="text-sm text-gray-500">Waste Report Details</p>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
        >
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Status & Priority */}
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="text-xs font-medium text-gray-500 uppercase mb-2 block">Status</label>
            <div className="relative">
              <button
                onClick={() => setShowStatusDropdown(!showStatusDropdown)}
                disabled={isCleared}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border ${statusColors[report.status]} font-medium text-sm ${isCleared ? 'cursor-not-allowed opacity-80' : ''}`}
              >
                {STATUS_LABELS[report.status]}
                {!isCleared && <ArrowRight className="w-4 h-4 ml-2" />}
              </button>
              {isCleared && (
                <p className="text-xs text-gray-500 mt-1">Report cleared &mdash; no further actions.</p>
              )}
              {showStatusDropdown && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
                  {nextStatuses.map((status) => (
                    <button
                      key={status}
                      onClick={() => {
                        onStatusChange(status);
                        setShowStatusDropdown(false);
                      }}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg ${
                        status === report.status ? 'font-semibold cursor-default' : ''
                      } ${statusColors[status]}`}
                    >
                      {STATUS_LABELS[status]}
                      {status === report.status ? ' (current)' : ''}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="flex-1">
            <label className="text-xs font-medium text-gray-500 uppercase mb-2 block">Priority</label>
            <div className={`px-3 py-2 rounded-lg border ${priorityColors[report.priority]} font-medium text-sm`}>
              {PRIORITY_LABELS[report.priority]}
            </div>
          </div>
        </div>

        {/* AI Analysis */}
        {report.confidence != null && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-ink-mute uppercase flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-forest-500" />
                AI Analysis
              </label>
              {report.related_reports > 1 && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-earth-800 bg-earth-50 border border-earth-200 rounded-full px-2 py-0.5">
                  <Users className="w-3 h-3" />
                  {report.related_reports} reports at this location
                </span>
              )}
            </div>
            <div className="rounded-lg border border-gray-200 bg-blue-50/40 overflow-hidden">
              <div className="grid grid-cols-2 gap-px bg-gray-100">
                <div className="bg-white p-3">
                  <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1">Waste type</p>
                  <p className="text-sm font-semibold text-gray-900 uppercase">{WASTE_TYPE_LABELS[report.waste_type]}</p>
                </div>
                <div className="bg-white p-3">
                  <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1">Severity</p>
                  <p className="text-sm font-semibold text-gray-900">
                    {report.severity_score ?? 0} <span className="text-gray-400 font-normal">/ 5</span>
                  </p>
                </div>
                <div className="bg-white p-3">
                  <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1">Hazard</p>
                  {report.hazard_level ? (
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${hazardBadgeColors[report.hazard_level]}`}>
                      <ShieldAlert className="w-3 h-3" />
                      {HAZARD_LABELS[report.hazard_level]}
                    </span>
                  ) : (
                    <span className="text-sm text-gray-400">—</span>
                  )}
                </div>
                <div className="bg-white p-3">
                  <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1">Confidence</p>
                  <p className="text-sm font-semibold text-gray-900">
                    {Math.round((report.confidence ?? 0) * 100)}%
                  </p>
                </div>
              </div>
              {report.estimated_size && (
                <div className="bg-white border-t border-gray-200 px-3 py-2 flex items-center justify-between">
                  <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide">Estimated size</p>
                  <p className="text-sm font-medium text-gray-900">{SIZE_LABELS[report.estimated_size]}</p>
                </div>
              )}
              {report.visible_hazards && report.visible_hazards.length > 0 && (
                <div className="bg-white border-t border-gray-200 px-3 py-2">
                  <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1">Visible hazards</p>
                  <div className="flex flex-wrap gap-1.5">
                    {report.visible_hazards.map((hazard) => (
                      <span key={hazard} className="text-xs text-gray-700 bg-gray-100 rounded px-1.5 py-0.5">{hazard}</span>
                    ))}
                  </div>
                </div>
              )}
              <div className="bg-white border-t border-gray-200 px-3 py-2">
                <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1">AI description</p>
                <p className="text-sm text-gray-700 leading-relaxed">{report.description}</p>
              </div>
              {report.recommended_action && (
                <div className="bg-green-50 border-t border-green-100 px-3 py-2.5">
                  <p className="text-[11px] font-medium text-green-700 uppercase tracking-wide mb-1">Recommended action</p>
                  <p className="text-sm text-green-900 leading-relaxed">{report.recommended_action}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Image */}
        {report.image_url && (
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase mb-2 block">Image</label>
            <div className="rounded-lg overflow-hidden border border-gray-200">
              <img 
                src={mediaUrl(report.image_url)} 
                alt="Waste report"
                className="w-full h-48 object-cover"
              />
            </div>
          </div>
        )}

        {/* Location */}
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase mb-2 block">Location</label>
          <div className="flex items-start gap-2 p-3 bg-gray-50 rounded-lg">
            <MapPin className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm text-gray-900">{report.location.address}</p>
              <p className="text-xs text-gray-500 mt-1">
                {report.location.lat.toFixed(4)}, {report.location.lng.toFixed(4)}
              </p>
            </div>
          </div>
        </div>

        {/* Waste Type */}
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase mb-2 block">Waste Type</label>
          <div className="flex items-center gap-2">
            <span className="text-2xl">
              {report.waste_type === 'plastic' && '🧴'}
              {report.waste_type === 'organic' && '🍃'}
              {report.waste_type === 'mixed' && '🗑️'}
              {report.waste_type === 'hazardous' && '☢️'}
              {report.waste_type === 'medical' && '💉'}
            </span>
            <span className="text-sm font-medium text-gray-900">
              {WASTE_TYPE_LABELS[report.waste_type]}
            </span>
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase mb-2 block">Description</label>
          <p className="text-sm text-gray-700 leading-relaxed">{report.description}</p>
        </div>

        {/* Assignment */}
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase mb-2 block">Assigned Team</label>
          <div className="relative">
            <button
              onClick={() => setShowTeamDropdown(!showTeamDropdown)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50"
            >
              <span className="text-sm text-gray-900">
                {assignedTeam ? assignedTeam.name : 'Select team...'}
              </span>
              <ArrowRight className="w-4 h-4 text-gray-400" />
            </button>
            {showTeamDropdown && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
                <button
                  onClick={() => {
                    onAssignTeam('');
                    setShowTeamDropdown(false);
                  }}
                  className="w-full text-left px-3 py-2 text-sm text-gray-500 hover:bg-gray-50 rounded-t-lg"
                >
                  Unassigned
                </button>
                {teams.map((team) => (
                  <button
                    key={team.id}
                    onClick={() => {
                      onAssignTeam(team.id);
                      setShowTeamDropdown(false);
                    }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                  >
                    {team.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Timestamps */}
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200">
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase mb-1 block">Reported</label>
            <div className="flex items-center gap-1.5 text-sm text-gray-700">
              <Clock className="w-3.5 h-3.5 text-gray-400" />
              {formatDateTime(report.created_at)}
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase mb-1 block">Updated</label>
            <div className="flex items-center gap-1.5 text-sm text-gray-700">
              <Clock className="w-3.5 h-3.5 text-gray-400" />
              {formatDateTime(report.updated_at)}
            </div>
          </div>
        </div>

        {/* Status History */}
        {report.status_history && report.status_history.length > 0 && (
          <div className="pt-4 border-t border-gray-200">
            <label className="text-xs font-medium text-gray-500 uppercase mb-3 block">Status History</label>
            <div className="space-y-3">
              {report.status_history.map((entry) => (
                <div key={entry.id} className="flex items-start gap-3">
                  <div className="flex flex-col items-center">
                    <div className="w-2 h-2 bg-gray-300 rounded-full"></div>
                    <div className="w-px h-full bg-gray-200"></div>
                  </div>
                  <div className="flex-1 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-gray-900">
                        {entry.from_status ? `${entry.from_status} → ${entry.to_status}` : entry.to_status}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{formatDate(entry.created_at)}</p>
                    {entry.notes && (
                      <p className="text-xs text-gray-600 mt-1 italic">{entry.notes}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}