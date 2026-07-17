# Share RCAutoLogin with others

**Full guide:** see **BUILD_AND_SHARE.md**

---

## Build the shareable bundle (you)

```bash
cd ~/Projects/Ring_Central_Automation
bash setup.sh                              # first time only
.venv/bin/python rc_autologin_run.py build-release
# or:  ./scripts/build_zip.sh
```

**Output:** `dist/RCAutoLogin-1.0.0-portable.zip`

### Never include in the zip

| File / folder | Contains |
|---------------|----------|
| `.env` | Schedule, login ID, **password** |
| `chrome-rcx-profile/` | Browser login cookies |
| `.venv/` | Your Python install |
| `logs/` | Your logs |

`build-release` excludes these automatically. **Do not** zip the project folder by hand.

---

## User setup (after receiving zip)

1. Unzip → `cd RCAutoLogin-1.0.0-portable`
2. `./install.sh` (once)
3. Mac: `Launch RCAutoLogin.command` · Linux: `./launch-gui.sh`
4. GUI **Setup** → save login · **Schedule** → save times · **Today** → **Start auto job**

See **BUILD_AND_SHARE.md** for full steps.
