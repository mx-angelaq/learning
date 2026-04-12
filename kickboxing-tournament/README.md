# Kickboxing Tournament Tracker

A single-elimination kickboxing tournament management system with **local** (offline-capable) and **hosted** (shareable) modes.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐
│   React SPA     │────▶│  FastAPI Backend  │
│  (Vite, port    │     │  (port 8000)      │
│   3000)         │     │                   │
│                 │     │  ┌──────────────┐ │
│  - Bracket view │     │  │ SQLite (local)│ │
│  - Admin panel  │     │  │ or PostgreSQL │ │
│  - Public view  │     │  │ (hosted)      │ │
│  - Ring queues  │     │  └──────────────┘ │
└─────────────────┘     │                   │
                        │  SSE live updates │
                        │  JWT auth         │
                        └──────────────────┘
```

**Why this stack:**
- **FastAPI** - async, fast, auto-docs, minimal boilerplate
- **SQLite** - zero-config local DB, works offline, WAL mode for concurrent reads
- **PostgreSQL** - production hosted DB (via Docker Compose)
- **React + Vite** - fast dev, small bundle, responsive UI
- **SSE** - simpler than WebSockets, works behind most proxies, auto-reconnect

## Quick Start (Local Mode)

### Option 1: Docker Compose (recommended)

```bash
cd kickboxing-tournament
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### Option 2: Manual

```bash
# Backend
cd backend
pip install -r requirements.txt
python seed_data.py          # Load demo data
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Default Credentials
- **Admin**: password `admin123`
- **Staff**: password `staff123`
- **Public**: no login needed (read-only)

## Hosted Mode (PostgreSQL)

```bash
cd kickboxing-tournament
docker compose -f docker-compose.hosted.yml up --build
```

Set real passwords via environment variables:
```bash
ADMIN_PASSWORD=your-secure-admin-pw \
STAFF_PASSWORD=your-secure-staff-pw \
SECRET_KEY=your-random-secret-key \
docker compose -f docker-compose.hosted.yml up --build
```

## Deployment (Step-by-Step)

### Deploy to a VPS (e.g., DigitalOcean, Render, Fly.io)

1. **Clone the repo** on your server
2. **Set environment variables** in a `.env` file:
   ```
   APP_MODE=hosted
   DATABASE_URL=postgresql://user:pass@host:5432/kickboxing
   ADMIN_PASSWORD=<strong-password>
   STAFF_PASSWORD=<strong-password>
   SECRET_KEY=<random-64-char-string>
   CORS_ORIGINS=https://yourdomain.com
   ```
3. **Run** `docker compose -f docker-compose.hosted.yml up -d`
4. **Share** the public view URL: `https://yourdomain.com/public/1`

### Deploy to Render.com (free tier)
1. Create a new Web Service pointing to the `backend/` directory
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `python seed_data.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables (see above)
5. For frontend: deploy as a Static Site from `frontend/` with `npm run build`

## Self-Registration

Competitors can register themselves via a public web form, removing the need for admin manual data entry.

### How it works

1. **Admin enables registration**: Set `registration_open: true` on the tournament (via API or creation form)
2. **Share the link**: `https://yourdomain.com/register/{tournament_id}`
3. **Competitor fills out the form**: name, email, division, weight, gym, waiver agreement
4. **Registration is saved as "pending"**
5. **Admin reviews** in the "Registrations" tab on the tournament management page
6. **Approve** creates a real `Competitor` record in the selected division (same code path as manual admin creation)
7. **Reject** marks the registration as rejected (competitor can re-register)

### Registration API endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/tournaments/{id}/registrations` | Public | Submit registration |
| `GET /api/tournaments/{id}/registrations/check?email=...` | Public | Check status by email |
| `GET /api/tournaments/{id}/registrations` | Admin | List all (filterable by `?status=pending`) |
| `POST /api/tournaments/{id}/registrations/{rid}/review` | Admin | Approve or reject |

### Duplicate prevention

Duplicate registrations are prevented by email per tournament. A rejected registration allows the email to re-register.

### Discord webhook (optional)

Set `DISCORD_WEBHOOK_URL` environment variable to receive notifications in a Discord channel when someone registers.

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Environment variables for registration

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_WEBHOOK_URL` | No | Discord webhook for registration notifications |

### Manual test (curl)

```bash
# Submit a registration (no auth needed)
curl -X POST http://localhost:8000/api/tournaments/1/registrations \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Test Fighter","email":"test@example.com","division_id":1,"declared_weight":68.5,"waiver_agreed":true}'

# Check status
curl http://localhost:8000/api/tournaments/1/registrations/check?email=test@example.com

