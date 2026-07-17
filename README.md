# RCAutoLogin

Automate **RingCX** web agent login, lunch/dinner, break, and logout on a daily schedule.

**Repo:** https://github.com/sarpatil-07/ring-central-automation  
**Releases:** https://github.com/sarpatil-07/ring-central-automation/releases

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python 3.12+** | Use **3.12 or 3.13** (3.14+ not supported yet) |
| **Google Chrome** | Or Chromium |
| **Desktop session** | Mac or Linux GUI (not headless-only SSH) |

```bash
# macOS
brew install python@3.12
```

---

## Install (from release zip)

1. Download **RCAutoLogin-*-portable.zip** from [Releases](https://github.com/sarpatil-07/ring-central-automation/releases)
2. Unzip, then in Terminal:

```bash
cd ~/Downloads/RCAutoLogin-*-portable   # or wherever you unzipped
chmod +x install.sh launch-gui.sh "Launch RCAutoLogin.command"
./install.sh
```

---

## Launch GUI

### Mac

```bash
cd /path/to/RCAutoLogin-*-portable

# Option A — script (recommended)
./launch-gui.sh

# Option B — double-click in Finder
open "Launch RCAutoLogin.command"

# Option C — direct Python
.venv/bin/python rc_autologin_run.py
```

Or open **RCAutoLogin.app** if included in the zip.

### Linux

```bash
cd /path/to/RCAutoLogin-*-portable

# Option A — script (recommended)
./launch-gui.sh

# Option B — direct Python
.venv/bin/python rc_autologin_run.py
```

GUI opens at **http://127.0.0.1:8765/**

---

## Install from git clone

```bash
git clone https://github.com/sarpatil-07/ring-central-automation.git
cd ring-central-automation
cp .env.example .env          # add your login + schedule
bash packaging/install.sh
./packaging/launch-gui.sh     # or: .venv/bin/python rc_autologin_run.py
```

---

## First-time setup in the GUI

1. **Setup** tab → save RingCentral email + password  
2. **Schedule** tab → work / lunch times → Save  
3. **Today** tab → **Start auto job**

Credentials stay in local `.env` (never commit that file).

---

## Docs

- `RC_AUTOLOGIN_SETUP.md` — full setup  
- `SHARE.md` / `BUILD_AND_SHARE.md` — building the portable zip  
