"""Byte-identity and differential parity against agent-conductor's deny script."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from conftest import AC_DENY_SH, ENV_PROTECT_SH

# deny: current regex classes (bare env/printenv/export -p, and reader + .env path)
DENY_COMMANDS = [
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

# allow: not covered by the three regexes
ALLOW_COMMANDS = [
    "command -v op",
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


@pytest.mark.skipif(not AC_DENY_SH.is_file(), reason="agent-conductor not in tree")
def test_byte_identical_to_agent_conductor() -> None:
    assert ENV_PROTECT_SH.read_bytes() == AC_DENY_SH.read_bytes()


@pytest.mark.skipif(not AC_DENY_SH.is_file(), reason="agent-conductor not in tree")
@pytest.mark.parametrize("command", DENY_COMMANDS + ALLOW_COMMANDS)
@pytest.mark.parametrize("shape", PAYLOAD_SHAPES)
def test_output_matches_agent_conductor(command: str, shape: str) -> None:
    payload = {"command": command} if shape == "command" else {"tool_input": {"command": command}}
    ours = _run(ENV_PROTECT_SH, payload)
    theirs = _run(AC_DENY_SH, payload)
    assert ours.stdout == theirs.stdout
    assert json.loads(ours.stdout)["permission"] == (
        "deny" if command in DENY_COMMANDS else "allow"
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
