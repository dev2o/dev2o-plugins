"""Tests for shell-secrets-deny.sh."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import HOOKS_TRANSCRIPTS

DENY_SH = HOOKS_TRANSCRIPTS / "shell-secrets-deny.sh"


def _run_deny(payload: dict) -> dict:
    result = subprocess.run(
        [str(DENY_SH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_deny_env_pipe_grep() -> None:
    out = _run_deny({"tool_input": {"command": "env | grep -E 'OP_|TAVILY' || true"}})
    assert out["permission"] == "deny"


def test_deny_printenv() -> None:
    out = _run_deny({"command": "printenv OP_TOKEN"})
    assert out["permission"] == "deny"


def test_deny_cat_dotenv() -> None:
    out = _run_deny({"tool_input": {"command": "cat /workspaces/app/.env"}})
    assert out["permission"] == "deny"


def test_allow_command_v_op() -> None:
    out = _run_deny({"tool_input": {"command": "command -v op; ls -la .env 2>/dev/null || true"}})
    assert out["permission"] == "allow"


def test_allow_node_env_file() -> None:
    out = _run_deny({"command": "node --env-file=.env app.js"})
    assert out["permission"] == "allow"
