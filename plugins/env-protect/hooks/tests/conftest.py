"""Shared paths for env-protect tests."""

from __future__ import annotations

from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = HOOKS_DIR.parent
REPO_ROOT = PLUGIN_ROOT.parent.parent
ENV_PROTECT_SH = HOOKS_DIR / "env-protect.sh"
INSTALL_SH = PLUGIN_ROOT / "scripts" / "install.sh"
AC_DENY_SH = (
    REPO_ROOT / "plugins" / "agent-conductor" / "hooks" / "transcriptor" / "shell-secrets-deny.sh"
)
REAL_HOOKS_JSON = REPO_ROOT / ".cursor" / "hooks.json"
