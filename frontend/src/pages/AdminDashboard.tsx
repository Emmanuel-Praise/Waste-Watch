import { useState, useEffect, useCallback } from 'react';
import { Header } from '../components/Header';
import { Sidebar, SidebarView } from '../components/Sidebar';
import { StatCard } from '../components/StatCard';
import { WasteMap } from '../components/WasteMap';
import { ReportsTable } from '../components/ReportsTable';
import { ReportDetailPanel } from '../components/ReportDetailPanel';
import { MarketPanel } from '../components/MarketPanel';
import { PartnersPanel } from '../components/PartnersPanel';
import { WasteReport, DashboardStats, Team, Status } from '../types';
import * as api from '../services/api';
import { FileText, CheckCircle, Users, Clock, AlertCircle, Store } from 'lucide-react';

const VIEW_TITLES: Record<SidebarView, string> = {
  overview: 'Operations Overview',
  reports: 'All Reports',
  map: 'Waste Map',
  market: 'Waste Marketplace',
  partners: 'Vendors & Collectors',
};

export function AdminDashboard() {
  const [view, setView] = useState<SidebarView>('overview');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [live, setLive] = useState(false);
  const [reports, setReports] = useState<WasteReport[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedReport, setSelectedReport] = useState<WasteReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const showActionError = (message: string) => {
    setActionError(message);
    window.setTimeout(() => setActionError(null), 4000);
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [reportsData, statsData, teamsData] = await Promise.all([
        api.getReports(),
        api.getDashboardStats(),
        api.getTeams(),
      ]);
      setReports(reportsData);
      setStats(statsData);
      setTeams(teamsData);
    } catch (err) {
      console.error('Failed to load data:', err);
      setError('Failed to load data. Please ensure the backend is running.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    api
      .getWhatsAppConfig()
      .then((config) => setLive(config.channel === 'whatsapp'))
      .catch(() => setLive(false));
  }, [loadData]);

  // Keep the dashboard live: silently refresh reports + stats every 20s and
  // whenever the tab regains focus, so new submissions appear without a
  // manual refresh.
  const pollData = useCallback(async () => {
    try {
      const [reportsData, statsData] = await Promise.all([
        api.getReports(),
        api.getDashboardStats(),
      ]);
      setReports(reportsData);
      setStats(statsData);
    } catch (err) {
      console.error('Live refresh failed:', err);
    }
  }, []);

  useEffect(() => {
    const timer = window.setInterval(pollData, 20000);
    const onVisible = () => {
      if (document.visibilityState === 'visible') pollData();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [pollData]);

  const handleSelectReport = async (report: WasteReport) => {
    try {
      const fullReport = await api.getReport(report.id);
      setSelectedReport(fullReport);
    } catch (err) {
      console.error('Failed to load report details:', err);
      setSelectedReport(report);
    }
  };

  const handleStatusChange = async (newStatus: Status) => {
    if (!selectedReport) return;

    try {
      const updated = await api.updateReportStatus(selectedReport.id, { status: newStatus });
      setSelectedReport(updated);
      setReports((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));

      const newStats = await api.getDashboardStats();
      setStats(newStats);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update status';
      showActionError(message);
      console.error(message);
    }
  };

  const handleAssignTeam = async (teamId: string) => {
    if (!selectedReport) return;

    try {
      const updated = await api.assignReportTeam(selectedReport.id, { team_id: teamId });
      setSelectedReport(updated);
      setReports((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));

      const newStats = await api.getDashboardStats();
      setStats(newStats);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to assign team';
      showActionError(message);
      console.error(message);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md">
          <h2 className="text-xl font-semibold text-red-600 mb-2">Connection Error</h2>
          <p className="text-ink-mute mb-4">{error}</p>
          <button
            onClick={loadData}
            className="px-4 py-2 bg-forest-600 text-white rounded-lg hover:bg-forest-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream flex">
      <Sidebar
        active={view}
        onNavigate={setView}
        live={live}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Header
          onRefresh={loadData}
          isLoading={isLoading}
          title={VIEW_TITLES[view]}
          onMenu={() => setSidebarOpen(true)}
        />

        {actionError && (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[2000]">
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm font-medium px-4 py-2.5 rounded-lg shadow-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {actionError}
            </div>
          </div>
        )}

        <main className="flex-1 p-4 md:p-6 flex flex-col lg:min-h-0 overflow-y-auto">
          {view === 'overview' && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <StatCard title="Total Reports" value={stats?.total || 0} icon={FileText} color="bg-forest-600" />
                <StatCard title="Pending" value={stats?.pending || 0} icon={Clock} color="bg-amber-500" />
                <StatCard title="Assigned" value={stats?.assigned || 0} icon={Users} color="bg-earth-500" />
                <StatCard title="Cleared" value={stats?.cleared || 0} icon={CheckCircle} color="bg-forest-500" />
              </div>

              <div className="flex flex-col">
                <div className="mb-3 flex items-end justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-ink">Recent Reports</h2>
                    <p className="text-sm text-ink-mute">{reports.length} reports</p>
                  </div>
                  <button
                    onClick={() => setView('map')}
                    className="shrink-0 rounded-lg border border-earth-200 bg-white px-3.5 py-2 text-xs font-semibold text-forest-700 transition hover:border-forest-400 hover:bg-forest-50"
                  >
                    Open Waste Map
                  </button>
                </div>
                <div className="flex-1">
                  <ReportsTable
                    reports={reports}
                    onSelectReport={handleSelectReport}
                    selectedReportId={selectedReport?.id}
                  />
                </div>
              </div>
            </>
          )}

          {view === 'reports' && (
            <div className="flex flex-col h-full">
              <div className="mb-3">
                <h2 className="text-lg font-semibold text-ink">All Reports</h2>
                <p className="text-sm text-ink-mute">
                  {reports.length} reports - select one to view details or update its status
                </p>
              </div>
              <div className="flex-1">
                <ReportsTable
                  reports={reports}
                  onSelectReport={handleSelectReport}
                  selectedReportId={selectedReport?.id}
                />
              </div>
            </div>
          )}

          {view === 'map' && (
            <div className="flex flex-col h-full">
              <div className="mb-3">
                <h2 className="text-lg font-semibold text-ink">Waste Map</h2>
                <p className="text-sm text-ink-mute">Click a marker to inspect a report</p>
              </div>
              <div className="flex-1 min-h-[420px]">
                <WasteMap
                  reports={reports}
                  onSelectReport={handleSelectReport}
                  selectedReportId={selectedReport?.id}
                />
              </div>
            </div>
          )}

          {view === 'market' && (
            <div className="flex flex-col">
              <div className="mb-4 flex items-center gap-2">
                <Store className="h-5 w-5 text-forest-600" />
                <div>
                  <h2 className="text-lg font-semibold text-ink">Waste Marketplace</h2>
                  <p className="text-sm text-ink-mute">
                    Vendor reservations, collection jobs and the money split — all in one place.
                  </p>
                </div>
              </div>
              <MarketPanel />
            </div>
          )}

          {view === 'partners' && (
            <div className="flex flex-col">
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-ink">Vendors & Collectors</h2>
                <p className="text-sm text-ink-mute">
                  The business network: buyers of sorted materials and citizens earning from collection work.
                </p>
              </div>
              <PartnersPanel />
            </div>
          )}
        </main>
      </div>

      {selectedReport && (
        <>
          <div
            className="fixed inset-0 bg-black/20 z-[999] lg:hidden"
            onClick={() => setSelectedReport(null)}
          />
          <ReportDetailPanel
            report={selectedReport}
            teams={teams}
            onClose={() => setSelectedReport(null)}
            onStatusChange={handleStatusChange}
            onAssignTeam={handleAssignTeam}
          />
        </>
      )}
    </div>
  );
}
