# Share RCAutoLogin (RingCX)

**Full guide:** [BUILD_AND_SHARE.md](BUILD_AND_SHARE.md)

Portable zip for **RingCX web agent** automation — Mac and Linux. Each user keeps their own login on their machine.

---

## Build the shareable bundle

```bash
cd ~/Projects/Ring_Central_Automation   # or your clone path
bash packaging/install.sh               # first time only
.venv/bin/python rc_autologin_run.py build-release
```

**Output:** `dist/RCAutoLogin-1.1.0-portable.zip`

### Prerequisites (each recipient)

- **Python 3.12+** (3.12 or 3.13; 3.14+ not supported yet)
- Google Chrome or Chromium
- Desktop session (Mac/Linux GUI)

### Never include in the zip

| File / folder | Why |
|---------------|-----|
| `.env` | Schedule + login password |
| `chrome-rcx-profile/` | Browser cookies / session |
| `.venv/` | Local Python env |
| `logs/` | Runtime logs |

`build-release` excludes these automatically. **Do not** zip the project folder by hand.

---

## User setup (after receiving zip)

1. Unzip → `cd RCAutoLogin-1.1.0-portable`
2. `./install.sh` (once)
3. Launch: Mac → `./launch-gui.sh` or `Launch RCAutoLogin.command` · Linux → `./launch-gui.sh`
4. GUI: **Setup** (login) → **Schedule** → **Today** → **Start auto job**

See [BUILD_AND_SHARE.md](BUILD_AND_SHARE.md) for details.
