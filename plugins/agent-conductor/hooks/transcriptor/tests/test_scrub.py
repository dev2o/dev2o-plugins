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


def _scrubbed_command(tmp_path: Path, command: str) -> str:
    payload = json.loads((FIXTURES / "before_shell_execution_secret.json").read_text())
    payload["command"] = command
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "85189265-b5cb-454b-b201-bc4532062073.jsonl"
    return _read_jsonl(out)[0]["command"]


def _scrubbed_shell_output(tmp_path: Path, output: str) -> str:
    payload = json.loads((FIXTURES / "after_shell_execution.json").read_text())
    payload["output"] = output
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl"
    return _read_jsonl(out)[0]["output"]


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


def test_audit_redacts_cursor_api_key(tmp_path: Path) -> None:
    key = "crsr_d04dacee78262bc80c1722d8ea63db44b16cbf424836285161b2427d08da1fe1"
    command = _scrubbed_command(tmp_path, f"echo {key} > /tmp/note.txt")
    assert key not in command
    assert command == "echo [REDACTED] > /tmp/note.txt"


def test_audit_redacts_authorization_bearer_header(tmp_path: Path) -> None:
    token = "f7c3bc1d808e04732adf679965ccc34ca7ae3441"
    command = _scrubbed_command(
        tmp_path,
        f'curl -H "Authorization: Bearer {token}" https://api.cursor.com/v0/agents',
    )
    assert token not in command
    assert command == 'curl -H "Authorization: Bearer [REDACTED]" https://api.cursor.com/v0/agents'


def test_audit_redacts_authorization_basic_header(tmp_path: Path) -> None:
    credential = "YWRtaW46aHVudGVyMg=="
    command = _scrubbed_command(tmp_path, f"curl -H 'Authorization: Basic {credential}' https://example.com/api")
    assert credential not in command
    assert command == "curl -H 'Authorization: Basic [REDACTED]' https://example.com/api"


def test_audit_redacts_credential_bearing_cli_flags(tmp_path: Path) -> None:
    token = "f7c3bc1d808e04732adf679965ccc34ca7ae3441"
    command = _scrubbed_command(tmp_path, f'gh auth login --token "{token}" --hostname github.com')
    assert token not in command
    assert command == 'gh auth login --token "[REDACTED]" --hostname github.com'


def test_audit_redacts_basic_auth_user_flag(tmp_path: Path) -> None:
    command = _scrubbed_command(tmp_path, "curl -u admin:hunter2correcthorse https://example.com/api")
    assert "hunter2correcthorse" not in command
    assert command == "curl -u admin:[REDACTED] https://example.com/api"


def test_audit_leaves_numeric_uid_gid_pairs_alone(tmp_path: Path) -> None:
    command = _scrubbed_command(tmp_path, "docker run --rm -u 1000:1000 node:20 npm test")
    assert command == "docker run --rm -u 1000:1000 node:20 npm test"


def test_audit_leaves_date_format_strings_alone(tmp_path: Path) -> None:
    command = _scrubbed_command(tmp_path, "date -u +%H:%M:%S && ls -la --time-style=+%H:%M:%S .")
    assert command == "date -u +%H:%M:%S && ls -la --time-style=+%H:%M:%S ."


def test_audit_leaves_key_file_flags_alone(tmp_path: Path) -> None:
    command = _scrubbed_command(tmp_path, "curl --key client.key --cert client.crt https://mtls.example.com/")
    assert command == "curl --key client.key --cert client.crt https://mtls.example.com/"


def test_audit_redacts_password_in_connection_url(tmp_path: Path) -> None:
    command = _scrubbed_command(tmp_path, "psql postgres://appuser:s3cr3tdbpass@db.internal:5432/production")
    assert "s3cr3tdbpass" not in command
    assert command == "psql postgres://appuser:[REDACTED]@db.internal:5432/production"


def test_audit_redacts_password_in_connection_url_without_a_user(tmp_path: Path) -> None:
    command = _scrubbed_command(tmp_path, "redis-cli -u redis://:s3cr3tredispass@cache.internal:6379/0 ping")
    assert "s3cr3tredispass" not in command
    assert command == "redis-cli -u redis://:[REDACTED]@cache.internal:6379/0 ping"


