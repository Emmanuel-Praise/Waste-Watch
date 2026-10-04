import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { MapPinOff, Users } from 'lucide-react';
import { WasteReport, STATUS_LABELS, PRIORITY_LABELS, WASTE_TYPE_LABELS } from '../types';

// Fix for default marker icons in React-Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Custom marker colors based on priority
const priorityIconColors: Record<string, string> = {
  low: '#78716C',
  medium: '#F59E0B',
  high: '#EA580C',
  critical: '#DC2626',
};

// Custom marker colors based on status
const statusIconColors: Record<string, string> = {
  pending: '#D97706',
  verified: '#0E7490',
  assigned: '#8B5E3C',
  cleared: '#2E7D32',
};

// Create custom colored marker (status ring + priority pin)
function createColoredIcon(priority: string, status: string) {
  const color = priorityIconColors[priority] || '#6B7280';
  const ring = statusIconColors[status] || '#94A3B8';

  // SVG marker with status ring and priority-colored pin
  const svgIcon = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 48" width="36" height="48">
      <defs>
        <filter id="shadow-${priority}-${status}" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.3"/>
        </filter>
      </defs>
      <path fill="${ring}" filter="url(#shadow-${priority}-${status})" d="M18 2C10.8 2 5 7.8 5 15c0 10.5 13 29 13 29s13-18.5 13-29c0-7.2-5.8-13-13-13z"/>
      <circle fill="#FFFFFF" cx="18" cy="15" r="10.5"/>
      <path fill="${color}" d="M18 7.5C13.9 7.5 10.5 10.9 10.5 15c0 5.3 7.5 13.5 7.5 13.5S25.5 20.3 25.5 15C25.5 10.9 22.1 7.5 18 7.5z"/>
    </svg>
  `;

  return L.divIcon({
    html: svgIcon,
    className: 'custom-marker',
    iconSize: [36, 48],
    iconAnchor: [18, 48],
    popupAnchor: [0, -46],
  });
}

// Map center updater component
function MapCenterUpdater({ center }: { center: [number, number] }) {
  const map = useMap();
  const prevCenterRef = useRef(center);
  
  useEffect(() => {
    const prevCenter = prevCenterRef.current;
    if (prevCenter[0] !== center[0] || prevCenter[1] !== center[1]) {
      map.flyTo(center, 14, { duration: 0.5 });
      prevCenterRef.current = center;
    }
  }, [center, map]);
  
  return null;
}

interface WasteMapProps {
  reports: WasteReport[];
  onSelectReport: (report: WasteReport) => void;
  selectedReportId?: string;
}

export function WasteMap({ reports, onSelectReport, selectedReportId }: WasteMapProps) {
  // Default center: Bamenda, Cameroon
  const defaultCenter: [number, number] = [5.96, 10.15];
  
  // Find selected report center
  const selectedReport = reports.find(r => r.id === selectedReportId);
  const center = selectedReport 
    ? [selectedReport.location.lat, selectedReport.location.lng] as [number, number]
    : defaultCenter;
  
  return (
    <div className="h-full w-full relative rounded-lg overflow-hidden shadow-sm border border-gray-200">
      <MapContainer
        center={defaultCenter}
        zoom={13}
        className="h-full w-full"
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapCenterUpdater center={center} />
        {reports.map((report) => (
          <Marker
            key={report.id}
            position={[report.location.lat, report.location.lng]}
            icon={createColoredIcon(report.priority, report.status)}
            eventHandlers={{
              click: () => onSelectReport(report),
            }}
          >
            <Popup>
              <div className="min-w-[200px]">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-gray-900">{report.ticket_id}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    report.status === 'pending' ? 'bg-amber-100 text-amber-700' :
                    report.status === 'verified' ? 'bg-cyan-100 text-cyan-700' :
                    report.status === 'assigned' ? 'bg-earth-100 text-earth-700' :
                    'bg-forest-100 text-forest-700'
                  }`}>
                    {STATUS_LABELS[report.status]}
                  </span>
                </div>
                <div className="text-sm text-gray-600 mb-2">{report.location.address}</div>
                <div className="flex gap-2 mb-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    report.priority === 'low' ? 'bg-gray-100 text-gray-700' :
                    report.priority === 'medium' ? 'bg-amber-100 text-amber-700' :
                    report.priority === 'high' ? 'bg-red-100 text-red-700' :
                    'bg-red-200 text-red-800'
                  }`}>
                    {PRIORITY_LABELS[report.priority]} priority
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                    {WASTE_TYPE_LABELS[report.waste_type]}
                  </span>
                </div>
                {report.related_reports > 1 && (
                  <div className="flex items-center gap-1 text-xs font-medium text-earth-800 mb-2">
                    <Users className="w-3.5 h-3.5" />
                    {report.related_reports} reports at this location
                  </div>
                )}
                <div className="text-xs text-gray-500">
                  Click to view details
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {reports.length === 0 && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center pointer-events-none">
          <div className="bg-white/95 backdrop-blur rounded-xl shadow-lg border border-gray-200 px-6 py-5 text-center">
            <MapPinOff className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm font-medium text-gray-600">No waste reports on the map yet</p>
            <p className="text-xs text-gray-400 mt-1 max-w-[220px]">
              New WhatsApp reports with a location will show up here instantly.
            </p>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 left-3 z-[1000] bg-white/95 backdrop-blur rounded-lg shadow-md border border-gray-200 p-3 text-xs pointer-events-none">
        <div className="grid grid-cols-2 gap-x-5 gap-y-1.5">
          <div>
            <p className="font-semibold text-gray-700 mb-1">Priority</p>
            {(Object.keys(priorityIconColors) as Array<keyof typeof priorityIconColors>).map((key) => (
              <div key={key} className="flex items-center gap-2 py-0.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: priorityIconColors[key] }} />
                <span className="text-gray-600 capitalize">{key}</span>
              </div>
            ))}
          </div>
          <div>
            <p className="font-semibold text-gray-700 mb-1">Status</p>
            {(Object.keys(statusIconColors) as Array<keyof typeof statusIconColors>).map((key) => (
              <div key={key} className="flex items-center gap-2 py-0.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: statusIconColors[key] }} />
                <span className="text-gray-600 capitalize">{key}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}