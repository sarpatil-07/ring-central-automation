# RCAutoLogin — RingCX Web Agent

Automates **https://app.ringcentral.com/ring_cx/agent** in a **dedicated Chrome profile**.

**RCAutoLogin only** — use `rc_autologin_run.py` (not `run.py` or other tools).

---

## What it does

| Time | Actions |
|------|---------|
| Work start | Open RingCX Chrome → Agent tab → **Start session** → **AVAILABLE** |
| Lunch | Presence pill → **LUNCH** |
| After lunch | Presence pill → **AVAILABLE** |
| Work end | Presence pill → **Stop session** → close browser |

Uses stable `data-test-automation-id` selectors (see `rc_autologin/selectors.yaml`).

---

## First install

```bash
cd ~/Projects/Ring_Central_Automation
bash setup.sh   # once: venv + Playwright + Chrome
.venv/bin/python rc_autologin_run.py   # open GUI
```

---

## One-time setup (each user)

1. **Save login (once)** — email + password in GUI → stored in local `.env`
2. **Save schedule** — work start/end, lunch times, timezone
3. **Start auto job** — click in GUI or run `install-service`

After step 3, you can **close the GUI browser tab and terminal** — daily jobs still run on schedule.

---

## Daily background (runs without GUI)

The **GUI is only a control panel**. The scheduler is a **separate background process**.

| | |
|--|--|
| **Start once** | GUI → **Start auto job**, or `.venv/bin/python rc_autologin_run.py install-service` |
| **Runs when** | Your saved work times, every configured work day |
| **Survives** | Closing GUI tab, stopping GUI terminal, Mac/Linux restart |
| **Mac** | LaunchAgent — starts on login |
| **Linux** | systemd user service |
| **Logs** | `logs/rc-autologin-scheduler.log` |

Check status: `.venv/bin/python rc_autologin_run.py service-status`

---

## Daily use — GUI (optional control panel)

```bash
.venv/bin/python rc_autologin_run.py
# or
./rc_autologin.sh
```

Opens a **browser window** at `http://127.0.0.1:8765/` with:
- **One-time setup checklist** — login, schedule, Start auto job
- **RingCentral login** — save once per user (local `.env`)
- **Schedule fields** — work start/end, lunch, timezone → **Save schedule**
- **Run now** — manual Login, Lunch, Back, Logout (for testing)
- **Daily background job** — Start / Stop auto job, Pause, leave today
- **Activity log** at the bottom

Closing the GUI does **not** stop the background scheduler (if Start auto job was clicked).

Press **Ctrl+C** in the terminal only stops the **GUI server**, not the scheduler.

### Dock app (one-click launch)

```bash
.venv/bin/python rc_autologin_run.py install-app
```

This installs **RCAutoLogin.app** in `~/Applications`. Drag it to your Dock.

- Double-click opens the GUI in your browser (starts the server in the background if needed).
- If the GUI is already running, it just opens the browser tab again.
- Logs: `logs/gui-server.log`

Remove: `.venv/bin/python rc_autologin_run.py uninstall-app`

### Share with others (Mac + Linux)

```bash
.venv/bin/python rc_autologin_run.py build-release
```

Creates `dist/RCAutoLogin-1.0.0-portable.zip` — send to anyone. They unzip, run `./install.sh` once, then launch. See **SHARE.md**.

Text menu (CLI): `.venv/bin/python rc_autologin_run.py menu`

Menu options:
- **2** — Set all times (work start/end, lunch start/end, e.g. 1 hour lunch 13:00–14:00)
- **m/l/b/g** — Run login, lunch, back from lunch, logout now
- **i** — Start background job (auto on Mac login)
- **o** — Stop background job
- **t** — Background job status

---

## Commands (CLI)

```bash
.venv/bin/python rc_autologin_run.py show
.venv/bin/python rc_autologin_run.py morning
.venv/bin/python rc_autologin_run.py lunch
.venv/bin/python rc_autologin_run.py lunch-end
.venv/bin/python rc_autologin_run.py logout
.venv/bin/python rc_autologin_run.py schedule
.venv/bin/python rc_autologin_run.py install-service
.venv/bin/python rc_autologin_run.py uninstall-service
```

---

## Optional `.env`

```bash
RCX_AGENT_URL=https://app.ringcentral.com/ring_cx/agent?env=production
CHROME_RCX_PROFILE_DIR=./chrome-rcx-profile
CHROME_RCX_CDP_PORT=9334
RCX_CONNECT_WAIT_SECONDS=30
```

---

## Logs

```
logs/rc-autologin-scheduler.log
logs/rc-autologin-scheduler.err.log
```

---

## Selectors (if UI changes)

Edit `rc_autologin/selectors.yaml`:

| Step | Selector |
|------|----------|
| Agent tab | `data-test-automation-id="rcxAgent"` |
| Start session | `rcx-presence-pill[connectstate="disconnected"]` |
| Status pill | `rcx-presence-pill[connectstate="connected"]` |
| AVAILABLE | `rcx-presence-menu-item-AVAILABLE` |
| LUNCH | `rcx-presence-menu-item-LUNCH` |
| Stop session | `rcx-presence-menu-item-stop-session` |
