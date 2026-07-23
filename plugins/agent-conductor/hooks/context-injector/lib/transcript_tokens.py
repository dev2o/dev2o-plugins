#!/usr/bin/env python3
"""Substitute transcript tokens in subagent context templates."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TOKEN_CONVERSATION_ID = "{{CONVERSATION_ID}}"
TOKEN_PROJECT_DIR = "{{PROJECT_DIR}}"
ID_UNAVAILABLE = "(conversation id unavailable)"


def resolve_project_dir() -> str:
    """Absolute project root holding .cursor/chat-transcripts/.

    Hooks run with CURSOR_PROJECT_DIR set; fall back to the working directory
    (never to the plugin cache — transcripts are project-scoped data).
    """
    env = os.environ.get("CURSOR_PROJECT_DIR")
    if env:
        return str(Path(env).resolve())
    return str(Path.cwd().resolve())


def resolve_conversation_id(
    conversation_id: str,
    fallback_conversation_id: str = "",
    session_id: str = "",
) -> str:
    candidates = [c for c in (conversation_id, fallback_conversation_id, session_id) if c]
    chat_dir = Path(resolve_project_dir()) / ".cursor" / "chat-transcripts"
    for cid in candidates:
        if (chat_dir / f"{cid}.jsonl").is_file():
            return cid
    return candidates[0] if candidates else ID_UNAVAILABLE


def substitute_tokens(
    context: str,
    conversation_id: str,
    fallback_conversation_id: str = "",
    session_id: str = "",
) -> str:
    if TOKEN_PROJECT_DIR in context:
        context = context.replace(TOKEN_PROJECT_DIR, resolve_project_dir())
    if TOKEN_CONVERSATION_ID in context:
        context = context.replace(
            TOKEN_CONVERSATION_ID,
            resolve_conversation_id(conversation_id, fallback_conversation_id, session_id),
        )
    return context


def main() -> int:
    context = sys.stdin.read()
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

    sys.stdout.write(
        substitute_tokens(context, conversation_id, fallback_conversation_id, session_id)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
