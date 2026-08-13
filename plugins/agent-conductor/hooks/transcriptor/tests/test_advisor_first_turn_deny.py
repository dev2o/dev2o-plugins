"""Tests for advisor-first-turn-deny.sh."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from conftest import REPO_ROOT

DENY_SH = REPO_ROOT / "hooks" / "context-injector" / "advisor-first-turn-deny.sh"
CID = "11111111-1111-1111-1111-111111111111"
DENY_MSG = "ensure your usage of the advisor follows the advisor_protocol, then reuse when ready"


def _run(project_root: Path, payload: dict) -> dict:
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    result = subprocess.run(
        [str(DENY_SH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(result.stdout)


def _advisor_task() -> dict:
    return {
        "tool_name": "Task",
        "conversation_id": CID,
        "tool_input": {
            "description": "Advise",
            "prompt": "Advise.",
            "subagent_type": "advisor",
            "model": "claude-opus-5-thinking-high",
        },
    }


def _write_prompts(project_root: Path, n: int) -> None:
    log_dir = project_root / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True)
    line = json.dumps({"hook_event_name": "beforeSubmitPrompt", "prompt": "hi"}) + "\n"
    extra = json.dumps({"hook_event_name": "afterAgentThought", "text": "x"}) + "\n"
    (log_dir / f"{CID}.jsonl").write_text(extra + line * n, encoding="utf-8")


def test_deny_first_prompt(tmp_path: Path) -> None:
    _write_prompts(tmp_path, 1)
    out = _run(tmp_path, _advisor_task())
    assert out["permission"] == "deny"
    assert out["agent_message"] == DENY_MSG


def test_deny_missing_transcript(tmp_path: Path) -> None:
    out = _run(tmp_path, _advisor_task())
    assert out["permission"] == "deny"


def test_allow_second_prompt(tmp_path: Path) -> None:
    _write_prompts(tmp_path, 2)
    out = _run(tmp_path, _advisor_task())
    assert out["permission"] == "allow"


def test_allow_non_advisor(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        {
            "tool_name": "Task",
            "conversation_id": CID,
            "tool_input": {"subagent_type": "explore", "prompt": "look"},
        },
    )
    assert out["permission"] == "allow"
