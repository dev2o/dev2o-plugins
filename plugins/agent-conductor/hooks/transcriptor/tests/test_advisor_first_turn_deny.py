"""Tests for advisor-first-turn-deny.sh."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from conftest import REPO_ROOT

DENY_SH = REPO_ROOT / "hooks" / "context-injector" / "advisor-first-turn-deny.sh"
CID = "11111111-1111-1111-1111-111111111111"
GEN = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PRIOR = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
DENY_MSG = (
    "It is not common to use the advisor on the first turn.  You should gather intel, "
    "understand the project, and then ensure your usage of the advisor follows the "
    "advisor_protocol, then reuse when ready. Do not ignore future use of the advisor "
    "because of this block."
)


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
    return json.loads(result.stdout) if result.stdout.strip() else {"permission": "allow"}


def _advisor_task() -> dict:
    return {
        "tool_name": "Task",
        "conversation_id": CID,
        "generation_id": GEN,
        "tool_input": {
            "description": "Advise",
            "prompt": "Advise.",
            "subagent_type": "advisor",
            "model": "claude-opus-5-thinking-high",
        },
    }


def _write_events(project_root: Path, events: list[dict]) -> None:
    log_dir = project_root / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True)
    (log_dir / f"{CID}.jsonl").write_text(
        "".join(json.dumps(ev) + "\n" for ev in events),
        encoding="utf-8",
    )


def test_deny_prompt_only(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        [
            {"generation_id": GEN, "hook_event_name": "beforeSubmitPrompt", "prompt": "hi"},
            {"generation_id": GEN, "hook_event_name": "afterAgentThought", "text": "x"},
        ],
    )
    out = _run(tmp_path, _advisor_task())
    assert out["permission"] == "deny"
    assert out["agent_message"] == DENY_MSG
    assert out["user_message"] == DENY_MSG


def test_deny_missing_transcript(tmp_path: Path) -> None:
    out = _run(tmp_path, _advisor_task())
    assert out["permission"] == "deny"


def test_allow_after_read(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        [
            {"generation_id": GEN, "hook_event_name": "beforeSubmitPrompt", "prompt": "hi"},
            {"generation_id": GEN, "hook_event_name": "beforeReadFile", "file_path": "a.py"},
        ],
    )
    assert _run(tmp_path, _advisor_task())["permission"] == "allow"


def test_allow_after_grep(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        [
            {"generation_id": GEN, "hook_event_name": "beforeSubmitPrompt", "prompt": "hi"},
            {"generation_id": GEN, "hook_event_name": "preToolUse", "tool_name": "Grep"},
        ],
    )
    assert _run(tmp_path, _advisor_task())["permission"] == "allow"


def test_deny_when_read_was_prior_turn(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        [
            {"generation_id": PRIOR, "hook_event_name": "beforeReadFile", "file_path": "a.py"},
            {"generation_id": GEN, "hook_event_name": "beforeSubmitPrompt", "prompt": "hi"},
        ],
    )
    assert _run(tmp_path, _advisor_task())["permission"] == "deny"


def test_allow_non_advisor(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        {
            "tool_name": "Task",
            "conversation_id": CID,
            "generation_id": GEN,
            "tool_input": {"subagent_type": "explore", "prompt": "look"},
        },
    )
    assert out["permission"] == "allow"
