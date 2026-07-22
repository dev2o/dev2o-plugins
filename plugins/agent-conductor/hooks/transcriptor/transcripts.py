#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Browse scrubbed Cursor hook transcripts by conversation_id.

Standard-library only, so it runs under any python3 without a package
manager. The PEP 723 metadata block above declares zero dependencies, so
`uv run` (or any PEP 723 runner) still works, but is not required — the
plain `python3` shebang avoids dying in sandboxes that lack uv.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

EVENT_CATEGORY: dict[str, str] = {
    "beforeSubmitPrompt": "user",
    "afterAgentResponse": "assistant",
    "afterAgentThought": "thinking",
    "preToolUse": "tool",
    "postToolUse": "tool",
    "afterFileEdit": "tool",
    "beforeReadFile": "tool",
    "subagentStart": "tool",
    "subagentStop": "tool",
    "postToolUseFailure": "error",
    "stop": "meta",
    "preCompact": "meta",
}

SHORT_LIMIT = 200
TOOL_INPUT_PREVIEW = 100


def project_root() -> Path:
    """Project root containing .cursor/chat-transcripts/.

    Transcripts are project-scoped data, but this script lives in the plugin
    cache, so __file__ is useless for locating them. Resolution order:
    1. CURSOR_PROJECT_DIR (hooks set it; the injected advisor command sets it)
    2. Walk up from cwd looking for .cursor/chat-transcripts/
    3. cwd itself (so error messages point at a sane location)
    """
    env = os.environ.get("CURSOR_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".cursor" / "chat-transcripts").is_dir():
            return candidate
    return cwd


def transcript_dir(root: Path | None = None) -> Path:
    base = root or project_root()
    return base / ".cursor" / "chat-transcripts"


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def format_time(ts: str | None) -> str:
    dt = parse_ts(ts)
    if not dt:
        return "??:??:??"
    return dt.strftime("%H:%M:%S")


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def category_for(event: dict) -> str:
    name = event.get("hook_event_name", "")
    return EVENT_CATEGORY.get(name, "meta")


def iter_events(path: Path) -> Iterator[tuple[int, dict | None]]:
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            yield line_no, json.loads(line)
        except json.JSONDecodeError:
            yield line_no, None


def compact_json(obj: object, limit: int = 200) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return truncate(raw, limit)


def tool_summary(event: dict) -> str:
    name = event.get("hook_event_name", "tool")
    if name == "beforeReadFile":
        return f"Read file {event.get('file_path', '?')}"
    if name == "afterFileEdit":
        return f"Edit {event.get('file_path', '?')}"
    if name == "subagentStart":
        return f"Subagent start {event.get('subagent_type', '?')}: {truncate(str(event.get('task', '')), 120)}"
    if name == "subagentStop":
        return f"Subagent stop {event.get('subagent_type', '?')} ({event.get('status', '?')})"
    tool_name = event.get("tool_name") or name
    tool_input = event.get("tool_input") or {}
    if tool_name == "Shell" and isinstance(tool_input, dict):
        cmd = tool_input.get("command", "")
        return f"Shell: {truncate(str(cmd), 160)}"
    if tool_name in ("Read", "Write", "StrReplace") and isinstance(tool_input, dict):
        fp = tool_input.get("file_path", "?")
        return f"{tool_name}: {fp}"
    if name == "postToolUse":
        out = event.get("tool_output")
        if out is not None:
            return f"{tool_name}: {truncate(str(out), 120)}"
    if name == "postToolUseFailure":
        return f"{tool_name} failed: {event.get('error_message', '?')}"
    if isinstance(tool_input, dict) and tool_input:
        return f"{tool_name}: {truncate(compact_json(tool_input, TOOL_INPUT_PREVIEW), 160)}"
    return str(tool_name)


def body_for_event(event: dict, short: bool) -> str:
    cat = category_for(event)
    if cat == "user":
        body = str(event.get("prompt", ""))
    elif cat == "assistant":
        body = str(event.get("text", ""))
    elif cat == "thinking":
        body = str(event.get("text", ""))
    elif cat == "error":
        body = str(event.get("error_message", compact_json(event)))
    elif cat == "tool":
        body = tool_summary(event)
    else:
        body = compact_json({k: v for k, v in event.items() if k not in ("ts", "conversation_id", "generation_id")})
    if short:
        body = truncate(body, SHORT_LIMIT)
    return body


def load_transcript(path: Path) -> tuple[list[dict], int]:
    events: list[dict] = []
    skipped = 0
    for _line_no, event in iter_events(path):
        if event is None:
            skipped += 1
            continue
        events.append(event)
    return events, skipped


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_TITLE_RE = re.compile(r"--title\s+(?:\"([^\"]*)\"|'([^']*)')")
_COMMIT_HEREDOC_RE = re.compile(r"-m\s+\"\$\(cat\s+<<'?EOF'?\n([^\n]*)")
_COMMIT_MSG_RE = re.compile(r"-m\s+(?:\"([^\"]*)\"|'([^']*)')")


def pr_title_from_command(command: str) -> str | None:
    if "gh pr create" not in command:
        return None
    m = _TITLE_RE.search(command)
    if not m:
        return None
    return m.group(1) or m.group(2)


def commit_message_from_command(command: str) -> str | None:
    if "git commit" not in command:
        return None
    m = _COMMIT_HEREDOC_RE.search(command)
    if m:
        return m.group(1)
    m = _COMMIT_MSG_RE.search(command)
    if not m:
        return None
    msg = m.group(1) or m.group(2) or ""
    return msg.splitlines()[0] if msg else None


def snippet_for_events(events: list[dict]) -> str:
    pr_title: str | None = None
    commit_msg: str | None = None
    first_prompt: str | None = None
    for ev in events:
        if ev.get("hook_event_name") == "beforeSubmitPrompt" and first_prompt is None:
            first_prompt = str(ev.get("prompt", ""))
        tool_input = ev.get("tool_input")
        if ev.get("tool_name") == "Shell" and isinstance(tool_input, dict):
            command = str(tool_input.get("command", ""))
            title = pr_title_from_command(command)
            if title:
                pr_title = title
            msg = commit_message_from_command(command)
            if msg:
                commit_msg = msg
    best = pr_title or commit_msg or first_prompt or ""
    return collapse_ws(best)


def summarize_file(path: Path) -> dict | None:
    events, _skipped = load_transcript(path)
    if not events:
        return None
    conversation_id = path.stem
    user_prefix: str | None = None
    start_ts: str | None = None
    for ev in events:
        if not start_ts and ev.get("ts"):
            start_ts = str(ev["ts"])
        email = ev.get("user_email")
        if user_prefix is None and isinstance(email, str) and email:
            user_prefix = email
    return {
        "conversation_id": conversation_id,
        "path": path,
        "start_ts": start_ts,
        "user_prefix": user_prefix,
        "event_count": len(events),
        "snippet": snippet_for_events(events),
        "mtime": path.stat().st_mtime,
    }


def collect_summaries() -> list[dict]:
    tdir = transcript_dir()
    if not tdir.is_dir():
        return []
    summaries = []
    for path in tdir.glob("*.jsonl"):
        summary = summarize_file(path)
        if summary:
            summaries.append(summary)
    summaries.sort(key=lambda s: s["mtime"], reverse=True)
    return summaries


def print_list(summaries: list[dict]) -> None:
    rows = [("CONVERSATION_ID", "START", "USER", "EVENTS", "SUMMARY")]
    for s in summaries:
        rows.append(
            (
                s["conversation_id"],
                s["start_ts"] or "?",
                s["user_prefix"] or "-",
                str(s["event_count"]),
                truncate(s["snippet"], 60),
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    for row in rows:
        cols = [row[i].ljust(widths[i]) for i in range(4)] + [row[4]]
        print("  ".join(cols).rstrip())


def cmd_list(args: argparse.Namespace) -> int:
    summaries = collect_summaries()
    if not summaries:
        print("No transcripts found.", file=sys.stderr)
        return 0
    if not args.all:
        summaries = summaries[: args.limit]
    print_list(summaries)
    return 0


def cmd_guide() -> int:
    prog = sys.argv[0]
    print("Browse scrubbed Cursor chat transcripts (one .jsonl per conversation).")
    print()
    summaries = collect_summaries()
    if summaries:
        print_list(summaries[:10])
        example_id = summaries[0]["conversation_id"]
    else:
        print("No transcripts found yet.")
        example_id = "<conversation_id>"
    print()
    print("Usage:")
    print(f"  {prog} list [--all | -n N]           # list recent transcripts")
    print(f"  {prog} show {example_id}          # short bodies, first 20 events")
    print(f"  {prog} show {example_id} --only user,assistant --offset 20 --full")
    print(f"  {prog} search \"keywords\" [-n N]      # keyword search across transcripts")
    print()
    print("Categories for --only: user, assistant, thinking, tool, error, meta")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    path = transcript_dir() / f"{args.conversation_id}.jsonl"
    if not path.is_file():
        print(f"No transcript: {args.conversation_id}", file=sys.stderr)
        return 1
    only = None
    if args.only:
        only = {p.strip() for p in args.only.split(",") if p.strip()}
    events, skipped = load_transcript(path)
    if args.json:
        for ev in events:
            if only and category_for(ev) not in only:
                continue
            print(json.dumps(ev, ensure_ascii=False))
        if skipped:
            print(f"# skipped {skipped} malformed line(s)", file=sys.stderr)
        return 0
    short = not args.full
    matching = [
        (idx, ev)
        for idx, ev in enumerate(events, start=1)
        if not only or category_for(ev) in only
    ]
    total = len(matching)
    offset = args.offset if args.offset >= 0 else max(0, total + args.offset)
    page = matching[offset : offset + args.limit]
    for idx, ev in page:
        cat = category_for(ev)
        header = f"[#{idx} {format_time(ev.get('ts'))}] {cat}"
        body = body_for_event(ev, short)
        print(header)
        if body:
            print(body)
        print()
    end = offset + len(page)
    filtered = len(events) - total
    print(f"# events {offset + 1}-{end} of {total} ({filtered} filtered by --only).")
    hints = []
    if end < total:
        hints.append(f"next page: --offset {end}")
    if short:
        hints.append("full bodies: --full")
    hints.append("narrow: --only user,assistant,thinking,tool,error,meta")
    print("# " + " | ".join(hints))
    if skipped:
        print(f"# skipped {skipped} malformed line(s)", file=sys.stderr)
    return 0


def searchable_text(event: dict) -> str:
    parts = [event.get("hook_event_name", "")]
    for key in ("prompt", "text", "command", "error_message", "task", "summary"):
        val = event.get(key)
        if val:
            parts.append(str(val))
    tool_input = event.get("tool_input")
    if tool_input:
        parts.append(json.dumps(tool_input))
    return "\n".join(parts)


def cmd_search(args: argparse.Namespace) -> int:
    tdir = transcript_dir()
    if not tdir.is_dir():
        return 0
    term = args.term.lower()
    context = args.context
    matches = 0
    for path in sorted(tdir.glob("*.jsonl")):
        events, _skipped = load_transcript(path)
        for ev in events:
            text = searchable_text(ev)
            idx = text.lower().find(term)
            if idx < 0:
                continue
            matches += 1
            if matches > args.limit:
                return 0
            start = max(0, idx - context)
            end = min(len(text), idx + len(term) + context)
            snippet = text[start:end].replace("\n", " ")
            print(
                f"{path.stem}\t{ev.get('hook_event_name', '?')}\t{truncate(snippet, 200)}"
            )
    if matches == 0:
        print(
            f"No matches for {args.term!r}. Try a broader term, or run 'list' to browse transcripts.",
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Browse Cursor hook transcripts")
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="List recent transcripts")
    list_p.add_argument("--all", action="store_true", help="List all transcripts")
    list_p.add_argument("-n", "--limit", type=int, default=20, help="Max results")
    list_p.set_defaults(func=cmd_list)

    show_p = sub.add_parser("show", help="Show one transcript")
    show_p.add_argument("conversation_id", help="Conversation id (filename stem)")
    show_p.add_argument(
        "--only",
        help="Comma-separated categories: user,assistant,thinking,tool,error,meta",
    )
    show_p.add_argument(
        "--short",
        action="store_true",
        help="Truncate bodies (default; kept for compatibility)",
    )
    show_p.add_argument("--full", action="store_true", help="Untruncated bodies")
    show_p.add_argument("-n", "--limit", type=int, default=20, help="Max events per page")
    show_p.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip first N matching events; negative = from the end (tail)",
    )
    show_p.add_argument("--json", action="store_true", help="Output raw JSON lines")
    show_p.set_defaults(func=cmd_show)

    search_p = sub.add_parser("search", help="Keyword search across transcripts")
    search_p.add_argument("term", help="Search term")
    search_p.add_argument("-n", "--limit", type=int, default=20, help="Max matches")
    search_p.add_argument(
        "--context",
        type=int,
        default=80,
        help="Characters of context around match",
    )
    search_p.set_defaults(func=cmd_search)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        return cmd_guide()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
