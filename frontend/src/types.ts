// Shared types for waste management system

export type WasteType = 'plastic' | 'organic' | 'mixed' | 'hazardous' | 'medical';
export type Priority = 'low' | 'medium' | 'high' | 'critical';
export type Status = 'pending' | 'verified' | 'assigned' | 'cleared';
export type HazardLevel = 'low' | 'medium' | 'high' | 'critical';
export type Size = 'small' | 'medium' | 'large';

export interface Location {
  lat: number;
  lng: number;
  address: string;
}

export interface StatusHistoryEntry {
  id: string;
  report_id: string;
  from_status: Status | null;
  to_status: Status;
  changed_by: string | null;
  notes: string | null;
  created_at: string;
}

export interface WasteReport {
  id: string;
  ticket_id: string;
  location: Location;
  waste_type: WasteType;
  severity: Priority;
  priority: Priority;
  description: string;
  image_url: string | null;
  status: Status;
  assigned_team_id: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  status_history: StatusHistoryEntry[];
  severity_score: number | null;
  hazard_level: HazardLevel | null;
  estimated_size: Size | null;
  visible_hazards: string[] | null;
  recommended_action: string | null;
  confidence: number | null;
  hotspot_id: string | null;
  related_reports: number;
}

export interface Team {
  id: string;
  name: string;
  area: string;
  active: boolean;
  created_at: string;
}

export interface DashboardStats {
  total: number;
  pending: number;
  verified: number;
  assigned: number;
  cleared: number;
  by_priority: Record<Priority, number>;
  by_type: Record<WasteType, number>;
}

export const STATUS_ORDER: Status[] = ['pending', 'verified', 'assigned', 'cleared'];

export const STATUS_LABELS: Record<Status, string> = {
  pending: 'Pending',
  verified: 'Verified',
  assigned: 'Assigned',
  cleared: 'Cleared'
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical'
};

export const HAZARD_LABELS: Record<HazardLevel, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical'
};

export const SIZE_LABELS: Record<Size, string> = {
  small: 'Small',
  medium: 'Medium',
  large: 'Large'
};

export const WASTE_TYPE_LABELS: Record<WasteType, string> = {
  plastic: 'Plastic',
  organic: 'Organic',
  mixed: 'Mixed',
  hazardous: 'Hazardous',
  medical: 'Medical'
};

export const WASTE_TYPE_ICONS: Record<WasteType, string> = {
  plastic: '🧴',
  organic: '🍃',
  mixed: '🗑️',
  hazardous: '☢️',
  medical: '💉'
};

// ---------------------------------------------------------------------------
// Waste marketplace (business layer)
// ---------------------------------------------------------------------------

export type ListingStatus = 'available' | 'partially_claimed' | 'reserved' | 'completed';
export type ClaimStatus = 'reserved' | 'collecting' | 'collected' | 'delivered' | 'paid' | 'cancelled';

export interface Vendor {
  id: string;
  business_name: string;
  owner_name: string;
  phone: string;
  id_number: string | null;
  id_card_url: string | null;
  waste_types: string[];
  zone: string | null;
  status: string;
  created_at: string;
}

export interface Collector {
  id: string;
  full_name: string;
  phone: string;
  id_number: string | null;
  id_card_url: string | null;
  zone: string | null;
  status: string;
  jobs_completed: number;
  total_earnings: number;
  created_at: string;
}

export interface Payout {
  id: string;
  role: 'reporter' | 'collector' | 'platform';
  payee_name: string | null;
  phone: string | null;
  amount: number;
  status: string;
}

export interface ClaimListingSummary {
  id: string;
  waste_type: string;
  quantity_kg: number;
  report_ticket_id: string | null;
  report_address: string | null;
}

export interface Claim {
  id: string;
  listing_id: string;
  listing: ClaimListingSummary | null;
  vendor: { id: string; business_name: string; phone: string } | null;
  collector: { id: string; full_name: string; phone: string } | null;
  quantity_kg: number;
  price_per_kg: number;
  total_value: number;
  reporter_commission: number;
  collector_payout: number;
  platform_fee: number;
  status: ClaimStatus;
  created_at: string;
  payouts: Payout[];
}

export interface Listing {
  id: string;
  report: WasteReport;
  waste_type: WasteType;
  quantity_kg: number;
  available_kg: number;
  price_per_kg: number;
  status: ListingStatus;
  created_at: string;
  claims: Claim[];
}

export interface ClaimSummary {
  id: string;
  listing_id: string;
  quantity_kg: number;
  total_value: number;
  collector_payout: number;
  reporter_commission: number;
  status: ClaimStatus;
  created_at: string;
  waste_type: string | null;
  location: string | null;
}

export interface MarketStats {
  listings: number;
  total_kg: number;
  available_kg: number;
  reserved_kg: number;
  sold_kg: number;
  active_claims: number;
  completed_claims: number;
  gmv_fcfa: number;
  paid_out_fcfa: number;
  vendors: number;
  collectors: number;
}

export const LISTING_STATUS_LABELS: Record<ListingStatus, string> = {
  available: 'Available',
  partially_claimed: 'Partly Reserved',
  reserved: 'Fully Reserved',
  completed: 'Completed',
};

export const CLAIM_STATUS_LABELS: Record<ClaimStatus, string> = {
  reserved: 'Reserved',
  collecting: 'Collecting',
  collected: 'Collected',
  delivered: 'Delivered',
  paid: 'Paid',
  cancelled: 'Cancelled',
};

export const CLAIM_FLOW: ClaimStatus[] = ['reserved', 'collecting', 'collected', 'delivered', 'paid'];

// ---------------------------------------------------------------------------
// Staff auth (dashboard login: admin + council)
// ---------------------------------------------------------------------------

export interface AppUser {
  id: string;
  name: string;
  email: string;
  role: string;
}

export interface AuthResponse {
  token: string;
  user: AppUser;
}