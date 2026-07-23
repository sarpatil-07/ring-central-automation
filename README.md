# RCAutoLogin (RingCX)

Automate the **Ring Central RingCX web agent** (`app.ringcentral.com/ring_cx/agent`): daily login → AVAILABLE, lunch/dinner, break, back to AVAILABLE, and logout — on your saved schedule.

**Repo:** https://github.com/sarpatil-07/ring-central-automation  
**Releases:** https://github.com/sarpatil-07/ring-central-automation/releases

This repository documents **RCAutoLogin only** (GUI + background scheduler for RingCX). Use `rc_autologin_run.py` / `./launch-gui.sh`.

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python 3.12+** | Use **3.12 or 3.13** (3.14+ not supported yet) |
| **Google Chrome** | Or Chromium (`google-chrome` / `chromium` on Linux) |
| **Desktop session** | Mac or Linux GUI (not headless-only SSH) |

```bash
# macOS
brew install python@3.12

# Fedora
sudo dnf install python3.12 google-chrome-stable
# or: sudo dnf install chromium
```

**Fedora / Linux:** If `./install.sh` prints `chrome is already installed` or `BEWARE: … ubuntu20.04-x64`, that is **normal**. Setup still completed.

---

## Install (from release zip)

1. Download **RCAutoLogin-*-portable.zip** from [Releases](https://github.com/sarpatil-07/ring-central-automation/releases)
2. Unzip, then:

```bash
cd ~/Downloads/RCAutoLogin-*-portable   # or your unzip path
chmod +x install.sh launch-gui.sh "Launch RCAutoLogin.command"
./install.sh
```

---

## Launch GUI

### Mac

```bash
./launch-gui.sh
# or: open "Launch RCAutoLogin.command"
# or: .venv/bin/python rc_autologin_run.py
```

### Linux

```bash
./launch-gui.sh
# or: .venv/bin/python rc_autologin_run.py
```

GUI: **http://127.0.0.1:8765/**

---

## Install from git clone

```bash
git clone https://github.com/sarpatil-07/ring-central-automation.git
cd ring-central-automation
cp .env.example .env          # add your own login + schedule
bash packaging/install.sh
./packaging/launch-gui.sh
```

---

## First-time setup (GUI)

1. **Setup** → RingCentral email + password → **Save login** (stored locally on the machine)  
2. **Schedule** → work / lunch times, timezone, work days → **Save schedule**  
3. **Today** → **Start auto job**

After that, you can close the GUI — scheduled jobs keep running in the background.

### Manage RingCX from Today

**Quick actions:** Login · Lunch/Dinner · Break · Back · Logout  

**Background:** Start / Stop auto job · Pause / Resume · **Mark leave** (logout + pause until **Clear leave**) · Close RingCX Chrome  

Credentials stay in local `.env` — never commit that file.

---

## More docs

| Doc | Contents |
|-----|----------|
| [RC_AUTOLOGIN_SETUP.md](RC_AUTOLOGIN_SETUP.md) | Full setup, schedule, leave, CLI |
| [BUILD_AND_SHARE.md](BUILD_AND_SHARE.md) | Build portable zip for Mac/Linux |
| [SHARE.md](SHARE.md) | Short share checklist |
