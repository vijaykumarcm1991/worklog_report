# Worklog Dashboard

A modern web app that aggregates daily **Jira worklog hours** from **both Jira Cloud and Jira on-prem (Server/DC)** instances into a single calendar view.

- Configure any number of Jira instances from the UI (Cloud + on-prem)
- Pick and save users per instance via a live search dropdown
- Calendar shows per-day hours color-coded as **met / under / over** the daily target (default **8h**, configurable)
- Credentials encrypted at rest (Fernet key via env)
- Background scheduled sync + on-demand "Sync now"
- Deployed with **Docker Compose** (FastAPI backend + React/Tailwind frontend served by nginx)

![stack](https://img.shields.io/badge/stack-FastAPI%2BReact%2B%20Docker%20Compose-blueviolet)

---

## Quick start (Docker Compose)

```bash
# 1. Create your environment file from the template
cp .env.example .env

# 2. Generate a Fernet encryption key and paste it into WORKLOG_ENC_KEY in .env
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 3. Build and start
docker compose up -d --build
```

Then open **http://localhost:8080** (change `APP_PORT` in `.env` to use a different host port).

### Stopping

```bash
docker compose down        # stop containers
docker compose down -v     # stop AND delete the DB volume (removes saved data)
```

---

## Usage

1. **Instances** — add each Jira connection. Choose **Cloud** or **On-prem**, enter the site/base URL, email (cloud) or username (on-prem), and an API token/password. Use **Test** to validate credentials before saving. Credentials are stored encrypted.
2. **Users** — for each instance, search users from a live dropdown and **Save** the ones you want reported. Only saved users are pulled into the calendar.
3. **Calendar** — the default view. Browse months; each day is shaded by whether logged hours reached the daily target. Use **Sync now** to pull fresh worklogs on demand (they also sync on a schedule in the background).
4. **Settings** — change the **daily target hours** (default `8`).

### Jira API tokens

- **Jira Cloud**: create an API token at https://id.atlassian.com/manage-profile/security/api-tokens; use your login **email** as the username.
- **Jira On-prem (Server/DC)**: use the user's **username** and either the account password or a Personal Access Token (if PAT auth is enabled on your Server/DC).

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `WORKLOG_ENC_KEY` | *(required)* | Fernet key encrypting stored credentials. Generate with the command above. |
| `SYNC_INTERVAL_MINUTES` | `60` | How often the background sync runs. `0` disables the scheduler. |
| `CORS_ORIGINS` | `http://localhost:8080` | Allowed browser origins. In Docker the UI is same-origin (nginx proxies `/api`), so the default is fine. |
| `APP_PORT` | `8080` | Host port the web UI is published on. |

The SQLite database lives in the named volume `worklog-data` (`/app/data/worklog.db`).

---

## Development (without Docker)

**Backend** (FastAPI):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export WORKLOG_ENC_KEY="$(python3 -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
uvicorn app.main:app --reload --port 8000
```

**Frontend** (Vite + React + Tailwind):

```bash
cd frontend
npm install
npm run dev    # Vite proxies /api -> http://localhost:8000
```

**Tests** (backend, mocked Jira HTTP + API + crypto round-trips):

```bash
cd backend && python -m pytest
```

---

## Architecture

```
frontend/ (nginx serves static build, proxies /api -> backend:8000)
├── Vite + React 18 + Tailwind, dark/light dashboard (sidebar nav)
└── Views: Calendar, Instances, Users, Settings
backend/ (FastAPI + SQLAlchemy + SQLite)
├── Jira client abstraction
│   ├── JiraCloudClient   (REST api/3, users identified by accountId)
│   └── JiraOnPremClient  (REST api/2, users identified by username)
├── credentials encrypted at rest with Fernet (WORKLOG_ENC_KEY)
├── APScheduler background sync + manual refresh endpoint
└── API: /instances, /instances/{id}/users, /config, /sync, /calendar
```

The one abstraction (`app/jira.py`, `make_client` factory) keeps sync and the calendar agnostic to instance type: **Cloud** uses REST API v3 and `accountId`; **On-prem** uses API v2 and `username`. Worklog authors are matched accordingly.

## Notes & caveats

- Real connectivity depends on reaching your Jira instances from wherever this app runs (in Docker, the backend must reach your on-prem Jira host on its network).
- On-prem Jira Server instances may require the API to be reachable over HTTP(s) from the container.
- **Everything is IST (Asia/Kolkata).** Both Jira instances are IST, so worklog start times are stored exactly as Jira reports them, with no timezone conversion. Days, the sync window, the scheduler and the calendar's "today" all use IST. The Jira API account on each instance should have its profile timezone set to IST.
- The calendar aggregates **worklog time by date**, comparing it against your daily target.
- A sync replaces each user's worklogs inside the fetch window, so worklogs deleted in Jira disappear from the calendar on the next sync.
