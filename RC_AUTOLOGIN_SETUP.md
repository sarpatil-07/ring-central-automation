# RCAutoLogin — RingCX setup guide

Automates **https://app.ringcentral.com/ring_cx/agent** in a **dedicated Chrome profile** (separate from your normal work browser).

**Entry point:** `rc_autologin_run.py` or `./launch-gui.sh`  
**GUI:** http://127.0.0.1:8765/

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python 3.12+** | **3.12 or 3.13** (3.14+ not supported yet) |
| **Google Chrome** | Or Chromium |
| **Desktop session** | Mac/Linux GUI (not headless SSH only) |

```bash
# macOS
brew install python@3.12
```

---

## What it does

| Time | Action |
|------|--------|
| Work start | Open RingCX Chrome → Agent → **Start session** → **AVAILABLE** |
| Lunch / Dinner | Set presence → **LUNCH** |
| Break (manual) | Set presence → **ON-BREAK** |
| Back | Set presence → **AVAILABLE** |
| Work end | **Stop session** → close RingCX browser |

Selectors live in `rc_autologin/selectors.yaml`.

---

## First install

### From release zip

```bash
unzip RCAutoLogin-*-portable.zip
cd RCAutoLogin-*-portable
./install.sh
./launch-gui.sh
```

### From git clone

```bash
cd ring-central-automation
bash packaging/install.sh
./packaging/launch-gui.sh
# or: .venv/bin/python rc_autologin_run.py
```

---

## One-time setup (each user)

1. **Setup** tab — email + password → **Save login** (local `.env` on this machine only)  
2. **Schedule** tab — work start/end, lunch, timezone, work days → **Save schedule**  
3. **Today** tab — **Start auto job**

Then you may close the GUI tab/terminal. Daily jobs still run.

---

## Background scheduler

| | |
|--|--|
| **Start** | GUI → **Start auto job**, or `rc_autologin_run.py install-service` |
| **Stop** | GUI → **Stop**, or `uninstall-service` |
| **Mac** | LaunchAgent — starts on Mac login |
| **Linux** | systemd user service |
| **Logs** | `logs/rc-autologin-scheduler.log` |

Status: `.venv/bin/python rc_autologin_run.py service-status`

**Missed jobs:** if the laptop was asleep or you logged in after work start, catch-up can still run login (and other due jobs) during the work day.

---

## Today tab — manage RingCX

| Control | Purpose |
|---------|---------|
| **Login** | Morning flow now |
| **Lunch/Dinner** | Set LUNCH |
| **Break** | Set ON-BREAK |
| **Back** | Set AVAILABLE |
| **Logout** | Stop session + close browser |
| **Start / Stop auto job** | Enable or disable background schedule |
| **Pause / Resume** | Temporarily stop / restart scheduled jobs |
| **Mark leave** | Logout now **and pause** scheduler until you return |
| **Clear leave** | Resume scheduler (multi-day leave safe) |
| **Close RingCX Chrome** | Clean up after closing Chrome manually |

---

## Leave

- **Mark leave** → logs out of RingCX and **pauses** the background job  
- Jobs stay off for tomorrow and later days until **Clear leave**  
- **Clear leave** → resumes the scheduler  

---

## CLI (optional)

```bash
.venv/bin/python rc_autologin_run.py show
.venv/bin/python rc_autologin_run.py morning
.venv/bin/python rc_autologin_run.py lunch
.venv/bin/python rc_autologin_run.py break
.venv/bin/python rc_autologin_run.py lunch-end
.venv/bin/python rc_autologin_run.py logout
.venv/bin/python rc_autologin_run.py install-service
.venv/bin/python rc_autologin_run.py uninstall-service
.venv/bin/python rc_autologin_run.py service-status
.venv/bin/python rc_autologin_run.py menu
.venv/bin/python rc_autologin_run.py build-release
```

---

## Optional `.env` keys

```bash
RCX_AGENT_URL=https://app.ringcentral.com/ring_cx/agent?env=production
RCX_LOGIN_ID=you@company.com
RCX_LOGIN_PASSWORD=
RCX_AUTO_LOGIN_ENABLED=true
TIMEZONE=Asia/Kolkata
WORK_DAYS=mon,tue,wed,thu,fri
WORK_START=09:00
WORK_END=18:00
LUNCH_START=13:00
LUNCH_END=14:00
LUNCH_ENABLED=true
```

Copy from `.env.example`. Never commit `.env`.

---

## Logs

```
logs/rc-autologin-scheduler.log
logs/rc-autologin-scheduler.err.log
```

---

## Selectors (if RingCX UI changes)

Edit `rc_autologin/selectors.yaml`:

| Step | Selector key |
|------|----------------|
| Agent tab | `rcxAgent` |
| Presence pill | `rcx-presence-pill` |
| AVAILABLE | `rcx-presence-menu-item-AVAILABLE` |
| LUNCH | `rcx-presence-menu-item-LUNCH` |
| ON-BREAK | `ON-BREAK` / `break_menu` |
| Stop session | `rcx-presence-menu-item-stop-session` |
