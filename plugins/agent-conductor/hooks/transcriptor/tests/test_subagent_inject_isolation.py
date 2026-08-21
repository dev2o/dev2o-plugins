"""A subagent must never receive the orchestrator context.

On a cloud VM a Task child is indistinguishable from a main agent in the hook
payload, so identity comes from the spawn registry rather than the payload.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from conftest import REPO_ROOT

INJECT = REPO_ROOT / "hooks" / "context-injector" / "main-agent-orchestrator-inject.sh"
SPAWN = REPO_ROOT / "hooks" / "context-injector" / "subagent-context-pre-tool-use.sh"


def _env(registry: Path, project_root: Path) -> dict:
    env = os.environ.copy()
    env["CURSOR_HOOK_REGISTRY_DIR"] = str(registry)
    env["CURSOR_PROJECT_DIR"] = str(project_root)
    return env


def _spawn(registry: Path, project_root: Path, subagent_type: str, prompt: str) -> dict:
    result = subprocess.run(
        ["bash", str(SPAWN)],
        input=json.dumps(
            {
                "tool_name": "Task",
                "conversation_id": str(uuid.uuid4()),
                "tool_input": {"subagent_type": subagent_type, "prompt": prompt},
            }
        ),
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=_env(registry, project_root),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _submit(registry: Path, project_root: Path, conversation_id: str, prompt: str) -> dict:
    result = subprocess.run(
        ["bash", str(INJECT)],
        input=json.dumps(
            {
                "conversation_id": conversation_id,
                "generation_id": str(uuid.uuid4()),
                "hook_event_name": "beforeSubmitPrompt",
                "composer_mode": "agent",
                "prompt": prompt,
            }
        ),
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=_env(registry, project_root),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_main_agent_receives_the_orchestrator_context(tmp_path: Path) -> None:
    out = _submit(tmp_path / "reg", tmp_path, str(uuid.uuid4()), "please fix the pricing flow")
    assert "delegation_protocol" in out["additional_context"]


def test_a_spawned_subagent_does_not(tmp_path: Path) -> None:
    registry = tmp_path / "reg"
    prompt = "look at the pricing flow and report"
    _spawn(registry, tmp_path, "explore", prompt)
    out = _submit(registry, tmp_path, str(uuid.uuid4()), prompt)
    assert "additional_context" not in out


def test_a_subagent_stays_known_on_later_turns(tmp_path: Path) -> None:
    registry = tmp_path / "reg"
    prompt = "look at the pricing flow and report"
    child = str(uuid.uuid4())
    _spawn(registry, tmp_path, "explore", prompt)
    _submit(registry, tmp_path, child, prompt)
    # A resume carries different text; the child is known by id by now.
    out = _submit(registry, tmp_path, child, "now check the MSRP column detection")
    assert "additional_context" not in out


def test_the_advisor_child_does_not_get_it_either(tmp_path: Path) -> None:
    registry = tmp_path / "reg"
    parent = "959870a8-e0be-40e6-96ca-9ef9226cff13"
    result = subprocess.run(
        ["bash", str(SPAWN)],
        input=json.dumps(
            {
                "tool_name": "Task",
                "conversation_id": parent,
                "tool_input": {"subagent_type": "advisor", "prompt": "Advise."},
            }
        ),
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=_env(registry, tmp_path),
    )
    stamped = json.loads(result.stdout)["updated_input"]["prompt"]
    assert stamped == f"Advise. {parent}"
    out = _submit(registry, tmp_path, str(uuid.uuid4()), stamped)
    assert "additional_context" not in out


def test_the_parent_keeps_getting_it_after_spawning(tmp_path: Path) -> None:
    registry = tmp_path / "reg"
    parent = str(uuid.uuid4())
    _submit(registry, tmp_path, parent, "fix the pricing flow")
    _spawn(registry, tmp_path, "explore", "go read the flow")
    out = _submit(registry, tmp_path, parent, "that did not work, try again")
    assert "delegation_protocol" in out["additional_context"]