# Admin: list pending
curl http://localhost:8000/api/tournaments/1/registrations?status=pending \
  -H "Authorization: Bearer <admin_token>"

# Admin: approve
curl -X POST http://localhost:8000/api/tournaments/1/registrations/1/review \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"action":"approve","admin_notes":"Verified weight"}'
```

## Sync Strategy

**Local is source of truth.** The local instance running at the venue holds the authoritative data.

When internet is available:
1. Admin clicks "Sync to Hosted" (or use the API)
2. Local exports a full tournament snapshot (JSON)
3. Snapshot is POSTed to the hosted instance's `/api/sync/import` endpoint
4. Hosted instance replaces its data for that tournament

This avoids complex conflict resolution. The venue laptop always wins.

```
┌──────────┐    Full JSON     ┌──────────┐
│  Local   │───snapshot──────▶│  Hosted  │
│ (SQLite) │  when online     │ (Postgres)│
└──────────┘                  └──────────┘
```

**API endpoints:**
- `POST /api/sync/export/{tournament_id}` - Get snapshot JSON
- `POST /api/sync/push/{tournament_id}` - Push to hosted
- `POST /api/sync/import` - Receive snapshot (hosted side)

## Features

### Roles & Permissions
| Feature | Admin | Staff | Public |
|---------|-------|-------|--------|
| Create/edit tournament | ✓ | ✗ | ✗ |
| Manage divisions/competitors | ✓ | ✗ | ✗ |
| Generate brackets | ✓ | ✗ | ✗ |
| Record results | ✓ | ✓ | ✗ |
| Set match status | ✓ | ✓ | ✗ |
| Handle chaos (withdrawal/sub) | ✓ | ✗ | ✗ |
| View brackets & results | ✓ | ✓ | ✓ |
| View audit log | ✓ | ✓ | ✓ |
| Self-register as competitor | - | - | ✓ |
| Review registrations | ✓ | ✗ | ✗ |

### Tournament Setup
- Name, date, venue, rings, timing
- Configurable weight presets (editable, not hardcoded)
- Rules: weigh-in tolerance, substitution cutoff, no-show policy

### Bracket Engine
- Single elimination, any competitor count
- Byes for non-power-of-two
- Seeding: random, manual (by seed field), separate-gyms (best-effort)
- Safe regeneration with confirmation

### Day-of Chaos Handling
- **Dropout/Withdrawal** → opponent advances
- **No-show** → configurable policy (walkover/DQ/reschedule)
- **Substitution** → new competitor replaces old with audit
- **Result correction** → rollback + re-advance with safeguards
- **Division change** → move competitor with warnings

### Scheduling
- Ring-based queues: Up Next, On Deck, In Progress
- Auto-estimated times based on settings
- Drag/drop reorder via API

### Live Updates
- SSE (Server-Sent Events) for real-time bracket updates
- Auto-refresh every 15 seconds on public view
- "Last updated" timestamp

## Running Tests

```bash
cd backend
pip install -r requirements.txt
python -m pytest app/tests/ -v
```

### Test Coverage

| Category | Tests |
|----------|-------|
| Bracket generation | power-of-2, non-power-of-2, 2/3/5/7 competitors, byes |
| Seeding | random, manual, separate-gyms |
| Advancement | winner advances, invalid winner rejected |
| Withdrawal | opponent advances, status updated |
| No-show | walkover, DQ, reschedule policies |
| Substitution | round 1 ok, past cutoff blocked |
| Rollback | clears result, blocked if next match played |
| Correction | rollback + re-advance |
| Scheduling | time estimation |
| Audit | bracket gen logged, withdrawal logged |
| Registration submit | happy path, minimal fields, all fields |
| Registration validation | missing name, invalid email, waiver not agreed, invalid division |
| Registration closed | blocked when registration_open=false |
| Duplicate prevention | same email blocked, different tournament ok, rejected can resubmit |
| Admin approval | creates competitor, reject no competitor, double-approve blocked |
| Approval auth | admin required, staff/public denied |
| Approval audit | logged in audit trail |
| Status check | by email, not found, email normalization |
| Admin list | filter by status, requires admin |
| API auth | admin login, staff login, wrong password, public denied |
| API CRUD | tournaments, divisions, competitors, brackets |
| Permissions | admin-only actions, staff can record results |

## Seed Data

The seed script creates:
- **Spring Kickboxing Championship 2026**
- 3 divisions (Men's LW, Men's MW, Women's LW)
- 16 competitors across divisions
- Pre-generated brackets with gym separation

## Manual QA Checklist (Tournament Day)

- [ ] Start app, verify health endpoint returns ok
- [ ] Login as admin with correct password
- [ ] Create a tournament with all settings
- [ ] Create at least 2 divisions
- [ ] Add 4+ competitors per division
- [ ] Generate bracket (random), verify visual display
- [ ] Regenerate bracket (confirm dialog appears)
- [ ] Set matches to queued/on_deck/in_progress
- [ ] Record a result, verify winner advances
- [ ] Process a withdrawal, verify opponent advances
- [ ] Process a no-show with walkover policy
- [ ] Substitute a competitor, verify audit log
- [ ] Rollback a result, verify bracket state reset
- [ ] Correct a result with wrong winner
- [ ] Check schedule tab shows ring queues
- [ ] Open public view in separate browser/incognito
- [ ] Verify public view shows live bracket + results
- [ ] Verify public view auto-refreshes
- [ ] Verify public view cannot modify anything
- [ ] Login as staff, verify can record results but not create tournaments
- [ ] Check audit log shows all actions

## Edge Cases Handled

| Scenario | Handling | Location |
|----------|----------|----------|
| 1 competitor | Error: need at least 2 | `bracket_engine.py` |
| 3, 5, 7 competitors | Byes auto-assigned | `bracket_engine.py` |
| Same-gym opponents | Best-effort separation | `separate_gyms_seed()` |
| Duplicate competitor | Warning + force override | `competitors.py` |
| Bracket regeneration | Confirmation required | `bracket_engine.py` |
| Withdrawal mid-tournament | Opponent auto-advances | `handle_withdrawal()` |
| No-show (3 policies) | Configurable per tournament | `handle_no_show()` |
| Substitution past cutoff | Rejected with error | `handle_substitution()` |
| Result rollback | Blocked if next match played | `rollback_result()` |
| Invalid winner ID | Rejected with clear error | `advance_winner()` |
| Delete competitor with bracket | Rejected (use withdrawal) | `competitors.py` |
| Delete division with matches | Rejected | `divisions.py` |

## Known Limitations & Next Steps

### Limitations
- **Sync is one-way** (local → hosted). No merge/conflict resolution.
- **No real-time push** from backend on data changes (SSE is connected but events must be manually triggered by extending API handlers).
- **No drag-and-drop** in frontend for seeding/reorder (API supports it, UI uses buttons).
- **Single elimination only** (no double elimination or round robin).
- **No print-friendly** bracket export (would need CSS print styles or PDF generation).
- **Auth is password-based** (no OAuth/magic link in this version).

### Recommended Next Steps
1. Add WebSocket or extend SSE to push on every DB write
2. Add drag-and-drop UI for seeding and ring queue reorder
3. Add print/PDF bracket export
4. Add double elimination bracket engine
5. Add competitor photo/ID upload
6. Add real-time sync with conflict resolution for multi-device editing
7. Add email/SMS notifications for upcoming matches

## Project Structure

```
kickboxing-tournament/
├── docker-compose.yml          # Local mode (SQLite)
├── docker-compose.hosted.yml   # Hosted mode (PostgreSQL)
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── seed_data.py
│   └── app/
│       ├── main.py             # FastAPI app entry
│       ├── config.py           # Settings (env-based)
│       ├── database.py         # SQLAlchemy setup
│       ├── auth.py             # JWT auth
│       ├── models/
│       │   ├── db_models.py    # SQLAlchemy models
│       │   └── schemas.py      # Pydantic schemas
│       ├── services/
│       │   ├── bracket_engine.py  # Core bracket logic
│       │   ├── scheduling.py      # Ring queues & timing
│       │   ├── events.py          # SSE manager
│       │   └── sync.py            # Local→hosted sync
│       ├── routers/
│       │   ├── auth.py
│       │   ├── tournaments.py
│       │   ├── divisions.py
│       │   ├── competitors.py
│       │   ├── brackets.py
│       │   ├── scheduling.py
│       │   ├── audit.py
│       │   ├── sync_routes.py
│       │   ├── events.py
│       │   └── registrations.py     # Self-registration + admin review
│       └── tests/
│           ├── test_bracket_engine.py
│           ├── test_api.py
│           └── test_registration.py  # 22 registration tests
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── utils/api.js
        ├── hooks/
        │   ├── useAuth.js
        │   └── useLiveUpdates.js
        ├── pages/
        │   ├── TournamentList.jsx
        │   ├── TournamentView.jsx
        │   ├── DivisionView.jsx
        │   └── PublicView.jsx
        ├── components/
        │   ├── LoginModal.jsx
        │   ├── BracketView.jsx
        │   └── MatchActions.jsx
        └── styles/
            └── global.css
```
