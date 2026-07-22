"""Shared paths for transcriptor tests."""

from __future__ import annotations

from pathlib import Path

HOOKS_TRANSCRIPTS = Path(__file__).resolve().parents[1]
REPO_ROOT = HOOKS_TRANSCRIPTS.parents[1]
AUDIT_SH = HOOKS_TRANSCRIPTS / "audit.sh"
SCRUB_JQ = HOOKS_TRANSCRIPTS / "scrub.jq"
TRANSCRIPTS_PY = HOOKS_TRANSCRIPTS / "transcripts.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