def test_audit_redacts_lowercase_password_assignment(tmp_path: Path) -> None:
    command = _scrubbed_command(tmp_path, 'psql "host=db.internal user=appuser password=s3cr3tdbpass dbname=production"')
    assert "s3cr3tdbpass" not in command
    assert command == 'psql "host=db.internal user=appuser password=[REDACTED] dbname=production"'


def test_audit_redacts_aws_access_key_id(tmp_path: Path) -> None:
    output = _scrubbed_shell_output(
        tmp_path,
        '{"AccessKeyId":"AKIAIOSFODNN7EXAMPLE","Arn":"arn:aws:iam::123456789012:user/dev"}',
    )
    assert "AKIAIOSFODNN7EXAMPLE" not in output
    assert output == '{"AccessKeyId":"[REDACTED]","Arn":"arn:aws:iam::123456789012:user/dev"}'


def test_audit_redacts_google_api_key(tmp_path: Path) -> None:
    key = "AIzaSyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY"
    command = _scrubbed_command(tmp_path, f"curl 'https://maps.googleapis.com/maps/api/geocode/json?key={key}&address=nyc'")
    assert key not in command
    assert command == "curl 'https://maps.googleapis.com/maps/api/geocode/json?key=[REDACTED]&address=nyc'"


def test_audit_redacts_stripe_secret_key(tmp_path: Path) -> None:
    # Long enough for the 16-character rule, short of the 24 GitHub's own push
    # protection matches on. A realistic-length fixture here blocks the push.
    key = "sk_live_NOTAREALKEY000000"
    command = _scrubbed_command(tmp_path, f"curl https://api.stripe.com/v1/charges -u {key}:")
    assert key not in command
    assert command == "curl https://api.stripe.com/v1/charges -u [REDACTED]:"


def test_audit_redacts_npm_registry_token(tmp_path: Path) -> None:
    token = "npm_wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEab"
    command = _scrubbed_command(tmp_path, f"npm config set //registry.npmjs.org/:_authToken={token}")
    assert token not in command
    assert command == "npm config set //registry.npmjs.org/:_authToken=[REDACTED]"


def test_audit_redacts_github_server_to_server_token(tmp_path: Path) -> None:
    token = "ghs_16C7e42F292c6912E7710c838347Ae178B4a"
    output = _scrubbed_shell_output(tmp_path, f"remote token {token} expires in 1h")
    assert token not in output
    assert output == "remote token [REDACTED] expires in 1h"


def test_audit_redacts_private_key_pem_body(tmp_path: Path) -> None:
    body = "MIIEpAIBAAKCAQEA3Zx9kQfLmNoPqRsTuVwXyZaBcDeFgHiJkLmNoPqRsTuVwXyZ"
    output = _scrubbed_shell_output(
        tmp_path,
        f"-----BEGIN RSA PRIVATE KEY-----\n{body}\n-----END RSA PRIVATE KEY-----",
    )
    assert body not in output
    assert output == "-----BEGIN RSA PRIVATE KEY-----[REDACTED]-----END RSA PRIVATE KEY-----"


def test_audit_leaves_prose_about_keys_and_tokens_alone(tmp_path: Path) -> None:
    prose = (
        "Explain how API key rotation works: the token is read from the keychain, "
        "the password manager holds the secret, and each credential has a key id. "
        "Pass the --token flag to gh, or send the Authorization: Bearer header instead."
    )
    payload = json.loads((FIXTURES / "before_submit_prompt_secret.json").read_text())
    payload["prompt"] = prose
    _run_audit(tmp_path, payload)
    out = tmp_path / ".cursor" / "chat-transcripts" / "29767380-b541-41b6-a58a-639adea36baa.jsonl"
    assert _read_jsonl(out)[0]["prompt"] == prose


def test_audit_after_file_edit_drops_edit_bodies(tmp_path: Path) -> None:
    payload = json.loads((FIXTURES / "after_file_edit.json").read_text())
    _run_audit(tmp_path, payload)
    row = _read_jsonl(tmp_path / ".cursor" / "chat-transcripts" / "663268e0-f424-494a-a543-3de2743795b5.jsonl")[0]
    assert row["file_path"].endswith("foo.ts")
    assert "old_string" not in row["edits"][0]
    assert "new_string" not in row["edits"][0]

