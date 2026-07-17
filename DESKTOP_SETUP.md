# RingCentralAutoSet-Desktop — RingCentral.app automation

Automates the **desktop RingCentral app** using macOS **Accessibility** (clicks real UI buttons). No API keys and no browser.

**Separate** from `run.py` (Chrome) and `rc_run.py` (Agent API). Use only one scheduler at a time.

---

## What it does

| Time | Desktop actions |
|------|-----------------|
| Work start | Agent tab → **Start working** → wait → **Available** |
| Lunch | Status → **Unavailable** → **Lunch** |
| After lunch | **Available** |
| Work end | **Stop working** |

Assumes **RingCentral.app is already open and logged in**.

---

## One-time setup

### 1. macOS Accessibility permission

1. Open **System Settings → Privacy & Security → Accessibility**
2. Enable **Terminal** (or **iTerm**) — whatever you run commands from
3. If using the background service, also enable **Python** (`/usr/bin/python3` or `.venv/bin/python`)

### 2. Open RingCentral before work

Leave **RingCentral.app** running. You stay logged in; the script only changes agent state.

### 3. Test access

```bash
cd ~/Projects/Ring_Central_Automation
source .venv/bin/activate   # if not already active

# RingCentral.app must be open
.venv/bin/python desktop_run.py test-access
```

### 4. Tune UI labels (if clicks fail)

With RingCentral on the **Agent** tab:

```bash
.venv/bin/python desktop_run.py inspect
```

This saves `logs/desktop-ui-inspect.txt`. Edit `rc_desktop/labels.yaml` so names match your app (e.g. `Start working`, `Agent`, `Lunch`).

### 5. Trial a full morning flow

```bash
.venv/bin/python desktop_run.py morning
```

### 6. Trial logout

```bash
.venv/bin/python desktop_run.py logout
```

---

## Daily automation

Work times come from the same `.env` as the main app (`WORK_START`, `WORK_END`, `LUNCH_*`, `TIMEZONE`).

### Option A — Background (recommended)

```bash
.venv/bin/python desktop_run.py install-service
```

Runs on Mac login. Logs:

- `logs/desktop-scheduler.log`
- `logs/desktop-scheduler.err.log`

Check status:

```bash
.venv/bin/python desktop_run.py service-status
```

Stop:

```bash
.venv/bin/python desktop_run.py uninstall-service
```

### Option B — Terminal scheduler (testing)

```bash
.venv/bin/python desktop_run.py schedule
```

---

## Commands

| Command | Purpose |
|---------|---------|
| `desktop_run.py test-access` | Accessibility + app running |
| `desktop_run.py show` | Schedule + config |
| `desktop_run.py inspect` | List UI names for labels.yaml |
| `desktop_run.py morning` / `login` | Work start |
| `desktop_run.py lunch` | Lunch |
| `desktop_run.py lunch-end` | Back from lunch |
| `desktop_run.py logout` | Stop working |
| `desktop_run.py schedule` | Scheduler in terminal |
| `desktop_run.py install-service` | Auto on login |
| `desktop_run.py uninstall-service` | Remove background job |

---

## Optional `.env` settings

```bash
RC_APP_PROCESS=RingCentral
DESKTOP_CONNECT_WAIT_SECONDS=15
DESKTOP_ACTION_DELAY_SECONDS=0.8
DESKTOP_STATUS_DELAY_SECONDS=1.2
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Accessibility denied | Enable Terminal/Python in System Settings |
| RingCentral not running | Open RingCentral.app first |
| Not found: Start working | Run `inspect`, fix `rc_desktop/labels.yaml` |
| Lunch menu wrong | Update `unavailable` / `lunch` in labels.yaml |
| Wrong timezone / times | Same `.env` as main app; use `run.py menu` or edit `.env` |
| Two automations conflict | Uninstall other schedulers (`run.py` / `rc_run.py` services) |

---

## Safety notes

- Runs only on your Mac; no cloud API credentials
- Needs **Accessibility** — can control UI while the script runs
- Fragile if RingCentral updates its UI — re-run `inspect` and update labels
- For production long-term, IT-approved **Agent API** (`rc_run.py`) is more reliable
