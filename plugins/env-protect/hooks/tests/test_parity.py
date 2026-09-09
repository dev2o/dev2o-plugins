"""Deny/allow corpus for env-protect.sh."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from conftest import ENV_PROTECT_SH

# Multi-line script: only stderr is redirected, so `op environment read` prints
# KEY=VALUE pairs to stdout and should be denied.
LEAKED_OP_COMMAND = """set +x
OP_SERVICE_ACCOUNT_TOKEN="$OP_TOKEN" op vault list 2>&1 | head -30
OP_SERVICE_ACCOUNT_TOKEN="$OP_TOKEN" op whoami 2>&1 | head -20
OP_SERVICE_ACCOUNT_TOKEN="$OP_TOKEN" op environment read env-id-example 2>/tmp/op-env.out
if [ $? -eq 0 ]; then
  awk -F= '{print $1}' /tmp/op-env.out
else
  head -c 200 /tmp/op-env.out; echo
fi
for name in A B C; do
  eval "tok=\\$OP_TOKEN_${name}"
  OP_SERVICE_ACCOUNT_TOKEN="$tok" op vault list 2>&1 | head -15
done
rm -f /tmp/op-env.out
"""

# deny: bare env/printenv/export -p, reader + .env path, and op secret reads to stdout
DENY_COMMANDS = [
    LEAKED_OP_COMMAND,
    "op environment read x",
    "op environment read x 2>/tmp/o",
    "op read op://v/i/f",
    "op item get x --reveal",
    "op document get d",
    "op inject -i .env.tpl",
    "foo && op read op://v/i/f",
    "env",
    "env | grep OP_",
    "printenv",
    "printenv OP_TOKEN",
    "export -p",
    "cat .env",
    "cat ./.env",
    "cat .env.local",
    "cat .env.example",  # '.' after .env is a name boundary, so this is denied
    "tail .env",
    "less .env",
    "more .env",
    "ls; env",
    "foo && printenv",
    "foo | env",
    "cat /workspaces/app/.env",
    # known false positive: `env` as a prefix assignment is still denied
    "env VAR=1 cmd",
]

# allow: not covered by the rules
ALLOW_COMMANDS = [
    "command -v op",
    # op: non-secret subcommands, or secret output redirected / piped / substituted
    "op run --env-file=.env -- cmd",
    "op whoami",
    "op vault list",
    "op item get x",
    "op read op://v/i/f > /tmp/s",
    "op read op://v/i/f | jq -r .",
    "op inject -i a -o b",
    "TOK=$(op read op://v/i/f)",  # known gap: substitution is not detected
    "awk -F= '{print $1}' /tmp/op-env.out",  # not a .env file
    "node --env-file=.env app.js",
    "ls -la .env",
    "cat .envrc",
    "cat environment.yml",
    # extra args between the reader and the path: the regex only sees the first token
    "head -n5 .env",
    "sed -n 1p .env",
    "grep KEY .env",
    "awk '{print}' .env",
    "printenvx",
    "echo $HOME",
    "dotenv run cmd",
    # known gaps: these leak env and are currently allowed
    "source .env",
    ". .env",
    "set",
    "declare -p",
    "python -c 'import os;print(os.environ)'",
]

PAYLOAD_SHAPES = ("command", "tool_input")


def _run(script: Path, payload: dict, *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=check,
        cwd=cwd,
    )


@pytest.mark.parametrize("command", DENY_COMMANDS)
@pytest.mark.parametrize("shape", PAYLOAD_SHAPES)
def test_denies_corpus(command: str, shape: str) -> None:
    payload = {"command": command} if shape == "command" else {"tool_input": {"command": command}}
    out = json.loads(_run(ENV_PROTECT_SH, payload).stdout)
    assert out["permission"] == "deny"
    assert "user_message" in out


@pytest.mark.parametrize("command", ALLOW_COMMANDS)
@pytest.mark.parametrize("shape", PAYLOAD_SHAPES)
def test_allows_corpus(command: str, shape: str) -> None:
    payload = {"command": command} if shape == "command" else {"tool_input": {"command": command}}
    out = json.loads(_run(ENV_PROTECT_SH, payload).stdout)
    assert out == {"permission": "allow"}


def test_empty_stdin_allows() -> None:
    result = subprocess.run(
        [str(ENV_PROTECT_SH)],
        input="",
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout) == {"permission": "allow"}


def test_missing_command_field_allows() -> None:
    out = json.loads(_run(ENV_PROTECT_SH, {"hook_event_name": "beforeShellExecution"}).stdout)
    assert out == {"permission": "allow"}
