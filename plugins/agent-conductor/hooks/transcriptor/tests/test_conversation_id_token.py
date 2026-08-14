"""Tests for advisor / exe-advisor transcript injection into the Task prompt."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from conftest import REPO_ROOT

REAL_ID = "959870a8-e0be-40e6-96ca-9ef9226cff13"
GATEKEEPER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
HOOK = REPO_ROOT / "hooks" / "context-injector" / "subagent-context-pre-tool-use.sh"
MARKER = "unique-advisor-inject-marker"


def _write_transcript(project_root: Path, cid: str) -> None:
    log_dir = project_root / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "conversation_id": cid,
        "hook_event_name": "beforeSubmitPrompt",
        "prompt": MARKER,
        "ts": "2026-07-21T12:00:00Z",
    }
    (log_dir / f"{cid}.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")


def _run_fn(project_root: Path, expr: str) -> str:
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    proc = subprocess.run(
        ["bash", "-c", f"source hooks/context-injector/lib/context.sh && {expr}"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return proc.stdout


def _advisor_prompt(project_root: Path, lookup: str, fallback: str = "") -> str:
    return _run_fn(
        project_root,
        f'advisor_injection_prompt "{lookup}" "{fallback}" ""',
    )


def _gatekeeper_prompt(project_root: Path, lookup: str, fallback: str = "") -> str:
    return _run_fn(
        project_root,
        f'advisor_gatekeeper_prompt "{lookup}" "{fallback}" ""',
    )


def _hook(project_root: Path, payload: dict) -> dict:
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    proc = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(proc.stdout)


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


def test_gatekeeper_prompt_has_id_and_last_messages(tmp_path: Path) -> None:
    _write_transcript(tmp_path, REAL_ID)
    out = _gatekeeper_prompt(tmp_path, REAL_ID)
    assert "The Executor agent has invoked you for strategic guidance." in out
    assert f"<conversation_id>{REAL_ID}</conversation_id>" in out
    assert "<inputs>" in out
    assert "<recent_transcript>" in out
    assert MARKER in out
    assert f"CID:{REAL_ID}" in out
    assert "exe-advisor" in out
    assert "<execution_transcript>" not in out
    assert "Advise." not in out
    assert "{{CONVERSATION_ID}}" not in out


def test_hook_advisor_injects_gatekeeper_template(tmp_path: Path) -> None:
    _write_transcript(tmp_path, REAL_ID)
    data = _hook(
        tmp_path,
        {
            "tool_name": "Task",
            "conversation_id": REAL_ID,
            "tool_input": {"subagent_type": "advisor", "prompt": "Advise."},
        },
    )
    prompt = data["updated_input"]["prompt"]
    assert data["permission"] == "allow"
    assert f"<conversation_id>{REAL_ID}</conversation_id>" in prompt
    assert MARKER in prompt
    assert "Advise." not in prompt
    assert "<execution_transcript>" not in prompt
    assert "{{CONVERSATION_ID}}" not in prompt


def test_hook_exe_advisor_uses_cid_not_hook_conversation_id(tmp_path: Path) -> None:
    _write_transcript(tmp_path, REAL_ID)
    data = _hook(
        tmp_path,
        {
            "tool_name": "Task",
            "conversation_id": GATEKEEPER_ID,
            "tool_input": {
                "subagent_type": "exe-advisor",
                "prompt": f"CID:{REAL_ID}",
            },
        },
    )
    prompt = data["updated_input"]["prompt"]
    assert data["permission"] == "allow"
    assert "<execution_transcript>" in prompt
    assert MARKER in prompt
    assert REAL_ID in prompt
    assert f"CID:{REAL_ID}" not in prompt
    assert GATEKEEPER_ID not in prompt


def test_hook_exe_advisor_malformed_prompt_stubs(tmp_path: Path) -> None:
    _write_transcript(tmp_path, REAL_ID)
    data = _hook(
        tmp_path,
        {
            "tool_name": "Task",
            "conversation_id": REAL_ID,
            "tool_input": {"subagent_type": "exe-advisor", "prompt": "Advise."},
        },
    )
    prompt = data["updated_input"]["prompt"]
    assert data["permission"] == "allow"
    assert "<execution_transcript>" in prompt
    assert "(conversation id unavailable)" in prompt
    assert MARKER not in prompt
