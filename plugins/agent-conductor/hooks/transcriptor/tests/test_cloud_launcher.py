"""The cloud launcher stands in for plugin hook loading on a cloud VM."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from conftest import REPO_ROOT

LAUNCHER = REPO_ROOT / "cloud" / "agent-conductor-hook.sh"
CLOUD_HOOKS = REPO_ROOT / "cloud" / "hooks.json"
REAL_ID = "959870a8-e0be-40e6-96ca-9ef9226cff13"
AUDIT = "hooks/transcriptor/audit.sh"
TASK_HOOK = "hooks/context-injector/subagent-context-pre-tool-use.sh"


def _install_plugin(home: Path, cloud: bool = True, layout: str = "marketplace/id/sha") -> Path:
    root = home / ".cursor" / "plugins" / "cache"
    for part in layout.split("/"):
        root = root / part
    shutil.copytree(REPO_ROOT, root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    if cloud:
        manifest = home / ".cursor" / "plugins" / "cache" / ".cloud-plugin-manifest.json"
        manifest.write_text(
            json.dumps({"plugins": [{"name": "agent-conductor", "enabledCapabilities": ["static"]}]}),
            encoding="utf-8",
        )
    return root


def _run(target: str, payload: dict, project_root: Path, home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    return subprocess.run(
        ["bash", str(LAUNCHER), target],
        input=json.dumps(payload),
        cwd=str(project_root),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_launcher_captures_a_transcript_event(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _install_plugin(home)
    result = _run(
        AUDIT,
        {
            "conversation_id": REAL_ID,
            "hook_event_name": "beforeSubmitPrompt",
            "prompt": "captured through the launcher",
        },
        tmp_path,
        home,
    )
    assert result.returncode == 0
    log = tmp_path / ".cursor" / "chat-transcripts" / f"{REAL_ID}.jsonl"
    assert "captured through the launcher" in log.read_text(encoding="utf-8")


def test_launcher_syncs_the_cli_that_session_start_would_have(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _install_plugin(home)
    _run(AUDIT, {"conversation_id": REAL_ID, "hook_event_name": "stop"}, tmp_path, home)
    cli = tmp_path / ".cursor" / "chat-transcripts" / "_transcripts.py"
    assert cli.is_file()
    brief = subprocess.run(
        ["python3", str(cli), "brief", f"Advise. {REAL_ID}"],
        cwd=str(tmp_path),
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "CURSOR_PROJECT_DIR": str(tmp_path), "HOME": str(home)},
    )
    assert brief.returncode == 0
    assert "<brief" in brief.stdout


def test_launcher_replaces_a_stale_cli_with_a_fresh_timestamp(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _install_plugin(home)
    cli = tmp_path / ".cursor" / "chat-transcripts" / "_transcripts.py"
    cli.parent.mkdir(parents=True)
    cli.write_text("# committed before brief existed\n", encoding="utf-8")
    _run(AUDIT, {"conversation_id": REAL_ID, "hook_event_name": "stop"}, tmp_path, home)
    assert "brief" in cli.read_text(encoding="utf-8")


def test_launcher_forwards_the_task_stamp(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _install_plugin(home)
    result = _run(
        TASK_HOOK,
        {
            "tool_name": "Task",
            "conversation_id": REAL_ID,
            "hook_event_name": "preToolUse",
            "tool_input": {"subagent_type": "advisor", "prompt": "Advise."},
        },
        tmp_path,
        home,
    )
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["updated_input"]["prompt"] == f"Advise. {REAL_ID}"


def test_launcher_stays_silent_when_a_capture_hook_answers_nothing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _install_plugin(home)
    dump = Path("/tmp/cursor-hook-debug/error.log")
    before = dump.read_text(encoding="utf-8") if dump.is_file() else ""
    result = _run(
        AUDIT,
        {"conversation_id": REAL_ID, "hook_event_name": "afterAgentResponse", "text": "quiet"},
        tmp_path,
        home,
    )
    assert json.loads(result.stdout) == {}
    after = dump.read_text(encoding="utf-8") if dump.is_file() else ""
    assert "cloud launcher" not in after[len(before) :]


def test_launcher_finds_the_deeper_cache_layout(tmp_path: Path) -> None:
    # A project-side installer left this shape on a real VM, beside Cursor's own
    # install: cache/<marketplace>/<sha>/current/<name>/.
    home = tmp_path / "home"
    _install_plugin(home, layout="dev2o-plugins/sha/current/agent-conductor")
    result = _run(
        AUDIT,
        {
            "conversation_id": REAL_ID,
            "hook_event_name": "beforeSubmitPrompt",
            "prompt": "found the deeper layout",
        },
        tmp_path,
        home,
    )
    assert result.returncode == 0
    log = tmp_path / ".cursor" / "chat-transcripts" / f"{REAL_ID}.jsonl"
    assert "found the deeper layout" in log.read_text(encoding="utf-8")


def test_launcher_honors_a_working_tree_override(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _cloud_without_plugin(home)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CURSOR_PROJECT_DIR"] = str(tmp_path)
    env["AGENT_CONDUCTOR_PLUGIN_ROOT"] = str(REPO_ROOT)
    result = subprocess.run(
        ["bash", str(LAUNCHER), AUDIT],
        input=json.dumps(
            {
                "conversation_id": REAL_ID,
                "hook_event_name": "beforeSubmitPrompt",
                "prompt": "captured from the working tree",
            }
        ),
        cwd=str(tmp_path),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0
    log = tmp_path / ".cursor" / "chat-transcripts" / f"{REAL_ID}.jsonl"
    assert "captured from the working tree" in log.read_text(encoding="utf-8")


def test_launcher_dispatches_without_a_cloud_manifest(tmp_path: Path) -> None:
    # A cloud VM with no plugins installed writes no manifest, so its absence
    # cannot be used to decide whether to dispatch.
    home = tmp_path / "home"
    _install_plugin(home, cloud=False)
    result = _run(
        AUDIT,
        {"conversation_id": REAL_ID, "hook_event_name": "beforeSubmitPrompt", "prompt": "no manifest"},
        tmp_path,
        home,
    )
    assert result.returncode == 0
    log = tmp_path / ".cursor" / "chat-transcripts" / f"{REAL_ID}.jsonl"
    assert "no manifest" in log.read_text(encoding="utf-8")


def test_two_hook_sources_capture_one_line(tmp_path: Path) -> None:
    # The plugin's own hooks and a project launcher both deliver the same event
    # on desktop. The capture has to be idempotent rather than gated.
    home = tmp_path / "home"
    _install_plugin(home)
    payload = {
        "conversation_id": REAL_ID,
        "hook_event_name": "afterAgentResponse",
        "text": "said once",
    }
    _run(AUDIT, payload, tmp_path, home)
    _run(AUDIT, payload, tmp_path, home)
    log = tmp_path / ".cursor" / "chat-transcripts" / f"{REAL_ID}.jsonl"
    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1


def test_cloud_hooks_json_omits_the_orchestrator_inject() -> None:
    # beforeSubmitPrompt never fires in the cloud, and unlike a capture the
    # inject cannot dedupe itself, so registering it only risks a double inject.
    config = json.loads(CLOUD_HOOKS.read_text(encoding="utf-8"))
    targets = {
        entry["command"]
        for entries in config["hooks"].values()
        for entry in entries
    }
    assert not any("main-agent-orchestrator-inject" in t for t in targets)


def _cloud_without_plugin(home: Path) -> None:
    manifest = home / ".cursor" / "plugins" / "cache" / ".cloud-plugin-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"plugins": []}), encoding="utf-8")


def test_launcher_fails_open_without_an_installed_plugin(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _cloud_without_plugin(home)
    result = _run(
        AUDIT,
        {"conversation_id": REAL_ID, "hook_event_name": "preToolUse"},
        tmp_path,
        home,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"permission": "allow"}


def test_launcher_fails_open_on_an_unknown_event(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _cloud_without_plugin(home)
    result = _run(
        AUDIT,
        {"conversation_id": REAL_ID, "hook_event_name": "afterAgentResponse"},
        tmp_path,
        home,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_the_harness_config_targets_the_working_tree() -> None:
    # This repository is the plugin, and a cloud agent may have no plugin
    # installed at all, so its own harness has to dispatch to the checkout.
    harness = REPO_ROOT.parents[1] / ".cursor" / "hooks.json"
    config = json.loads(harness.read_text(encoding="utf-8"))
    commands = [entry["command"] for entries in config["hooks"].values() for entry in entries]
    assert commands
    for command in commands:
        assert command.startswith("AGENT_CONDUCTOR_PLUGIN_ROOT=plugins/agent-conductor "), command


def test_cloud_hooks_json_omits_session_start() -> None:
    config = json.loads(CLOUD_HOOKS.read_text(encoding="utf-8"))
    events = config["hooks"]
    assert "sessionStart" not in events
    targets = {
        entry["command"].split(" ", 1)[1]
        for entries in events.values()
        for entry in entries
    }
    for target in targets:
        assert (REPO_ROOT / target).is_file(), target
