"""Tests for {{CONVERSATION_ID}} substitution in subagent context."""

from __future__ import annotations

import subprocess

from conftest import REPO_ROOT

REAL_ID = "959870a8-e0be-40e6-96ca-9ef9226cff13"


def _build_context(lookup: str, fallback: str = "") -> str:
    proc = subprocess.run(
        [
            "bash",
            "-c",
            f'source hooks/context-injector/lib/context.sh && build_subagent_context advisor "{lookup}" "{fallback}" ""',
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout


def test_conversation_id_substituted() -> None:
    out = _build_context(REAL_ID)
    assert REAL_ID in out
    assert "{{CONVERSATION_ID}}" not in out


def test_transcripts_cli_substituted() -> None:
    out = _build_context(REAL_ID)
    # Token must be replaced with the plugin's real, absolute CLI path.
    assert "{{TRANSCRIPTS_CLI}}" not in out
    expected = str(REPO_ROOT / "hooks" / "transcriptor" / "transcripts.py")
    assert expected in out


def test_project_dir_substituted() -> None:
    out = _build_context(REAL_ID)
    assert "{{PROJECT_DIR}}" not in out
    # Hook runs from REPO_ROOT with no CURSOR_PROJECT_DIR override in the
    # test env, so the token resolves to the working directory.
    assert f'CURSOR_PROJECT_DIR="{REPO_ROOT}"' in out or str(REPO_ROOT) in out
