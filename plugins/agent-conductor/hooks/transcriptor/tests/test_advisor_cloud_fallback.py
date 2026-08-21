"""The advisor must work when no plugin hook ever runs, as on cloud agents."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from conftest import REPO_ROOT, TRANSCRIPTS_PY

ADVISOR = REPO_ROOT / "agents" / "advisor.md"
AGENT_MAIN = REPO_ROOT / "hooks" / "context-injector" / "config" / "__agent-main.md"
REAL_ID = "959870a8-e0be-40e6-96ca-9ef9226cff13"
BLOCK_RE = re.compile(r"```bash\n(.*?)```", re.DOTALL)


def _fallback_command(agent_file: Path) -> str:
    """The <first_action> shell block, run as written rather than paraphrased."""
    match = BLOCK_RE.search(agent_file.read_text(encoding="utf-8"))
    assert match, f"{agent_file.name} has no first-action shell block"
    command = match.group(1)
    assert "find ~/.cursor/plugins/cache" in command, "lost the plugin-cache fallback"
    assert ".cursor/chat-transcripts/_transcripts.py" in command, "lost the project copy"
    return command


def _fake_plugin_install(home: Path) -> None:
    dest = (
        home / ".cursor" / "plugins" / "cache" / "m" / "sha" / "current" / "agent-conductor"
        / "hooks" / "transcriptor"
    )
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
    assert 'audience="senior"' in result.stdout
    assert "ship the fallback" in result.stdout


def test_fallback_skips_a_cached_copy_that_cannot_answer(tmp_path: Path) -> None:
    home = tmp_path / "home"
    stale = (
        home / ".cursor" / "plugins" / "cache" / "m" / "old-sha" / "current" / "agent-conductor"
        / "hooks" / "transcriptor"
    )
    stale.mkdir(parents=True)
    (stale / "transcripts.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
    _fake_plugin_install(home)
    command = _fallback_command(ADVISOR).replace(
        '"<your spawn line verbatim>"', f'"Advise. {REAL_ID}"'
    )
    result = _run(command, tmp_path, home)
    assert result.returncode == 0, result.stderr
    assert "<brief" in result.stdout


def test_main_agent_stamps_the_spawn_line_itself() -> None:
    text = AGENT_MAIN.read_text(encoding="utf-8")
    assert "CURSOR_CONVERSATION_ID" in text
    assert "Advise. <id>" in text
    assert "advisor-check" in text


def test_the_agent_description_carries_the_stamp_instruction() -> None:
    description = next(
        line
        for line in ADVISOR.read_text(encoding="utf-8").splitlines()
        if line.startswith("description:")
    )
    assert "advisor-check" in description
    assert "CURSOR_CONVERSATION_ID" in description
    assert "Advise." in description


def test_exe_advisor_agent_removed() -> None:
    assert not (REPO_ROOT / "agents" / "exe-advisor.md").exists()
