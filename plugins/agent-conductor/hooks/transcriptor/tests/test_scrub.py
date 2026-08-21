"""Tests for audit.sh scrubbing and capture."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from conftest import AUDIT_SH, FIXTURES, SCRUB_JQ


def _run_audit(project_root: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    env = {"CURSOR_PROJECT_DIR": str(project_root)}
    return subprocess.run(
        [str(AUDIT_SH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _read_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_audit_writes_scrubbed_jsonl(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "before_submit_email.json").read_text())
    result = _run_audit(tmp_path, payload)
    assert result.returncode == 0
    out = tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl"
    assert out.is_file()
    rows = _read_jsonl(out)
    assert len(rows) == 1
    row = rows[0]
    assert row["ts"]
    assert row["user_email"] == "user"
    assert "session_id" not in row
    assert "workspace_roots" not in row
    assert "transcript_path" not in row


def test_audit_null_email_unchanged(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "before_submit_null.json").read_text())
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de.jsonl"
    row = _read_jsonl(out)[0]
    assert row["user_email"] is None


def test_audit_before_read_file_drops_content(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "before_read_file.json").read_text())
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl"
    row = _read_jsonl(out)[0]
    assert "content" not in row
    assert row["file_path"].endswith("SKILL.md")
    assert row["future_field"] == 1


def test_audit_missing_conversation_id_writes_nothing(tmp_path: Path) -> None:
    result = _run_audit(tmp_path, {"hook_event_name": "stop"})
    assert result.returncode == 0
    assert not (tmp_path / ".cursor" / "chat-transcripts").exists()


def test_audit_path_traversal_conversation_id_writes_nothing(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        {"conversation_id": "../evil", "hook_event_name": "stop"},
    )
    assert result.returncode == 0
    assert not (tmp_path / ".cursor" / "chat-transcripts").exists()


def test_scrub_jq_present() -> None:
    assert SCRUB_JQ.is_file()


def test_audit_before_shell_execution_redacts_command(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "before_shell_execution_secret.json").read_text())
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "85189265-b5cb-454b-b201-bc4532062073.jsonl"
    row = _read_jsonl(out)[0]
    assert "command-secret-value" not in row["command"]
    assert "API_TOKEN=[REDACTED]" in row["command"]
    assert "keep-command-context" in row["command"]


def test_audit_before_submit_prompt_redacts_prompt(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "before_submit_prompt_secret.json").read_text())
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "29767380-b541-41b6-a58a-639adea36baa.jsonl"
    row = _read_jsonl(out)[0]
    assert "prompt-secret-value" not in row["prompt"]
    assert "PASSWORD=[REDACTED]" in row["prompt"]
    assert "keep prompt context" in row["prompt"]


def test_audit_pre_tool_use_redacts_tool_input(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "pre_tool_use_secret.json").read_text())
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "4d940726-0312-4917-a152-d25dc9370e3f.jsonl"
    row = _read_jsonl(out)[0]
    tool_input = row["tool_input"]
    note = tool_input["metadata"]["note"]
    assert "tool-input-secret-value" not in note
    assert "API_KEY=[REDACTED]" in note
    assert "keep tool input context" in note
    assert "old_string" not in tool_input
    assert "new_string" not in tool_input


def test_audit_post_tool_use_redacts_env_values(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "post_tool_use_env_leak.json").read_text())
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "34005c8e-b9dd-43bf-9a09-930a17c71735.jsonl"
    row = _read_jsonl(out)[0]
    assert "super-secret-token-abc123" not in row["tool_output"]
    assert "tvly-secret-key-xyz789" not in row["tool_output"]
    assert "OP_SERVICE_ACCOUNT_TOKEN=[REDACTED]" in row["tool_output"]
    assert "TAVILY_API_KEY=[REDACTED]" in row["tool_output"]
    assert "PATH=/usr/bin" in row["tool_output"]


def test_audit_after_agent_response_redacts_secrets(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "after_agent_response_secrets.json").read_text())
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl"
    row = _read_jsonl(out)[0]
    assert "leaked-in-response" not in row["text"]
    assert "OP_SERVICE_ACCOUNT_TOKEN=[REDACTED]" in row["text"]
    assert "sk-live-abc123def456" not in row["text"]
    assert "[REDACTED]" in row["text"]


def test_audit_after_shell_execution_keeps_short_output(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "after_shell_execution.json").read_text())
    _run_audit(tmp_path, payload)
    row = _read_jsonl(tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl")[0]
    assert row["output"] == "LINE1\nLINE2\nLINE3"
    assert row["command"] == "cat huge-file.txt"


def test_audit_after_shell_execution_keeps_the_tail_of_long_output(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "after_shell_execution.json").read_text())
    payload["output"] = "head-of-output\n" + ("x" * 4000) + "\nERROR: the useful part"
    _run_audit(tmp_path, payload)
    row = _read_jsonl(tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl")[0]
    assert row["output"].startswith("[TRUNCATED: kept the last 1200 of ")
    assert "ERROR: the useful part" in row["output"]
    assert "head-of-output" not in row["output"]
    assert len(row["output"]) < 1400


def test_audit_shell_output_is_still_redacted(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "after_shell_execution.json").read_text())
    payload["output"] = "OP_SERVICE_ACCOUNT_TOKEN=super-secret-value-1234567890"
    _run_audit(tmp_path, payload)
    row = _read_jsonl(tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl")[0]
    assert "super-secret-value" not in row["output"]
    assert "[REDACTED]" in row["output"]


def test_audit_after_file_edit_drops_edit_bodies(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "after_file_edit.json").read_text())
    _run_audit(tmp_path, payload)
    row = _read_jsonl(tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl")[0]
    assert row["file_path"].endswith("foo.ts")
    assert "old_string" not in row["edits"][0]
    assert "new_string" not in row["edits"][0]

