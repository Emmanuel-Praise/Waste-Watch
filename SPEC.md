# Bamenda Waste Management System - Step 1 Specification

## Project Overview
- **Project Name**: Bamenda Waste Reporting System
- **Type**: Full-stack municipal waste management dashboard
- **Core Functionality**: Display and manage waste reports on an interactive map with status workflow
- **Target Users**: Municipal council operators and waste management teams

## Architecture
```
AIWasteMan/
├── frontend/          # React + TypeScript + Tailwind CSS
├── backend/           # Python FastAPI
└── shared/            # Shared types/interfaces
```

## UI/UX Specification

### Layout Structure
- **Header**: Logo, title, user info (minimal)
- **Main Content**: Split view - Map (left/center 60%), Reports list (right 40%)
- **Stats Bar**: Summary cards at top
- **Responsive**: Desktop-first (1200px+), tablet (768px), mobile (480px)

### Visual Design

**Color Palette**
- Primary: `#1E3A5F` (deep navy blue)
- Secondary: `#2D5A7B` (medium blue)
- Accent: `#4CAF50` (green for positive actions)
- Background: `#F8FAFC` (light gray)
- Surface: `#FFFFFF` (white cards)
- Text Primary: `#1F2937`
- Text Secondary: `#6B7280`

**Status Colors**
- Pending: `#F59E0B` (amber)
- Verified: `#3B82F6` (blue)
- Assigned: `#8B5CF6` (purple)
- Cleared: `#10B981` (green)

**Priority Colors**
- Low: `#6B7280` (gray)
- Medium: `#F59E0B` (amber)
- High: `#EF4444` (red)
- Critical: `#DC2626` (dark red)

**Typography**
- Font Family: Inter, system-ui, sans-serif
- Headings: 600 weight
- Body: 400 weight
- H1: 24px, H2: 20px, H3: 16px, Body: 14px

### Components

**Stats Cards**
- Total Reports, Pending, Assigned, Cleared
- Rounded corners (8px), subtle shadow
- Icon + number + label layout

**Map Component**
- Leaflet with OpenStreetMap tiles
- Custom markers for different statuses/priorities
- Popup on marker click

**Reports Table**
- Columns: ID, Location, Type, Priority, Status, Date
- Sortable headers
- Click row to show details
- Status badge styling

**Report Details Panel**
- Slide-in panel or modal
- Full report information
- Status change dropdown
- Team assignment dropdown

## Database Schema

### Tables

**users**
- id: UUID (primary key)
- name: VARCHAR(255)
- email: VARCHAR(255)
- role: ENUM ('admin', 'operator', 'team')
- created_at: TIMESTAMP

**waste_reports**
- id: UUID (primary key)
- ticket_id: VARCHAR(20) (unique, e.g., "WST-001")
- location: JSONB (PostGIS-ready: lat, lng, address)
- waste_type: ENUM ('plastic', 'organic', 'mixed', 'hazardous', 'medical')
- severity: ENUM ('low', 'medium', 'high', 'critical')
- priority: ENUM ('low', 'medium', 'high', 'critical')
- description: TEXT
- image_url: VARCHAR(500)
- status: ENUM ('pending', 'verified', 'assigned', 'cleared')
- assigned_team_id: UUID (foreign key)
- created_by: UUID (foreign key)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP

**teams**
- id: UUID (primary key)
- name: VARCHAR(255)
- area: VARCHAR(255)
- active: BOOLEAN
- created_at: TIMESTAMP

**status_history**
- id: UUID (primary key)
- report_id: UUID (foreign key)
- from_status: ENUM
- to_status: ENUM
- changed_by: UUID (foreign key)
- notes: TEXT
- created_at: TIMESTAMP

## API Endpoints

### GET /api/reports
- Query params: status, priority, page, limit
- Returns: Paginated list of reports

### GET /api/reports/{id}
- Returns: Single report with status history

### POST /api/reports
- Body: report data
- Returns: Created report

### PUT /api/reports/{id}/status
- Body: { status, notes }
- Returns: Updated report

### PUT /api/reports/{id}/assign
- Body: { team_id }
- Returns: Updated report

### GET /api/dashboard/stats
- Returns: { total, pending, assigned, cleared }

## Sample Data
- 10 sample waste reports with varied statuses, priorities, locations in Bamenda area
- 3 teams (North Zone, South Zone, Central Zone)

## Acceptance Criteria
1. Frontend starts without errors (npm run dev)
2. Backend starts without errors (uvicorn)
3. Dashboard shows 4 stat cards with counts
4. Map displays with sample report markers
5. Different marker colors for status/priority
6. Clicking marker shows report popup
7. Reports list shows sortable table
8. Click report shows detail panel
9. Status can be changed via dropdown
10. Team can be assigned via dropdown
11. Stats update after changes
12. Responsive on tablet/mobile
13. No console errors
14. API endpoints return mock data

---

# Waste Watch Business Layer (Step 3)

The system is now a two-sided waste marketplace on top of the reporting pipeline.

## Voice reports
- Citizens record audio in the browser (`/report`); the recording is sent to
  `POST /api/voice/transcribe` and transcribed with **ElevenLabs Scribe**
  (same API key used for WhatsApp voice notes; `VOICE_PREFER_ELEVENLABS=true`).
- The editable transcript flows through the normal AI pipeline
  (`POST /api/reports/process`), which classifies waste type, severity and priority.

## Public web app
- `/` — landing page: choose **Report Waste** or **View Our Services**.
- `/report` — voice-first report flow (record → edit transcript → photo + location → ticket).
- `/services` — the two business programs with signup forms (ID card upload):
  - **Waste Vendor** — buys sorted materials; declares the waste types they want.
  - **EcoCollector** — citizens looking for work; collect, sort, deliver, get paid.
- `/market` — live listings of sellable waste with per-kg prices and availability bars.
- `/collector` — jobs board, job lifecycle actions and earnings.
- `/admin` — council dashboard, now including **Marketplace** and **Partners** views.

## How a sellable report flows
1. Report created (web voice/photo or WhatsApp) → saved to the dashboard (status `pending`).
2. `plastic` / `organic` / `mixed` reports automatically open a **Listing**
   (estimated kg from AI size, default price per kg: 150/60/100 FCFA).
3. Matching **vendors** are alerted on WhatsApp.
4. A vendor may reserve **all or part** of the quantity — the rest stays
   available for community pickup (listing status `partially_claimed`).
5. An **EcoCollector** takes the pickup job → collects → sorts → delivers.
6. On delivery the platform settles the deal (default split):
   - **10% commission** to the citizen who reported (paid automatically),
   - **55% payout** to the collector,
   - **35% platform fee**.
7. Hazardous / medical reports never enter the marketplace — they are
   escalated to the **community head** (`COMMUNITY_HEAD_PHONE`) and response teams.

## New API endpoints
- `POST /api/voice/transcribe` — ElevenLabs transcription of browser audio.
- `GET /api/market/listings`, `GET /api/market/listings/{id}`
- `POST /api/market/listings/{id}/claims` — vendor reserves quantity.
- `GET /api/market/claims`, `POST /api/market/claims/{id}/collector`,
  `PUT /api/market/claims/{id}/status` — claim lifecycle.
- `GET /api/market/stats` — marketplace KPIs.
- `POST /api/partners/vendors`, `GET /api/partners/vendors[/{id}][/claims]`
- `POST /api/partners/collectors`, `GET /api/partners/collectors[/{id}][/jobs]`

## New tables
`vendors`, `collectors`, `listings`, `claims`, `payouts`.