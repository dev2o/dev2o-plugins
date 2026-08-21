from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import FIXTURES, HOOKS_TRANSCRIPTS, REPO_ROOT, TRANSCRIPTS_PY

sys.path.insert(0, str(HOOKS_TRANSCRIPTS))
from transcripts import cursor_project_slug, parse_ref, parse_spawn_token, TokenError

REAL_ID = "959870a8-e0be-40e6-96ca-9ef9226cff13"
GATEKEEPER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
MISSING_ID = "00000000-0000-0000-0000-000000000000"
HOOK = REPO_ROOT / "hooks" / "context-injector" / "subagent-context-pre-tool-use.sh"
CONTEXT_SH = REPO_ROOT / "hooks" / "context-injector" / "lib" / "context.sh"
POISON = "POISON_ADVISOR_TRANSPORT_MARKER_7f3a"


def _write_poison(project_root: Path, cid: str = REAL_ID) -> None:
    log_dir = project_root / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True, exist_ok=True)
    src = (FIXTURES / "poison_transcript.jsonl").read_text(encoding="utf-8")
    (log_dir / f"{cid}.jsonl").write_text(src, encoding="utf-8")


def _write_session(root: Path, cid: str, events: list[dict]) -> None:
    log_dir = root / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / f"{cid}.jsonl").open("w", encoding="utf-8") as f:
        for ev in events:
            ev.setdefault("conversation_id", cid)
            ev.setdefault("ts", "2026-07-21T12:00:00Z")
            f.write(json.dumps(ev) + "\n")


def _hook_raw(project_root: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )


def _hook(project_root: Path, payload: dict) -> dict:
    proc = _hook_raw(project_root, payload)
    return json.loads(proc.stdout)


def _cli(project_root: Path, *args: str, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(TRANSCRIPTS_PY), *args],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_hook_advisor_prompt_is_the_token_only(tmp_path: Path) -> None:
    _write_poison(tmp_path, REAL_ID)
    proc = _hook_raw(
        tmp_path,
        {
            "tool_name": "Task",
            "conversation_id": REAL_ID,
            "tool_input": {"subagent_type": "advisor", "prompt": "Advise."},
        },
    )
    out = json.loads(proc.stdout)
    prompt = out["updated_input"]["prompt"]
    assert prompt == f"Advise. {REAL_ID}"
    assert len(prompt) < 80
    assert POISON not in proc.stdout
    assert POISON not in proc.stderr
    assert POISON not in json.dumps(out)


def test_hook_advisor_stamp_is_idempotent(tmp_path: Path) -> None:
    out = _hook(
        tmp_path,
        {
            "tool_name": "Task",
            "conversation_id": REAL_ID,
            "tool_input": {
                "subagent_type": "advisor",
                "prompt": f"Advise. {REAL_ID}",
            },
        },
    )
    assert out["updated_input"]["prompt"] == f"Advise. {REAL_ID}"


def test_hook_advisor_mismatched_id_denied(tmp_path: Path) -> None:
    _write_poison(tmp_path, REAL_ID)
    proc = _hook_raw(
        tmp_path,
        {
            "tool_name": "Task",
            "conversation_id": REAL_ID,
            "tool_input": {"subagent_type": "advisor", "prompt": "Advise. other-id"},
        },
    )
    out = json.loads(proc.stdout)
    assert out["permission"] == "deny"
    assert "updated_input" not in out
    # The deny has to tell the Executor to restamp. Telling it to send a bare
    # "Advise." would walk it back into the unstamped, blind case.
    assert "CURSOR_CONVERSATION_ID" in out["agent_message"]
    assert POISON not in proc.stdout
    assert POISON not in json.dumps(out)


