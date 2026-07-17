"""Background scheduler install — macOS LaunchAgent or Linux systemd."""

from __future__ import annotations

import sys

if sys.platform == "darwin":
    from rc_autologin.mac_service import *  # noqa: F403
else:
    from rc_autologin.linux_service import *  # noqa: F403
