# RingCentralAutoSet-API — Desktop MAX via Official Agent API

This is **separate** from `run.py` (Playwright + Chrome). Use this when you work in the **RC desktop MAX agent app**.

## What it does

| Time | API action | Desktop MAX |
|------|------------|-------------|
| Work start | Login session + Station + **Available** | Ready for calls |
| Lunch | **Unavailable (Lunch)** | Shows lunch |
| After lunch | **Available** | Back online |
| Work end | **End session (logout)** | Logged out |

No browser automation. Uses **NICE CXone Agent API** (official).

---

## One-time setup

### 1. Get API credentials (ask IT if needed)

In **CXone Admin** (or RC admin):

1. **Access Keys** — create for your agent user  
   - Save `Access Key ID` + `Secret` (shown once)

2. **API Application** — register at [developer.niceincontact.com](https://developer.niceincontact.com)  
   - Get `Client ID` + `Client Secret`  
   - Enable **Agent API** permissions

3. Note your **API base URL** (cluster), e.g.  
   `https://api-na1.niceincontact.com/inContactAPI/services/v27.0`

4. Confirm **Lunch** unavailable code name in admin (default: `Lunch`)

### 2. Configure `.env`

Copy from `.env.rc.example` into your main `.env`:

```bash
RC_ACCESS_KEY_ID=your-key-id
RC_ACCESS_KEY_SECRET=your-secret
RC_CLIENT_ID=your-client-id
RC_CLIENT_SECRET=your-client-secret
RC_API_BASE=https://api-na1.niceincontact.com/inContactAPI/services/v27.0
RC_STATION_ID=14065216
```

Work times use the same `WORK_START`, `WORK_END`, `LUNCH_*` as the main app.

### 3. Install dependency

```bash
cd ~/Projects/Ring_Central_Automation
source .venv/bin/activate
pip install requests
```

### 4. Test

```bash
.venv/bin/python rc_run.py test-auth
.venv/bin/python rc_run.py morning    # login + Available
.venv/bin/python rc_run.py status
.venv/bin/python rc_run.py logout
```

---

## Daily use

```bash
# Manual
.venv/bin/python rc_run.py morning
.venv/bin/python rc_run.py logout

# Auto on schedule (same times as .env)
.venv/bin/python rc_run.py schedule

# Background on Mac login
.venv/bin/python rc_run.py install-service
```

---

## Desktop app + API

- Open **desktop MAX** for your shift (calls, UI).
- The script changes **platform agent state** via API.
- If already logged in on desktop, it tries **join session** first.
- **Do not** also run `run.py` (Playwright) at the same time — pick one method.

---

## Commands

| Command | Purpose |
|---------|---------|
| `rc_run.py test-auth` | Verify credentials |
| `rc_run.py show` | Schedule + config |
| `rc_run.py morning` / `login` | Work start |
| `rc_run.py lunch` | Lunch |
| `rc_run.py lunch-end` | Back from lunch |
| `rc_run.py logout` | Work end |
| `rc_run.py schedule` | Run scheduler in terminal |
| `rc_run.py install-service` | Auto-start on login |
| `rc_run.py uninstall-service` | Stop background |
| `rc_run.py service-status` | Check service |

---

## Logs

```
logs/rc-api-scheduler.log
logs/rc-api-scheduler.err.log
```

Session id saved in: `rc_agent/data/session.json` (gitignored)

---

## Slack (later)

Slack status → map to `rc_run.py` actions can be added in `rc_agent/slack_sync.py` when you have Slack app approval.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| 401 on test-auth | Wrong access key or client id/secret |
| 404 on API | Wrong `RC_API_BASE` cluster URL |
| Lunch fails | Set `RC_LUNCH_REASON` to match admin code name |
| Session conflict | Logout desktop MAX once, then `rc_run.py logout` |

Get IT approval before production use.