def test_hook_leaves_exe_advisor_prompt_alone(tmp_path: Path) -> None:
    _write_poison(tmp_path, REAL_ID)
    out = _hook(
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
    assert out == {"permission": "allow"}


def test_hook_path_does_not_read_logs() -> None:
    hook = HOOK.read_text(encoding="utf-8")
    lib = CONTEXT_SH.read_text(encoding="utf-8")
    for src in (hook, lib):
        assert "transcripts.py" not in src
        assert ".jsonl" not in src
        assert " show " not in src


def test_brief_triage_hands_back_the_senior_token(tmp_path: Path) -> None:
    events = [
        {"hook_event_name": "beforeSubmitPrompt", "prompt": "add a --json flag"}
    ]
    for i in range(12):
        events.append(
            {
                "hook_event_name": "beforeSubmitPrompt",
                "prompt": f"turn {i}",
            }
        )
    events.append(
        {
            "hook_event_name": "preToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "hooks/transcriptor/transcripts.py"},
        }
    )
    _write_session(tmp_path, REAL_ID, events)
    result = _cli(tmp_path, "brief", f"Advise. {REAL_ID}")
    assert result.returncode == 0
    assert result.stdout.count(f"CID:{REAL_ID}") == 1
    assert f"<escalate>CID:{REAL_ID}</escalate>" in result.stdout
    assert 'audience="triage"' in result.stdout
    assert "turn 0" not in result.stdout
    assert "turn 11" in result.stdout
    assert "add a --json flag" in result.stdout


def test_brief_senior_never_offers_escalation(tmp_path: Path) -> None:
    _write_session(
        tmp_path,
        REAL_ID,
        [{"hook_event_name": "beforeSubmitPrompt", "prompt": "ship the transport"}],
    )
    result = _cli(tmp_path, "brief", f"CID:{REAL_ID}")
    assert result.returncode == 0
    assert "<escalate>" not in result.stdout
    assert 'audience="senior"' in result.stdout
    assert "ship the transport" in result.stdout


def test_brief_missing_log_exits_0(tmp_path: Path) -> None:
    result = _cli(tmp_path, "brief", f"Advise. {MISSING_ID}")
    assert result.returncode == 0
    assert "<no_transcript" in result.stdout
    assert 'reason="not-found"' in result.stdout
    assert "plugin-capture" in result.stdout
    assert "cursor-agent-transcripts" in result.stdout
    assert "cloud-dash" in result.stdout


def test_brief_malformed_token_exits_2(tmp_path: Path) -> None:
    result = _cli(tmp_path, "brief", "please advise me")
    assert result.returncode == 2
    assert "Advise. <executor_id>" in result.stderr
    assert "CID:<executor_id>" in result.stderr


def test_brief_reads_workspace_agent_transcripts(tmp_path: Path) -> None:
    home = tmp_path / "home"
    slug = cursor_project_slug(tmp_path)
    log = home / ".cursor" / "projects" / slug / "agent-transcripts" / REAL_ID / f"{REAL_ID}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        json.dumps(
            {
                "role": "user",
                "message": {
                    "content": [{"type": "text", "text": "workspace agent transcript body"}]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    decoy = (
        home
        / ".cursor"
        / "projects"
        / "other-workspace"
        / "agent-transcripts"
        / REAL_ID
        / f"{REAL_ID}.jsonl"
    )
    decoy.parent.mkdir(parents=True, exist_ok=True)
    decoy.write_text(
        json.dumps(
            {
                "role": "user",
                "message": {"content": [{"type": "text", "text": "DECOY_OTHER_WORKSPACE"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = _cli(tmp_path, "brief", f"Advise. {REAL_ID}", home=home)
    assert result.returncode == 0
    assert "workspace agent transcript body" in result.stdout
    assert "DECOY_OTHER_WORKSPACE" not in result.stdout
    assert 'source="cursor-agent-transcripts"' in result.stdout


def test_brief_plugin_wins_over_agent_transcripts(tmp_path: Path) -> None:
    _write_session(
        tmp_path,
        REAL_ID,
        [{"hook_event_name": "beforeSubmitPrompt", "prompt": "plugin jsonl wins"}],
    )
    home = tmp_path / "home"
    slug = cursor_project_slug(tmp_path)
    log = home / ".cursor" / "projects" / slug / "agent-transcripts" / REAL_ID / f"{REAL_ID}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        json.dumps(
            {
                "role": "user",
                "message": {"content": [{"type": "text", "text": "should not appear"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = _cli(tmp_path, "brief", f"Advise. {REAL_ID}", home=home)
    assert result.returncode == 0
    assert "plugin jsonl wins" in result.stdout
    assert "should not appear" not in result.stdout
    assert 'source="plugin-capture"' in result.stdout


def test_parse_ref_rejects_traversal() -> None:
    assert parse_ref("") is None
    assert parse_ref("../evil") is None
    assert parse_ref("foo/bar") is None
    assert parse_ref("please advise me") is None
    assert parse_ref(REAL_ID) is not None
    err = parse_spawn_token("please advise me")
    assert isinstance(err, TokenError)
