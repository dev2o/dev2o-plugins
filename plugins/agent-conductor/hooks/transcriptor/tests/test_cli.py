"""Tests for transcripts.py CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURES, REPO_ROOT, TRANSCRIPTS_PY


@pytest.fixture
def transcript_dir(tmp_path: Path) -> Path:
    log_dir = tmp_path / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True)

    ids = [
        ("663268e0-f424-494a-a543-3de2743795b5", "before_submit_email.json"),
        ("bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de", "before_submit_null.json"),
        ("bc-88d22cdb-dbc1-4627-996d-5f82ac03e6f7", "before_submit_null.json"),
    ]
    scrub_jq = FIXTURES.parents[1] / "scrub.jq"
    for cid, fixture_name in ids:
        raw = json.loads((FIXTURES / fixture_name).read_text())
        raw["conversation_id"] = cid
        proc = subprocess.run(
            ["jq", "-c", "--arg", "ts", "2026-07-21T12:00:00Z", "-f", str(scrub_jq)],
            input=json.dumps(raw),
            text=True,
            capture_output=True,
            check=True,
        )
        line = proc.stdout.strip()
        (log_dir / f"{cid}.jsonl").write_text(line + "\n", encoding="utf-8")
        if cid == "bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de":
            assistant = {
                "conversation_id": cid,
                "hook_event_name": "afterAgentResponse",
                "model": "composer-2.5",
                "text": "All good.\n\n| Check | Result |",
                "ts": "2026-07-21T12:11:12Z",
            }
            with (log_dir / f"{cid}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(assistant) + "\n")

    garbage_path = log_dir / "bc-88d22cdb-dbc1-4627-996d-5f82ac03e6f7.jsonl"
    garbage_path.write_text(
        garbage_path.read_text(encoding="utf-8") + "not valid json\n",
        encoding="utf-8",
    )
    return tmp_path


def _cli(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    import os

    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    return subprocess.run(
        [sys.executable, str(TRANSCRIPTS_PY), *args],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_list_shows_transcripts(transcript_dir: Path) -> None:
    result = _cli(transcript_dir, "list", "--all")
    assert result.returncode == 0
    for cid in (
        "663268e0-f424-494a-a543-3de2743795b5",
        "bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de",
        "bc-88d22cdb-dbc1-4627-996d-5f82ac03e6f7",
    ):
        assert cid in result.stdout


def test_list_limit(transcript_dir: Path) -> None:
    result = _cli(transcript_dir, "list", "-n", "1")
    assert result.returncode == 0
    assert result.stdout.count(".jsonl") + result.stdout.count("663268") <= 2


def test_show_includes_prompt_and_response(transcript_dir: Path) -> None:
    result = _cli(
        transcript_dir,
        "show",
        "bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de",
    )
    assert result.returncode == 0
    assert "read write test" in result.stdout
    assert "All good" in result.stdout


def test_show_only_user(transcript_dir: Path) -> None:
    result = _cli(
        transcript_dir,
        "show",
        "bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de",
        "--only",
        "user",
    )
    assert result.returncode == 0
    assert "read write test" in result.stdout
    assert "All good" not in result.stdout


def test_show_json(transcript_dir: Path) -> None:
    result = _cli(
        transcript_dir,
        "show",
        "bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de",
        "--json",
    )
    assert result.returncode == 0
    for line in result.stdout.strip().splitlines():
        json.loads(line)


def test_show_unknown_id_exits_1(transcript_dir: Path) -> None:
    result = _cli(transcript_dir, "show", "does-not-exist")
    assert result.returncode == 1
    assert result.stderr


def test_search_finds_term(transcript_dir: Path) -> None:
    result = _cli(transcript_dir, "search", "read write test")
    assert result.returncode == 0
    assert "bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de" in result.stdout


def test_search_skips_garbage_line(transcript_dir: Path) -> None:
    result = _cli(transcript_dir, "search", "read write test", "-n", "20")
    assert result.returncode == 0


def _write_session(root: Path, cid: str, events: list[dict]) -> None:
    log_dir = root / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / f"{cid}.jsonl").open("w", encoding="utf-8") as f:
        for ev in events:
            ev.setdefault("conversation_id", cid)
            ev.setdefault("ts", "2026-07-21T12:00:00Z")
            f.write(json.dumps(ev) + "\n")


def _prompt(text: str) -> dict:
    return {"hook_event_name": "beforeSubmitPrompt", "prompt": text}


def _shell(command: str) -> dict:
    return {
        "hook_event_name": "preToolUse",
        "tool_name": "Shell",
        "tool_input": {"command": command},
    }


def test_list_snippet_prefers_commit_message(tmp_path: Path) -> None:
    _write_session(
        tmp_path,
        "sess-commit",
        [_prompt("please fix the parser bug"), _shell('git commit -m "Fix parser"')],
    )
    result = _cli(tmp_path, "list")
    assert result.returncode == 0
    assert "Fix parser" in result.stdout
    assert "please fix the parser bug" not in result.stdout


def test_list_snippet_pr_title_wins_over_commit(tmp_path: Path) -> None:
    _write_session(
        tmp_path,
        "sess-pr",
        [
            _prompt("build the cli"),
            _shell('git commit -m "Fix parser"'),
            _shell('gh pr create --title "Add CLI" --body "stuff"'),
        ],
    )
    result = _cli(tmp_path, "list")
    assert result.returncode == 0
    assert "Add CLI" in result.stdout
    assert "Fix parser" not in result.stdout


def test_list_snippet_commit_heredoc(tmp_path: Path) -> None:
    cmd = 'git commit -m "$(cat <<\'EOF\'\nFix heredoc parsing\n\nMore details here.\nEOF\n)"'
    _write_session(tmp_path, "sess-heredoc", [_prompt("hello"), _shell(cmd)])
    result = _cli(tmp_path, "list")
    assert result.returncode == 0
    assert "Fix heredoc parsing" in result.stdout


def test_list_multiline_prompt_single_line(tmp_path: Path) -> None:
    _write_session(
        tmp_path,
        "sess-multiline",
        [_prompt("line one\nline two\nline three")],
    )
    result = _cli(tmp_path, "list")
    assert result.returncode == 0
    lines = [l for l in result.stdout.splitlines() if "sess-multiline" in l]
    assert len(lines) == 1
    assert "line one line two line three" in lines[0]


def test_list_has_header_and_no_model(transcript_dir: Path) -> None:
    result = _cli(transcript_dir, "list", "--all")
    assert result.returncode == 0
    header = result.stdout.splitlines()[0]
    assert "CONVERSATION_ID" in header
    assert "SUMMARY" in header
    assert "MODEL" not in header
    assert "composer-2.5" not in result.stdout


def test_no_args_prints_guide(transcript_dir: Path) -> None:
    result = _cli(transcript_dir)
    assert result.returncode == 0
    assert "CONVERSATION_ID" in result.stdout
    assert "Usage:" in result.stdout
    assert "search" in result.stdout
    assert "composer-2.5" not in result.stdout


def test_show_footer_hint(transcript_dir: Path) -> None:
    result = _cli(
        transcript_dir,
        "show",
        "bc-d15b22ad-3ef4-44fe-b0e4-213894ba53de",
        "--only",
        "user",
    )
    assert result.returncode == 0
    assert "events 1-1 of 1 (1 filtered by --only)" in result.stdout
    assert "--only" in result.stdout


def test_show_paginates_and_hints(tmp_path: Path) -> None:
    events = [_prompt(f"prompt number {i}") for i in range(30)]
    _write_session(tmp_path, "sess-long", events)
    result = _cli(tmp_path, "show", "sess-long")
    assert result.returncode == 0
    assert "prompt number 19" in result.stdout
    assert "prompt number 20" not in result.stdout
    assert "events 1-20 of 30" in result.stdout
    assert "--offset 20" in result.stdout
    assert "--full" in result.stdout

    page2 = _cli(tmp_path, "show", "sess-long", "--offset", "20")
    assert "prompt number 20" in page2.stdout
    assert "events 21-30 of 30" in page2.stdout


def test_show_negative_offset_tails(tmp_path: Path) -> None:
    events = [_prompt(f"prompt number {i}") for i in range(30)]
    _write_session(tmp_path, "sess-tail", events)
    result = _cli(tmp_path, "show", "sess-tail", "--offset", "-5")
    assert result.returncode == 0
    assert "prompt number 25" in result.stdout
    assert "prompt number 24" not in result.stdout
    assert "events 26-30 of 30" in result.stdout


def test_show_truncates_by_default_full_expands(tmp_path: Path) -> None:
    long_prompt = "x" * 500
    _write_session(tmp_path, "sess-big", [_prompt(long_prompt)])
    default = _cli(tmp_path, "show", "sess-big")
    assert long_prompt not in default.stdout
    assert "..." in default.stdout
    full = _cli(tmp_path, "show", "sess-big", "--full")
    assert long_prompt in full.stdout


def test_search_no_match_hint(transcript_dir: Path) -> None:
    result = _cli(transcript_dir, "search", "zzz-no-such-term-zzz")
    assert result.returncode == 0
    assert "No matches" in result.stdout
