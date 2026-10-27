# Waste Watch

**A WhatsApp-first waste reporting and recovery platform for Bamenda.** Waste Watch turns citizen messages into actionable municipal reports, routes urgent incidents, and connects reusable waste with vendors and community collectors.

> **Project status:** the dashboard and API run locally; WhatsApp webhook handling is implemented. Live WhatsApp delivery requires valid Meta credentials and a public HTTPS callback URL. The Zetaris dashboard reads analytics through a registered Zetaris datasource and a reachable MySQL database.

## Contents

- [What the project does](#what-the-project-does)
- [How it is built](#how-it-is-built)
- [Requirements](#requirements)
- [Run locally](#run-locally)
- [Staff dashboard](#staff-dashboard)
- [WhatsApp webhooks with ngrok](#whatsapp-webhooks-with-ngrok)
- [Zetaris analytics](#zetaris-analytics)
- [Configuration reference](#configuration-reference)
- [API overview](#api-overview)
- [Troubleshooting](#troubleshooting)
- [Deployment notes](#deployment-notes)

## What the project does

- **Citizen intake:** accepts text, photos, voice notes and location pins through the WhatsApp Cloud API. The web API also supports report processing and voice transcription.
- **AI-assisted triage:** classifies waste, estimates severity and priority, and can request a clearer photo when evidence is uncertain.
- **Municipal operations:** staff can review reports, inspect them on a map, change status, assign teams and review activity.
- **Waste recovery marketplace:** eligible plastic, organic and mixed waste can be listed for vendor claims and collector jobs. Hazardous and medical reports are escalated instead.
- **Partner management:** review vendors and collectors and their marketplace activity.
- **Analytics:** the Insights view requests read-only summaries from Zetaris.

## How it is built

| Part | Technology | Local address |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Leaflet | http://localhost:5173 |
| Backend | Python, FastAPI, SQLAlchemy | http://localhost:5000 |
| Database | MySQL/MariaDB for Zetaris-backed analytics; SQLite is the code fallback | Configured by `DATABASE_URL` |
| Analytics | Zetaris SQL gateway | Configured by `ZETARIS_BASE_URL` |
| Public webhook tunnel | ngrok | Forwarding to backend port 5000 |

During local development, Vite proxies `/api` and `/media` to the backend. The browser therefore calls same-origin relative URLs; `frontend/.env` leaves `VITE_API_URL` empty for this setup.

## Requirements

- Python 3.10 or later (Python 3.11 is the deployment target in `render.yaml`).
- Node.js 20 or later and npm.
- MySQL/MariaDB when using the configured Zetaris catalog. The backend's fallback is SQLite, but the Zetaris datasource will not be able to query that SQLite file.
- A running Zetaris gateway and a datasource/catalog mapped to the app's MySQL schema for live insights.
- An ngrok account and an authenticated ngrok CLI for a public webhook URL.
- Meta WhatsApp Cloud API credentials for real inbound messages and replies. Without them, use `MESSAGE_CHANNEL=log` for local development.

## Run locally

Open two terminals at the repository root.

### 1. Install backend dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate` instead.

Create `backend/.env` from `backend/.env.example` if needed, then set the database and service credentials you have. Keep `.env` files private; they are ignored by Git.

### 2. Start the API on port 5000

From the `backend` directory with the virtual environment active:

```powershell
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

Or run `python main.py` (also binds port 5000). Check [http://localhost:5000/health](http://localhost:5000/health) and [http://localhost:5000/docs](http://localhost:5000/docs).

The first startup creates the database tables and admin/council users. Incoming reports are added through the WhatsApp intake flow.

For a local XAMPP database, start MariaDB from the XAMPP Control Panel before starting the API. A standard Windows XAMPP installation can also be started from PowerShell with:

```powershell
C:\xampp\mysql\bin\mysqld.exe --defaults-file=C:\xampp\mysql\bin\my.ini --console
```

Then run the API normally using the configured MySQL `DATABASE_URL`; Zetaris queries this same schema.

### 3. Start the frontend

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). API calls under `/api` and uploaded media under `/media` are proxied to `127.0.0.1:5000` by Vite. If you change `VITE_API_URL`, restart Vite because Vite reads it at startup/build time.

### 4. Build the frontend

```powershell
cd frontend
npm run build
```

The production bundle is written to `frontend/dist/`. `npm run preview` serves that built bundle locally; configure a production API URL at build time if it is hosted separately from the API.

## Staff dashboard

The app creates these initial accounts when they do not already exist:

| Role | Email | Initial password |
| --- | --- | --- |
| Admin | `admin@bamenda.cm` | `admin123` |
| Council | `council@bamenda.cm` | `council123` |

Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `COUNCIL_EMAIL` and `COUNCIL_PASSWORD` before the first run to choose your own. Existing account passwords are not overwritten on later starts. Change development passwords before exposing a deployment to other users.

The WhatsApp webhook, health check, root endpoint and media are public. Dashboard data and management endpoints require a staff bearer token obtained from `/api/auth/login`.

## WhatsApp webhooks with ngrok

The WhatsApp callback route is `GET/POST /api/whatsapp/webhook`. Keep the API running on port 5000 and, from a third terminal, start a tunnel:

```powershell
ngrok http 5000
```

Copy the HTTPS forwarding URL printed by ngrok, for example `https://example.ngrok-free.app`. If the CLI output is not visible, open the local ngrok inspector (by default [http://127.0.0.1:4040](http://127.0.0.1:4040)) to find the active URL. In the Meta developer console, configure:

- **Callback URL:** `https://example.ngrok-free.app/api/whatsapp/webhook`
- **Verify token:** exactly the value of `WHATSAPP_VERIFY_TOKEN` in `backend/.env`
- Subscribe the WhatsApp webhook fields your flow needs (at minimum `messages`).

Use the HTTPS URL while the tunnel is running. Free ngrok URLs can change after a restart; update Meta's callback URL when that happens. The tunnel forwards requests only to the backend; the local dashboard stays at `http://localhost:5173`.

### Webhook configuration

Set these backend variables for real Cloud API traffic:

```dotenv
MESSAGE_CHANNEL=whatsapp
WHATSAPP_ACCESS_TOKEN=your_meta_access_token
WHATSAPP_PHONE_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=choose_a_private_callback_verification_value
WHATSAPP_APP_SECRET=your_meta_app_secret
WHATSAPP_API_VERSION=v25.0
```

`WHATSAPP_APP_SECRET` enables POST signature validation. Keep it set when handling real Meta callbacks. With `MESSAGE_CHANNEL=log`, outgoing messages are logged for local simulation; a valid token and phone ID are still needed to receive media from the real Cloud API.

Meta verification can be checked locally (substitute your verify token):

```text
http://localhost:5000/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_VERIFY_TOKEN&hub.challenge=12345
```

The response should be the plain text `12345`. To test Meta itself, use the public HTTPS ngrok URL in its callback settings. The webhook acknowledges quickly and processes message contents in a background worker; inspect the backend terminal for processing errors.

## Zetaris analytics

The dashboard's **Insights** view calls `GET /api/insights`. The API logs into Zetaris, runs read-only Spark SQL statements through its SQL gateway and returns report totals, breakdowns and top areas. Results are cached briefly; the Refresh button bypasses the cache.

Configure the following in `backend/.env`:

```dotenv
ZETARIS_BASE_URL=http://127.0.0.1:3000
ZETARIS_EMAIL=your_zetaris_username
ZETARIS_PASSWORD=your_zetaris_password
ZETARIS_DATABASE=WASTE_WATCH
ZETARIS_TIMEOUT_SECONDS=30
```

Also point the app's `DATABASE_URL` at the MySQL/MariaDB schema registered with Zetaris, for example:

```dotenv
DATABASE_URL=mysql+pymysql://wastewatch_app:change_me@127.0.0.1:3306/wastewatch?charset=utf8mb4
```

Create the database and account in MySQL before starting the app, then register a Zetaris datasource/catalog whose name matches `ZETARIS_DATABASE` and whose JDBC connection can reach that database. The app's SQL expects the `waste_reports` and `locations` tables in that catalog. The user configured in Zetaris should have permission to run read-only analytics queries.

Check the gateway itself at its configured URL and call `/api/insights` from the app (the Insights dashboard requires staff login). A `503` indicates missing Zetaris settings; a `502` means the gateway login or query failed. Check the backend log and confirm the catalog, datasource connectivity, table names, and SQL dialect. If Zetaris is intentionally unavailable, core reporting still works and Insights will show an error/not-connected state.

## Configuration reference

| Variable | Purpose | Typical local value |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy database connection | MySQL URL for live Zetaris; unset uses SQLite |
| `MEDIA_DIR` | Uploaded image storage | Defaults to `backend/media` |
| `MESSAGE_CHANNEL` | `log` simulator or `whatsapp` delivery | `log` |
| `WHATSAPP_ACCESS_TOKEN` | Meta Cloud API bearer token | Empty for offline development |
| `WHATSAPP_PHONE_ID` | Meta phone-number ID | Empty for offline development |
| `WHATSAPP_VERIFY_TOKEN` | Callback verification secret | Choose a private value |
| `WHATSAPP_APP_SECRET` | Validate Meta callback signatures | Optional locally; set for real traffic |
| `OPENROUTER_API_KEY` | AI provider key | Optional; provider falls back when unavailable |
| `NVIDIA_API_KEY` | AI provider fallback key | Optional |
| `ELEVENLABS_API_KEY` | Voice transcription and speech features | Optional |
| `GROQ_API_KEY` | Groq speech recognition if selected | Optional |
| `COMMUNITY_HEAD_PHONE` | Escalation recipient in E.164 format | Optional |
| `ZETARIS_BASE_URL` | Zetaris gateway origin | `http://127.0.0.1:3000` |
| `ZETARIS_EMAIL`, `ZETARIS_PASSWORD` | Zetaris login | Set locally; never commit |
| `ZETARIS_DATABASE` | Zetaris registered catalog name | `WASTE_WATCH` |
| `VITE_API_URL` | Absolute API origin for separate frontend hosting | Empty for local Vite proxy |
| `FRONTEND_URL` | Extra allowed CORS frontend origin | Set for hosted frontend |

See `backend/.env.example` for the full list of tuning options.

## API overview

Interactive OpenAPI docs: [http://localhost:5000/docs](http://localhost:5000/docs).

| Route | Purpose | Access |
| --- | --- | --- |
| `GET /health` | Process health check | Public |
| `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` | Staff sessions | Login public; `me` requires token |
| `/api/reports` | Report list, detail and workflow updates | Staff |
| `/api/dashboard/stats`, `/api/dashboard/teams` | Dashboard KPIs and response teams | Staff |
| `/api/whatsapp/webhook` | Meta verification and inbound events | Public; signature checked when app secret is set |
| `GET /api/whatsapp/config` | Non-secret channel status | Public |
| `/api/voice` | Browser voice transcription | Staff |
| `/api/market` | Listings, claims, jobs and marketplace stats | Staff dashboard routes |
| `/api/partners` | Vendor and collector management | Staff |
| `GET /api/insights` | Zetaris-backed analytics (`?refresh=true` bypasses cache) | Staff dashboard route |
| `/media/*` | Stored inbound media | Public |

## Troubleshooting

### The dashboard cannot reach the API

Confirm the backend answers at `http://127.0.0.1:5000/health`, the frontend is running on 5173, and `frontend/vite.config.ts` proxies `/api` and `/media` to port 5000. Restart Vite after changing `.env`.

### Backend exits during startup

Check the terminal traceback. A MySQL `DATABASE_URL` requires a reachable MySQL/MariaDB service and existing schema; start that service or use SQLite for core-only development. With SQLite, Zetaris analytics cannot read the app's database through a MySQL datasource.

### Insights shows an error

Verify the Zetaris gateway URL is reachable from the backend, the login is valid, the configured catalog exists, and the catalog can query the MySQL tables used by the app. Inspect `/api/insights`' response and backend log for the upstream error.

### Meta cannot verify the callback

Check the HTTPS ngrok forwarding URL, exact `/api/whatsapp/webhook` path, matching verify token, and that port 5000 is listening. Verification is a GET request; message delivery uses POST. Recheck Meta's subscribed webhook fields.

### Reports do not get AI classification or replies

Inspect `MESSAGE_CHANNEL`, the provider selection and API key settings, and backend logs. Empty AI credentials may trigger a fallback or a reduced local response. `MESSAGE_CHANNEL=log` does not send messages to a citizen's phone.

## Deployment notes

`render.yaml` describes the hosted backend and its environment variables. A hosted frontend must set `VITE_API_URL` to the public backend origin at build time and the backend must allow the frontend origin through `FRONTEND_URL`. Configure production secrets in the hosting provider, not in committed files. For a production database, use durable MySQL/MariaDB if Zetaris analytics is required; the Render template currently selects SQLite for the hosted core API.
