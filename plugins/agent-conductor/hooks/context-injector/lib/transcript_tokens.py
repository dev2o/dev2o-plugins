#!/usr/bin/env python3
"""Substitute transcript tokens in subagent context templates safely."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TOKEN_CONVERSATION_ID = "{{CONVERSATION_ID}}"
TOKEN_PROJECT_DIR = "{{PROJECT_DIR}}"
ID_UNAVAILABLE = "(conversation id unavailable)"
DUMP_LOG = "/tmp/cursor-hook-debug/error.log"


def log_error(msg: str) -> None:
    """Append non-fatal errors to the /tmp debug log without crashing."""
    try:
        os.makedirs("/tmp/cursor-hook-debug", exist_ok=True)
        with open(DUMP_LOG, "a", encoding="utf-8") as f:
            f.write(f"FAILED (transcript_tokens.py) - {msg}\n")
    except Exception:
        pass


def resolve_project_dir() -> str:
    """Absolute project root holding .cursor/chat-transcripts/.

    Wraps path resolution in try/except to prevent permission crashes
    in restricted container environments when cwd is inaccessible.
    """
    env = os.environ.get("CURSOR_PROJECT_DIR")
    if env:
        try:
            return str(Path(env).resolve())
        except Exception as e:
            log_error(f"Could not resolve CURSOR_PROJECT_DIR '{env}': {e}")
            return env

    try:
        return str(Path.cwd().resolve())
    except Exception as e:
        log_error(f"Could not resolve current working directory: {e}")
        return "/tmp"


def resolve_conversation_id(
    conversation_id: str,
    fallback_conversation_id: str = "",
    session_id: str = "",
) -> str:
    candidates = [c for c in (conversation_id, fallback_conversation_id, session_id) if c]
    if not candidates:
        return ID_UNAVAILABLE

    project_dir = resolve_project_dir()
    try:
        chat_dir = Path(project_dir) / ".cursor" / "chat-transcripts"
        for cid in candidates:
            # Prevent path traversal attacks if a malformed ID contains ../ or slashes
            safe_cid = os.path.basename(cid)
            if (chat_dir / f"{safe_cid}.jsonl").is_file():
                return safe_cid
    except Exception as e:
        log_error(f"Error checking chat-transcripts directory: {e}")

    # Fallback to the first non-empty candidate if files aren't found or accessible
    return os.path.basename(candidates[0]) if candidates else ID_UNAVAILABLE


def substitute_tokens(
    context: str,
    conversation_id: str,
    fallback_conversation_id: str = "",
    session_id: str = "",
) -> str:
    if TOKEN_PROJECT_DIR in context:
        context = context.replace(TOKEN_PROJECT_DIR, resolve_project_dir())
    if TOKEN_CONVERSATION_ID in context:
        resolved_id = resolve_conversation_id(
            conversation_id, fallback_conversation_id, session_id
        )
        context = context.replace(TOKEN_CONVERSATION_ID, resolved_id)
    return context


def main() -> int:
    try:
        context = sys.stdin.read()
    except Exception as e:
        log_error(f"Failed to read stdin: {e}")
        return 0

    conversation_id = ""
    fallback_conversation_id = ""
    session_id = ""
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--conversation-id" and i + 1 < len(args):
            conversation_id = args[i + 1]
            i += 2
            continue
        if args[i] == "--fallback-conversation-id" and i + 1 < len(args):
            fallback_conversation_id = args[i + 1]
            i += 2
            continue
        if args[i] == "--session-id" and i + 1 < len(args):
            session_id = args[i + 1]
            i += 2
            continue
        i += 1

    try:
        output = substitute_tokens(
            context, conversation_id, fallback_conversation_id, session_id
        )
        sys.stdout.write(output)
    except Exception as e:
        log_error(f"Token substitution failed: {e}")
        # Fail-open: write the unmodified context back out so the subagent doesn't freeze
        sys.stdout.write(context)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())