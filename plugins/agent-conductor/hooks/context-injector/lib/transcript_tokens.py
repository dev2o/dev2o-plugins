#!/usr/bin/env python3
"""Substitute {{CONVERSATION_ID}} in subagent context templates."""

from __future__ import annotations

import sys
from pathlib import Path

TOKEN_CONVERSATION_ID = "{{CONVERSATION_ID}}"
ID_UNAVAILABLE = "(conversation id unavailable)"


def resolve_conversation_id(
    conversation_id: str,
    fallback_conversation_id: str = "",
    session_id: str = "",
) -> str:
    candidates = [c for c in (conversation_id, fallback_conversation_id, session_id) if c]
    chat_dir = Path(__file__).resolve().parents[3] / ".cursor" / "chat-transcripts"
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
    if TOKEN_CONVERSATION_ID not in context:
        return context
    return context.replace(
        TOKEN_CONVERSATION_ID,
        resolve_conversation_id(conversation_id, fallback_conversation_id, session_id),
    )


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
