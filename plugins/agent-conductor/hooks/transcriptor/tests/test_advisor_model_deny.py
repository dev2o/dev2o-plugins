"""Tests for advisor-model-deny.sh."""

from __future__ import annotations

import json
import subprocess

from conftest import REPO_ROOT

DENY_SH = REPO_ROOT / "hooks" / "context-injector" / "advisor-model-deny.sh"

DENY_SNIPPET = "You must select a opus high thinking model or grok"


def _run(payload: dict) -> dict:
    result = subprocess.run(
        [str(DENY_SH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {"permission": "allow"}


def _exe_advisor_task(**kwargs) -> dict:
    tool_input = {
        "description": "Advise",
        "prompt": "CID:959870a8-e0be-40e6-96ca-9ef9226cff13",
        "subagent_type": "exe-advisor",
    }
    tool_input.update(kwargs.pop("tool_input", {}))
    payload = {"tool_name": "Task", "tool_input": tool_input, "model": ""}
    payload.update(kwargs)
    payload["tool_input"] = tool_input
    return payload


def test_deny_empty_top_level_model() -> None:
    out = _run(_exe_advisor_task())
    assert out["permission"] == "deny"
    assert DENY_SNIPPET in out["agent_message"]
    assert DENY_SNIPPET in out["user_message"]


def test_deny_omitted_model() -> None:
    out = _run(
        {
            "tool_name": "Task",
            "tool_input": {
                "description": "Advise",
                "prompt": "CID:959870a8-e0be-40e6-96ca-9ef9226cff13",
                "subagent_type": "exe-advisor",
            },
        }
    )
    assert out["permission"] == "deny"


def test_deny_inherit() -> None:
    out = _run(_exe_advisor_task(tool_input={"model": "inherit"}))
    assert out["permission"] == "deny"


def test_allow_opus_in_tool_input() -> None:
    out = _run(_exe_advisor_task(tool_input={"model": "claude-opus-5-thinking-high"}))
    assert out["permission"] == "allow"


def test_allow_grok_in_tool_input() -> None:
    out = _run(_exe_advisor_task(tool_input={"model": "cursor-grok-4.6-xhigh-fast"}))
    assert out["permission"] == "allow"


def test_deny_parent_model_does_not_count() -> None:
    out = _run(_exe_advisor_task(model="claude-4.6-opus-high-thinking"))
    assert out["permission"] == "deny"


def test_allow_gatekeeper_advisor_without_model() -> None:
    out = _run(
        {
            "tool_name": "Task",
            "model": "",
            "tool_input": {
                "description": "Advise",
                "prompt": "Advise.",
                "subagent_type": "advisor",
            },
        }
    )
    assert out["permission"] == "allow"


def test_allow_non_advisor_task() -> None:
    out = _run(
        {
            "tool_name": "Task",
            "model": "",
            "tool_input": {"subagent_type": "explore", "prompt": "look around"},
        }
    )
    assert out["permission"] == "allow"


def test_allow_non_task() -> None:
    out = _run({"tool_name": "Grep", "model": "", "tool_input": {}})
    assert out["permission"] == "allow"
