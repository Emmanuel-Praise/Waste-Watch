import { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { Crosshair, MapPin } from 'lucide-react';
import type { Location } from '../types';

// Fix for default marker icons in React-Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const BAMENDA_CENTER: [number, number] = [5.96, 10.15];

function ClickHandler({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(event) {
      onPick(event.latlng.lat, event.latlng.lng);
    },
  });
  return null;
}

interface LocationPickerProps {
  value: Location | null;
  onChange: (location: Location) => void;
  address: string;
  onAddressChange: (address: string) => void;
}

export function LocationPicker({ value, onChange, address, onAddressChange }: LocationPickerProps) {
  const useMyLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        onChange({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          address: address || 'My current location',
        });
      },
      () => {
        // Silently ignore denial; the user can still click the map.
      }
    );
  };

  // Keep the address field in sync when the user picks a point without an address yet.
  useEffect(() => {
    if (value && !value.address && address) {
      onChange({ ...value, address });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [address]);

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <input
            value={address}
            onChange={(event) => onAddressChange(event.target.value)}
            placeholder="Describe the place (e.g. behind Nkwen Market)"
            className="w-full rounded-lg border border-earth-200 bg-white py-2.5 pl-9 pr-3 text-sm text-ink outline-none transition focus:border-forest-500 focus:ring-2 focus:ring-forest-100"
          />
        </div>
        <button
          type="button"
          onClick={useMyLocation}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-earth-200 bg-white px-4 py-2.5 text-sm font-medium text-ink-soft transition hover:border-forest-400 hover:text-forest-700"
        >
          <Crosshair className="h-4 w-4" />
          Use my location
        </button>
      </div>

      <div className="h-64 overflow-hidden rounded-xl border border-earth-200">
        <MapContainer
          center={value ? [value.lat, value.lng] : BAMENDA_CENTER}
          zoom={value ? 16 : 13}
          className="h-full w-full"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickHandler
            onPick={(lat, lng) =>
              onChange({
                lat,
                lng,
                address: address || `${lat.toFixed(5)}, ${lng.toFixed(5)}`,
              })
            }
          />
          {value && <Marker position={[value.lat, value.lng]} />}
        </MapContainer>
      </div>
      <p className="text-xs text-ink-mute">
        {value
          ? `Picked: ${value.lat.toFixed(5)}, ${value.lng.toFixed(5)}`
          : 'Tap the map to drop a pin where the waste is.'}
      </p>
    </div>
  );
}
