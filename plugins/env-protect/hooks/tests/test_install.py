"""install.sh: project copy, hooks.json merge, and the cloud invocation path."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import ENV_PROTECT_SH, INSTALL_SH, REAL_HOOKS_JSON

ENTRY_CMD = ".cursor/hooks/env-protect.sh"


def _install(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALL_SH), *args],
        text=True,
        capture_output=True,
        check=False,
        cwd=cwd,
    )


def _parse_check(stdout: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if ": " in line and line.split(":", 1)[0] in {
            "project",
            "plugin_root",
            "script",
            "script_matches",
            "hooks_json",
            "hooks_json_valid",
            "entry_present",
            "script_gitignored",
            "hooks_json_gitignored",
            "status",
        }:
            key, value = line.split(": ", 1)
            out[key] = value
    return out


def test_check_empty_project_writes_nothing(tmp_path: Path) -> None:
    result = _install("--check", str(tmp_path))
    assert result.returncode == 0, result.stderr
    fields = _parse_check(result.stdout)
    assert fields["status"] == "not-installed"
    assert fields["script"] == "missing"
    assert fields["hooks_json"] == "missing"
    assert fields["entry_present"] == "no"
    assert not (tmp_path / ".cursor").exists()
    assert "would copy: .cursor/hooks/env-protect.sh" in result.stdout
    assert "would create: .cursor/hooks.json" in result.stdout


def test_install_creates_hooks_json_and_script(tmp_path: Path) -> None:
    result = _install(str(tmp_path))
    assert result.returncode == 0, result.stderr
    dest = tmp_path / ".cursor" / "hooks" / "env-protect.sh"
    hooks = tmp_path / ".cursor" / "hooks.json"
    assert dest.is_file()
    assert dest.read_bytes() == ENV_PROTECT_SH.read_bytes()
    assert dest.stat().st_mode & stat.S_IXUSR
    data = json.loads(hooks.read_text())
    assert data == {
        "version": 1,
        "hooks": {
            "beforeShellExecution": [
                {"command": ENTRY_CMD, "timeout": 30},
            ]
        },
    }
    assert "copied: yes" in result.stdout
    assert "hooks.json: created" in result.stdout


def test_merge_preserves_this_repo_hooks_json(tmp_path: Path) -> None:
    orig = json.loads(REAL_HOOKS_JSON.read_text())
    dest_json = tmp_path / ".cursor" / "hooks.json"
    dest_json.parent.mkdir(parents=True)
    dest_json.write_text(REAL_HOOKS_JSON.read_text())

    result = _install(str(tmp_path))
    assert result.returncode == 0, result.stderr
    after = json.loads(dest_json.read_text())

    assert after["version"] == orig["version"]
    assert set(after["hooks"]) == set(orig["hooks"])
    assert orig["hooks"], "expected this repo's hooks.json to have events"
    for event, entries in orig["hooks"].items():
        if event == "beforeShellExecution":
            assert after["hooks"][event][: len(entries)] == entries
            assert len(after["hooks"][event]) == len(entries) + 1
            assert after["hooks"][event][-1] == {"command": ENTRY_CMD, "timeout": 30}
        else:
            assert after["hooks"][event] == entries
    assert sum(1 for e in after["hooks"]["beforeShellExecution"] if str(e.get("command", "")).endswith("env-protect.sh")) == 1
    assert "hooks.json: updated" in result.stdout


def test_idempotent_second_run(tmp_path: Path) -> None:
    first = _install(str(tmp_path))
    assert first.returncode == 0, first.stderr
    dest = tmp_path / ".cursor" / "hooks" / "env-protect.sh"
    hooks = tmp_path / ".cursor" / "hooks.json"
    dest_before = dest.read_bytes()
    hooks_before = hooks.read_bytes()

    second = _install(str(tmp_path))
    assert second.returncode == 0, second.stderr
    assert dest.read_bytes() == dest_before
    assert hooks.read_bytes() == hooks_before
    assert "copied: no" in second.stdout
    assert "hooks.json: unchanged" in second.stdout


def test_invalid_json_exits_without_touching(tmp_path: Path) -> None:
    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text("{not json")
    before = hooks.read_bytes()

    result = _install(str(tmp_path))
    assert result.returncode == 1
    assert "invalid JSON" in result.stderr
    assert hooks.read_bytes() == before
    assert not (tmp_path / ".cursor" / "hooks" / "env-protect.sh").exists()


def test_stale_project_copy_is_resynced(tmp_path: Path) -> None:
    first = _install(str(tmp_path))
    assert first.returncode == 0, first.stderr
    dest = tmp_path / ".cursor" / "hooks" / "env-protect.sh"
    dest.write_text("junk\n")

    result = _install(str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert dest.read_bytes() == ENV_PROTECT_SH.read_bytes()
    assert "copied: yes" in result.stdout
    assert "hooks.json: unchanged" in result.stdout


def test_check_after_install_reports_installed(tmp_path: Path) -> None:
    installed = _install(str(tmp_path))
    assert installed.returncode == 0, installed.stderr
    result = _install("--check", str(tmp_path))
    assert result.returncode == 0, result.stderr
    fields = _parse_check(result.stdout)
    assert fields["status"] == "installed"
    assert fields["script"] == "present"
    assert fields["script_matches"] == "yes"
    assert fields["entry_present"] == "yes"
    assert "nothing to write" in result.stdout


def test_cloud_path_runs_relative_project_copy(tmp_path: Path) -> None:
    result = _install(str(tmp_path))
    assert result.returncode == 0, result.stderr
    data = json.loads((tmp_path / ".cursor" / "hooks.json").read_text())
    command = data["hooks"]["beforeShellExecution"][-1]["command"]
    assert command == ENTRY_CMD

    ran = subprocess.run(
        ["bash", command],
        input='{"command":"env | grep KEY"}',
        text=True,
        capture_output=True,
        check=True,
        cwd=tmp_path,
        env={k: v for k, v in os.environ.items() if k != "CURSOR_PLUGIN_ROOT"},
    )
    out = json.loads(ran.stdout)
    assert out["permission"] == "deny"


def test_check_reports_stale_when_script_differs(tmp_path: Path) -> None:
    installed = _install(str(tmp_path))
    assert installed.returncode == 0, installed.stderr
    (tmp_path / ".cursor" / "hooks" / "env-protect.sh").write_text("junk\n")
    result = _install("--check", str(tmp_path))
    assert result.returncode == 0, result.stderr
    fields = _parse_check(result.stdout)
    assert fields["status"] == "stale"
    assert fields["script_matches"] == "no"
    assert "would copy: .cursor/hooks/env-protect.sh" in result.stdout


def test_defaults_to_cursor_project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_PROJECT_DIR", str(tmp_path))
    decoy = tmp_path / "decoy-cwd"
    decoy.mkdir()
    result = _install(cwd=decoy)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".cursor" / "hooks" / "env-protect.sh").is_file()
    assert not (decoy / ".cursor").exists()
