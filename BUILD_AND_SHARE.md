# RCAutoLogin — Build zip bundle & share with users

---

## Part A — You build the zip (once per release)

### Prerequisites

- **Python 3.12+** (3.12 or 3.13; 3.14+ not supported yet)
- Google Chrome

```bash
cd ~/Projects/Ring_Central_Automation
bash setup.sh    # first time only — creates .venv
# or: PYTHON=python3.12 bash packaging/install.sh
```

### Build the shareable zip

```bash
cd ~/Projects/Ring_Central_Automation
.venv/bin/python rc_autologin_run.py build-release
```

**Output file:**

```
dist/RCAutoLogin-1.1.0-portable.zip
```

Or use the helper script:

```bash
./scripts/build_zip.sh
```

### What is **included** in the zip

| Included | Purpose |
|----------|---------|
| Python app code (`rc_autologin/`, `rc_autologin_run.py`) | Automation + GUI |
| `requirements.txt` | Dependencies |
| `install.sh`, `launch-gui.sh` | Setup & launch |
| `Launch RCAutoLogin.command` | Mac double-click launcher |
| `RCAutoLogin.app` (Mac builds) | Dock launcher |
| `rc_autologin/.env.example` | Default schedule template |
| `README-FIRST.txt`, docs | Instructions |

### What is **excluded** (never share these)

| Excluded | Why |
|----------|-----|
| `.env` | Your schedule, **login ID & password** |
| `chrome-rcx-profile/` | Chrome cookies / SSO session |
| `.venv/` | Your local Python environment |
| `logs/` | Your runtime logs |
| `dist/` | Old build artifacts |
| Legacy folders (`chrome-max-profile/`, etc.) | Not used by RCAutoLogin |

Each user gets a **fresh `.env`** and **empty Chrome profile** when they run `install.sh`.

### Before you send the zip — checklist

- [ ] Built with `build-release` (not manual zip of whole folder)
- [ ] You are **not** zipping your project folder by hand with `.env` inside
- [ ] Test zip on another machine or clean folder if possible
- [ ] Share via Drive / Slack / email (zip is ~1–5 MB before `install.sh` downloads Chrome libs)

### Optional: verify zip contents

```bash
unzip -l dist/RCAutoLogin-1.0.0-portable.zip | head -40
# Should NOT list .env or chrome-rcx-profile
```

---

## Part B — End user installs (Mac or Linux)

### 1. Unzip

```bash
# Example: Downloads folder
cd ~/Downloads
unzip RCAutoLogin-1.0.0-portable.zip
cd RCAutoLogin-1.0.0-portable
```

Or unzip in Finder → move folder to `~/RCAutoLogin`

### 2. One-time install

```bash
cd ~/RCAutoLogin/RCAutoLogin-1.0.0-portable
chmod +x install.sh launch-gui.sh
./install.sh
```

This creates:
- `.venv/` — Python packages + Playwright browser
- `.env` — default schedule (from template)
- `chrome-rcx-profile/` — empty, for their login only

**Requires:** Python 3.12+, Google Chrome, internet for first install.

### 3. Launch GUI

| Platform | Command / action |
|----------|------------------|
| **Mac** | `./launch-gui.sh`  ·  or double-click `Launch RCAutoLogin.command`  ·  or `.venv/bin/python rc_autologin_run.py` |
| **Linux** | `./launch-gui.sh`  ·  or `.venv/bin/python rc_autologin_run.py` |

Browser opens at `http://127.0.0.1:8765/`

### 4. One-time setup in GUI (each user)

| Step | Tab | Action |
|------|-----|--------|
| 1 | **Setup** | Enter email + password → **Save login** |
| 2 | **Schedule** | Set work/lunch times → **Save schedule** |
| 3 | **Today** | Click **Start auto job** |

After step 3, daily login/lunch/logout runs in the background — even if they close the browser tab.

### 5. Daily use

- **Today** tab → **Login** (manual test) or rely on auto job
- No need to keep GUI open after **Start auto job**

---

## Part C — Platform notes

### Mac

- First open of `RCAutoLogin.app`: right-click → **Open** → **Open** (unsigned app)
- Background job: macOS LaunchAgent (starts on login)
- Logs: `logs/rc-autologin-scheduler.log`

### Linux

- Install Python: `sudo apt install python3 python3-venv`
- Background job: systemd user service
- Optional: `loginctl enable-linger $USER` (keep running after logout)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `install.sh` fails | Install Python 3.11+ |
| Chrome not found | Install Google Chrome |
| GUI blank / old UI | Hard refresh Cmd+Shift+R; restart server |
| Shared zip had `.env` inside | Rebuild with `build-release` — never zip project folder manually |

---

## Quick reference

```bash
# Builder
.venv/bin/python rc_autologin_run.py build-release

# User (after unzip)
./install.sh
./launch-gui.sh          # Linux
# or Launch RCAutoLogin.command   # Mac
```
