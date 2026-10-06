// API service for backend communication

import {
  WasteReport,
  DashboardStats,
  Team,
  Status,
  Priority,
  Listing,
  Claim,
  ClaimSummary,
  MarketStats,
  Vendor,
  Collector,
  AppUser,
  AuthResponse,
} from '../types';

const _API_ROOT = ((import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? '').replace(/\/$/, '');
const API_BASE = `${_API_ROOT}/api`;

const TOKEN_KEY = 'ww_token';

/** Stored dashboard session token (localStorage, per browser). */
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable - session lasts for this tab only
  }
}

/** fetch wrapper that attaches the staff bearer token to every dashboard call. */
async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string> | undefined) };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

/** Backend origin ('' for local dev proxy). Used to resolve /media image URLs when the API is remote. */
export const API_ROOT = _API_ROOT;

/** Resolve a backend file path (e.g. `/media/abc.jpg`) against the API origin. Absolute URLs pass through. */
export function mediaUrl(url: string | null | undefined): string {
  if (!url) return '';
  if (/^https?:\/\//i.test(url)) return url;
  if (!API_ROOT) return url;
  return `${API_ROOT}${url.startsWith('/') ? '' : '/'}${url}`;
}

async function handleResponse<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    let message = fallback;
    try {
      const body = await response.json();
      if (body && typeof body.detail === 'string' && body.detail) message = body.detail;
    } catch {
      // keep the fallback message
    }
    throw new Error(message);
  }
  return response.json();
}

// Dashboard stats
export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await apiFetch('/dashboard/stats');
  return handleResponse<DashboardStats>(response, 'Failed to fetch stats');
}

// Reports — read-only for the dashboard. New reports arrive via WhatsApp only.
export async function getReports(params?: {
  status?: Status;
  priority?: Priority;
  page?: number;
  limit?: number;
}): Promise<WasteReport[]> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.priority) searchParams.set('priority', params.priority);
  if (params?.page) searchParams.set('page', params.page.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const query = searchParams.toString();
  const response = await apiFetch('/reports' + (query ? `?${query}` : ''));
  return handleResponse<WasteReport[]>(response, 'Failed to fetch reports');
}

export async function getReport(id: string): Promise<WasteReport> {
  const response = await apiFetch(`/reports/${id}`);
  return handleResponse<WasteReport>(response, 'Failed to fetch report');
}

export interface UpdateStatusData {
  status: Status;
  notes?: string;
}

export async function updateReportStatus(id: string, data: UpdateStatusData): Promise<WasteReport> {
  const response = await apiFetch(`/reports/${id}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<WasteReport>(response, 'Failed to update status');
}

export interface AssignTeamData {
  team_id: string;
}

export async function assignReportTeam(id: string, data: AssignTeamData): Promise<WasteReport> {
  const response = await apiFetch(`/reports/${id}/assign`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<WasteReport>(response, 'Failed to assign team');
}

// Teams
export async function getTeams(): Promise<Team[]> {
  const response = await apiFetch('/dashboard/teams');
  return handleResponse<Team[]>(response, 'Failed to fetch teams');
}

// WhatsApp channel status indicator
export interface WhatsAppConfig {
  channel: 'log' | 'whatsapp';
  vision_provider: string;
  speech_provider: string;
  configured: boolean;
}

export async function getWhatsAppConfig(): Promise<WhatsAppConfig> {
  const response = await apiFetch('/whatsapp/config');
  return handleResponse<WhatsAppConfig>(response, 'Failed to fetch channel config');
}

// ---------------------------------------------------------------------------
// Waste marketplace — dashboard reads + council status advances.
// Vendor reservations and collector job-taking happen on WhatsApp only.
// ---------------------------------------------------------------------------

export async function getListings(params?: {
  waste_type?: string;
  status?: string;
  vendor_id?: string;
}): Promise<Listing[]> {
  const searchParams = new URLSearchParams();
  if (params?.waste_type) searchParams.set('waste_type', params.waste_type);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.vendor_id) searchParams.set('vendor_id', params.vendor_id);
  const query = searchParams.toString();
  const response = await apiFetch('/market/listings' + (query ? `?${query}` : ''));
  return handleResponse<Listing[]>(response, 'Failed to fetch listings');
}

export async function getClaims(params?: {
  vendor_id?: string;
  collector_id?: string;
  status?: string;
}): Promise<Claim[]> {
  const searchParams = new URLSearchParams();
  if (params?.vendor_id) searchParams.set('vendor_id', params.vendor_id);
  if (params?.collector_id) searchParams.set('collector_id', params.collector_id);
  if (params?.status) searchParams.set('status', params.status);
  const query = searchParams.toString();
  const response = await apiFetch('/market/claims' + (query ? `?${query}` : ''));
  return handleResponse<Claim[]>(response, 'Failed to fetch claims');
}

export async function updateClaimStatus(claimId: string, status: string): Promise<Claim> {
  const response = await apiFetch(`/market/claims/${claimId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  return handleResponse<Claim>(response, 'Failed to update claim');
}

export async function getMarketStats(): Promise<MarketStats> {
  const response = await apiFetch('/market/stats');
  return handleResponse<MarketStats>(response, 'Failed to fetch market stats');
}

// ---------------------------------------------------------------------------
// Partners — dashboard reads only. Signups happen on WhatsApp.
// ---------------------------------------------------------------------------

export async function getVendors(): Promise<Vendor[]> {
  const response = await apiFetch('/partners/vendors');
  return handleResponse<Vendor[]>(response, 'Failed to fetch vendors');
}

export async function getVendorClaims(vendorId: string): Promise<ClaimSummary[]> {
  const response = await apiFetch(`/partners/vendors/${vendorId}/claims`);
  return handleResponse<ClaimSummary[]>(response, 'Failed to fetch vendor claims');
}

export async function getCollectors(): Promise<Collector[]> {
  const response = await apiFetch('/partners/collectors');
  return handleResponse<Collector[]>(response, 'Failed to fetch collectors');
}

export async function getCollectorJobs(collectorId: string): Promise<ClaimSummary[]> {
  const response = await apiFetch(`/partners/collectors/${collectorId}/jobs`);
  return handleResponse<ClaimSummary[]>(response, 'Failed to fetch collector jobs');
}

export async function setVendorStatus(vendorId: string, status: string): Promise<Vendor> {
  const response = await apiFetch(`/partners/vendors/${vendorId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  return handleResponse<Vendor>(response, 'Failed to update vendor');
}

export async function setCollectorStatus(collectorId: string, status: string): Promise<Collector> {
  const response = await apiFetch(`/partners/collectors/${collectorId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  return handleResponse<Collector>(response, 'Failed to update collector');
}

// ---------------------------------------------------------------------------
// Staff auth (admin + council dashboard login)
// ---------------------------------------------------------------------------

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await apiFetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse<AuthResponse>(response, 'Invalid email or password.');
  setToken(data.token);
  return data;
}

export async function me(): Promise<AppUser> {
  const response = await apiFetch('/auth/me');
  return handleResponse<AppUser>(response, 'Session expired. Please log in again.');
}

export async function logout(): Promise<void> {
  try {
    await apiFetch('/auth/logout', { method: 'POST' });
  } catch {
    // logging out locally even if the server call fails
  }
  setToken(null);
}