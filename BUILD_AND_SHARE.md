# RCAutoLogin — Build zip & share (RingCX)

Guide for packaging **RCAutoLogin** (RingCX web agent) for Mac and Linux users.

---

## Part A — Build the zip (once per release)

### Prerequisites

- **Python 3.12+** (3.12 or 3.13; 3.14+ not supported yet)
- Google Chrome

```bash
cd ~/Projects/Ring_Central_Automation   # or your clone
bash packaging/install.sh               # first time — creates .venv
```

### Build

```bash
.venv/bin/python rc_autologin_run.py build-release
```

**Output:**

```
dist/RCAutoLogin-1.1.0-portable.zip
```

### Included

| Included | Purpose |
|----------|---------|
| `rc_autologin/`, `rc_autologin_run.py` | RingCX automation + GUI |
| `requirements.txt` | Dependencies |
| `install.sh`, `launch-gui.sh` | Setup & launch |
| `Launch RCAutoLogin.command` | Mac double-click launcher |
| `RCAutoLogin.app` (Mac builds) | Optional Dock launcher |
| `.env.example`, `README-FIRST.txt`, docs | Instructions |

### Excluded (never share)

| Excluded | Why |
|----------|-----|
| `.env` | Login ID & password |
| `chrome-rcx-profile/` | Chrome session cookies |
| `.venv/` | Local Python environment |
| `logs/` | Runtime logs |
| `dist/` | Old build artifacts |

Each user gets a **fresh `.env`** when they run `install.sh`.

### Checklist before sharing

- [ ] Built with `build-release` (not a manual zip of the whole project)
- [ ] No `.env` inside the zip
- [ ] Test on a clean folder / machine if possible

### Verify zip

```bash
unzip -l dist/RCAutoLogin-1.1.0-portable.zip | head -40
# Should NOT list .env or chrome-rcx-profile
```

---

## Part B — End user install (Mac or Linux)

### 1. Unzip

```bash
cd ~/Downloads
unzip RCAutoLogin-1.1.0-portable.zip
cd RCAutoLogin-1.1.0-portable
```

Prefer a local folder (e.g. `~/RCAutoLogin`), not iCloud Downloads.

### 2. One-time install

```bash
chmod +x install.sh launch-gui.sh "Launch RCAutoLogin.command"
./install.sh
```

Creates `.venv/`, `.env` from template, and Playwright browser support.

**Requires:** Python 3.12+, Chrome/Chromium, internet for first install.

### 3. Launch GUI

| Platform | Command |
|----------|---------|
| **Mac** | `./launch-gui.sh` · or double-click `Launch RCAutoLogin.command` · or `.venv/bin/python rc_autologin_run.py` |
| **Linux** | `./launch-gui.sh` · or `.venv/bin/python rc_autologin_run.py` |

Opens **http://127.0.0.1:8765/**

### 4. One-time GUI setup

| Step | Tab | Action |
|------|-----|--------|
| 1 | **Setup** | Email + password → **Save login** |
| 2 | **Schedule** | Work/lunch times → **Save schedule** |
| 3 | **Today** | **Start auto job** |

### 5. Daily use

- Rely on the background job, or use **Today** quick actions: Login, Lunch/Dinner, Break, Back, Logout  
- **Mark leave** = logout + pause until **Clear leave** (safe for multi-day leave)  
- No need to keep the GUI open after **Start auto job**

---

## Part C — Platform notes

### Mac

- First open of `RCAutoLogin.app`: right-click → **Open** (if Gatekeeper warns)
- Background: LaunchAgent on login
- Logs: `logs/rc-autologin-scheduler.log`

### Linux (Ubuntu / Fedora)

- Python: `python3.12` / `python3.13`
- Background: systemd user service
- Fedora: Playwright `ubuntu20.04` fallback warnings are OK
- Optional: `loginctl enable-linger $USER`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `install.sh` fails on Python | Install Python 3.12 or 3.13 |
| Chrome not found | Install Google Chrome or Chromium |
| GUI looks old | Hard refresh (Cmd/Ctrl+Shift+R); restart `./launch-gui.sh` |
| Zip contained `.env` | Rebuild with `build-release` only |

---

## Quick reference

```bash
# Builder
.venv/bin/python rc_autologin_run.py build-release

# User (after unzip)
./install.sh
./launch-gui.sh
```
