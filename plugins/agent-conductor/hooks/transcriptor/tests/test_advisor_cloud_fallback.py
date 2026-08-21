"""The advisor pair must work when no plugin hook ever runs, as on cloud agents."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from conftest import REPO_ROOT, TRANSCRIPTS_PY

ADVISOR = REPO_ROOT / "agents" / "advisor.md"
EXE_ADVISOR = REPO_ROOT / "agents" / "exe-advisor.md"
AGENT_MAIN = REPO_ROOT / "hooks" / "context-injector" / "config" / "__agent-main.md"
REAL_ID = "959870a8-e0be-40e6-96ca-9ef9226cff13"
FALLBACK_RE = re.compile(r"^python3 \"\$\(ls .*transcripts\.py.*\)\" brief .*$", re.MULTILINE)


def _fallback_command(agent_file: Path) -> str:
    match = FALLBACK_RE.search(agent_file.read_text(encoding="utf-8"))
    assert match, f"{agent_file.name} lost its plugin-cache CLI fallback"
    return match.group(0)


def _fake_plugin_install(home: Path) -> None:
    dest = home / ".cursor" / "plugins" / "cache" / "m" / "1" / "sha" / "hooks" / "transcriptor"
    dest.mkdir(parents=True)
    shutil.copy(TRANSCRIPTS_PY, dest / "transcripts.py")


def _run(command: str, project_root: Path, home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    return subprocess.run(
        ["bash", "-c", command],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_advisor_fallback_command_runs_brief_from_the_plugin_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _fake_plugin_install(home)
    log_dir = tmp_path / ".cursor" / "chat-transcripts"
    log_dir.mkdir(parents=True)
    (log_dir / f"{REAL_ID}.jsonl").write_text(
        json.dumps({"hook_event_name": "beforeSubmitPrompt", "prompt": "ship the fallback"}) + "\n",
        encoding="utf-8",
    )
    command = _fallback_command(ADVISOR).replace(
        '"<your spawn line verbatim>"', f'"Advise. {REAL_ID}"'
    )
    result = _run(command, tmp_path, home)
    assert result.returncode == 0, result.stderr
    assert 'audience="triage"' in result.stdout
    assert "ship the fallback" in result.stdout


def test_exe_advisor_fallback_command_runs_brief_from_the_plugin_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _fake_plugin_install(home)
    command = _fallback_command(EXE_ADVISOR).replace(
        '"<your spawn line verbatim>"', f'"CID:{REAL_ID}"'
    )
    result = _run(command, tmp_path, home)
    assert result.returncode == 0, result.stderr
    assert 'audience="senior"' in result.stdout
    assert "<no_transcript" in result.stdout


def test_executor_stamps_the_spawn_line_itself() -> None:
    text = AGENT_MAIN.read_text(encoding="utf-8")
    assert "CURSOR_CONVERSATION_ID" in text
    assert "Advise. <id>" in text


def test_the_agent_description_carries_the_stamp_instruction() -> None:
    # __agent-main.md rides beforeSubmitPrompt, which cloud agents never fire.
    # The description is the only copy of this instruction a cloud Executor reads.
    description = next(
        line
        for line in ADVISOR.read_text(encoding="utf-8").splitlines()
        if line.startswith("description:")
    )
    assert "CURSOR_CONVERSATION_ID" in description
    assert "Advise. <your own conversation id" in description
