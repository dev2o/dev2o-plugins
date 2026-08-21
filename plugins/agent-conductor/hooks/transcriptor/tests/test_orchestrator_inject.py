"""The orchestrator inject must land exactly once per prompt."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from conftest import REPO_ROOT

INJECT = REPO_ROOT / "hooks" / "context-injector" / "main-agent-orchestrator-inject.sh"


def _run(payload: dict, project_root: Path) -> dict:
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    result = subprocess.run(
        ["bash", str(INJECT)],
        input=json.dumps(payload),
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _payload() -> dict:
    return {
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeSubmitPrompt",
        "composer_mode": "agent",
        "prompt": "do the thing",
    }


def test_inject_delivers_the_orchestrator_context(tmp_path: Path) -> None:
    out = _run(_payload(), tmp_path)
    assert out["continue"] is True
    assert "delegation_protocol" in out["additional_context"]


def test_inject_is_claimed_once_per_prompt(tmp_path: Path) -> None:
    payload = _payload()
    first = _run(payload, tmp_path)
    second = _run(payload, tmp_path)
    assert "additional_context" in first
    assert "additional_context" not in second


def test_a_later_prompt_is_injected_again(tmp_path: Path) -> None:
    payload = _payload()
    _run(payload, tmp_path)
    later = dict(payload, generation_id=str(uuid.uuid4()))
    assert "additional_context" in _run(later, tmp_path)
