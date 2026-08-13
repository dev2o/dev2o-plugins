"""Tests for advisor transcript injection into the Task prompt."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from conftest import REPO_ROOT

REAL_ID = "959870a8-e0be-40e6-96ca-9ef9226cff13"
HOOK = REPO_ROOT / "hooks" / "context-injector" / "subagent-context-pre-tool-use.sh"
MARKER = "unique-advisor-inject-marker"


def _write_transcript(project_root: Path, cid: str) -> None:
    log_dir = project_root / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True)
    event = {
        "conversation_id": cid,
        "hook_event_name": "beforeSubmitPrompt",
        "prompt": MARKER,
        "ts": "2026-07-21T12:00:00Z",
    }
    (log_dir / f"{cid}.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")


def _advisor_prompt(project_root: Path, lookup: str, fallback: str = "") -> str:
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    proc = subprocess.run(
        [
            "bash",
            "-c",
            f'source hooks/context-injector/lib/context.sh && advisor_injection_prompt "{lookup}" "{fallback}" ""',
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return proc.stdout


def test_advisor_prompt_contains_show_output(tmp_path: Path) -> None:
    _write_transcript(tmp_path, REAL_ID)
    out = _advisor_prompt(tmp_path, REAL_ID)
    assert "<execution_transcript>" in out
    assert "</execution_transcript>" in out
    assert MARKER in out
    assert REAL_ID in out
    assert "Advise." not in out
    assert "{{CONVERSATION_ID}}" not in out


def test_advisor_prompt_uses_resolved_fallback_id(tmp_path: Path) -> None:
    _write_transcript(tmp_path, REAL_ID)
    out = _advisor_prompt(tmp_path, "missing-id", REAL_ID)
    assert REAL_ID in out
    assert MARKER in out
    assert "{{CONVERSATION_ID}}" not in out


def test_advisor_prompt_unavailable_without_id(tmp_path: Path) -> None:
    out = _advisor_prompt(tmp_path, "")
    assert "<execution_transcript>" in out
    assert "(conversation id unavailable)" in out
    assert "Advise." not in out
    assert "{{CONVERSATION_ID}}" not in out


def test_hook_replaces_orig_prompt(tmp_path: Path) -> None:
    _write_transcript(tmp_path, REAL_ID)
    payload = {
        "tool_name": "Task",
        "conversation_id": REAL_ID,
        "tool_input": {"subagent_type": "advisor", "prompt": "Advise."},
    }
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(tmp_path)
    proc = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    data = json.loads(proc.stdout)
    prompt = data["updated_input"]["prompt"]
    assert data["permission"] == "allow"
    assert "<execution_transcript>" in prompt
    assert MARKER in prompt
    assert "Advise." not in prompt
    assert "{{CONVERSATION_ID}}" not in prompt
