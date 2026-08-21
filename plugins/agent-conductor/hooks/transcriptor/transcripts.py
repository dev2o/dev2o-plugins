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

UPDATED: 2026-08-14
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
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
DEFAULT_BUDGET = 60_000
BLOCK_SEP = "\n\n---\n\n"
DUMP_LOG = "/tmp/cursor-hook-debug/error.log"
_LOCK_RE = re.compile(
    r"<advisor-context-lock>.*?</advisor-context-lock>\s*(?:---\s*)?",
    re.DOTALL,
)
_ROLE = {
    "user": "User",
    "assistant": "Assistant",
    "thinking": "Thinking",
    "error": "Error",
    "tool": "Tool",
    "meta": "Meta",
}


def log_error(msg: str) -> None:
    """Append non-fatal filesystem or parsing errors to debug log without crashing."""
    try:
        os.makedirs("/tmp/cursor-hook-debug", exist_ok=True)
        with open(DUMP_LOG, "a", encoding="utf-8") as f:
            f.write(f"FAILED (transcripts CLI) - {msg}\n")
    except Exception:
        pass


def project_root() -> Path:
    """Project root containing .cursor/chat-transcripts/.

    Wraps path resolution in try/except to prevent permission crashes
    in restricted container environments when parent directories are unreadable.
    """
    env = os.environ.get("CURSOR_PROJECT_DIR")
    if env:
        try:
            return Path(env).resolve()
        except Exception as e:
            log_error(f"Could not resolve CURSOR_PROJECT_DIR '{env}': {e}")
            return Path(env)

    try:
        cwd = Path.cwd().resolve()
        for candidate in (cwd, *cwd.parents):
            try:
                if (candidate / ".cursor" / "chat-transcripts").is_dir():
                    return candidate
            except (OSError, PermissionError):
                continue
        return cwd
    except Exception as e:
        log_error(f"Could not resolve working directory: {e}")
        return Path("/tmp")


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


def local_dt(ts: str | None) -> datetime | None:
    dt = parse_ts(ts)
    if not dt:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone()
    return dt


def format_ts(ts: str | None) -> str:
    dt = local_dt(ts)
    if not dt:
        return "?"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_header_ts(ts: str | None) -> str:
    dt = local_dt(ts)
    if not dt:
        return "?"
    return dt.strftime("%Y-%m-%d")


def strip_advisor_lock(text: str) -> str:
    return _LOCK_RE.sub("", text).strip()


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def category_for(event: dict) -> str:
    name = event.get("hook_event_name", "")
    return EVENT_CATEGORY.get(name, "meta")


def iter_events(path: Path) -> Iterator[tuple[int, dict | None]]:
    """Stream events line-by-line with encoding resilience to prevent memory bloat."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield line_no, json.loads(line)
                except json.JSONDecodeError:
                    yield line_no, None
    except (OSError, PermissionError) as e:
        log_error(f"Failed to open or read transcript {path}: {e}")
        return


def compact_json(obj: object, limit: int = 200) -> str:
    try:
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        return truncate(raw, limit)
    except (TypeError, ValueError):
        return "[UNSERIALIZABLE_DATA]"


def tool_summary(event: dict, short: bool = False) -> str:
    name = event.get("hook_event_name", "tool")
    if name == "beforeReadFile":
        return f"Read: {event.get('file_path', '?')}"
    if name == "afterFileEdit":
        return f"Edit: {event.get('file_path', '?')}"
    if name == "subagentStart":
        desc = event.get("description") or event.get("subagent_type") or "?"
        return f"Subagent start {event.get('subagent_type', '?')}: {desc}"
    tool_name = event.get("tool_name") or name
    tool_input = event.get("tool_input") or {}
    if tool_name == "Shell" and isinstance(tool_input, dict):
        cmd = str(tool_input.get("command", ""))
        return f"Shell: {truncate(cmd, SHORT_LIMIT) if short else cmd}"
    if tool_name in ("Read", "Write", "StrReplace") and isinstance(tool_input, dict):
        fp = tool_input.get("file_path", "?")
        return f"{tool_name}: {fp}"
    if name == "postToolUse":
        out = event.get("tool_output")
        if out is not None:
            preview = truncate(str(out), 120)
            return f"{tool_name}: {preview}"
        return str(tool_name)
    if name == "postToolUseFailure":
        return f"{tool_name} failed: {event.get('error_message', '?')}"
    if isinstance(tool_input, dict) and tool_input:
        preview = compact_json(tool_input, TOOL_INPUT_PREVIEW if short else 400)
        return f"{tool_name}: {preview}"
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
        body = tool_summary(event, short=short)
    else:
        body = compact_json({k: v for k, v in event.items() if k not in ("ts", "conversation_id", "generation_id")})
    if short:
        body = truncate(body, SHORT_LIMIT)
    return body


def is_task_call(event: dict) -> bool:
    return event.get("hook_event_name") == "preToolUse" and event.get("tool_name") == "Task"


def is_subagent_stop(event: dict) -> bool:
    return event.get("hook_event_name") == "subagentStop"


@dataclass
class Block:
    start_idx: int
    end_idx: int
    text: str
    category: str

    @property
    def n_chars(self) -> int:
        return len(self.text)


def format_subagent_block(
    call_idx: int | None,
    call_ev: dict | None,
    stop_idx: int | None,
    stop_ev: dict | None,
    short: bool,
) -> Block:
    tool_input = (call_ev or {}).get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    sub_type = (
        tool_input.get("subagent_type")
        or (stop_ev or {}).get("subagent_type")
        or "?"
    )
    desc = tool_input.get("description") or (stop_ev or {}).get("description") or ""
    prompt = str(tool_input.get("prompt") or "")
    if not prompt and stop_ev:
        prompt = str(stop_ev.get("task") or "")
    prompt = strip_advisor_lock(prompt)
    if short:
        prompt = truncate(prompt, SHORT_LIMIT)

    status = str((stop_ev or {}).get("status") or "")

    header = f"**Subagent**  {sub_type}"
    if desc:
        header += f"  ·  {desc}"
    lines = [header]

    if prompt:
        lines.append("")
        lines.append("Call:")
        lines.append(prompt)
    if stop_ev is not None:
        lines.append("")
        lines.append("Returned:")
        lines.append(status or "unknown")

    start = call_idx if call_idx is not None else (stop_idx or 0)
    end = stop_idx if stop_idx is not None else (call_idx or 0)
    return Block(start, end, "\n".join(lines), "tool")


def format_plain_block(idx: int, event: dict, short: bool) -> Block | None:
    cat = category_for(event)
    body = body_for_event(event, short)
    if not body:
        return None
    role = _ROLE.get(cat, cat.title())
    text = f"**{role}**\n\n{body}"
    return Block(idx, idx, text, cat)


def render_blocks(indexed: list[tuple[int, dict]], short: bool) -> list[Block]:
    stops_by_id: dict[str, tuple[int, dict]] = {}
    for idx, ev in indexed:
        if is_subagent_stop(ev):
            sid = ev.get("subagent_id")
            if isinstance(sid, str) and sid:
                stops_by_id[sid] = (idx, ev)

    skip: set[int] = set()
    blocks: list[Block] = []
    for idx, ev in indexed:
        if idx in skip:
            continue
        if is_task_call(ev):
            tool_use_id = ev.get("tool_use_id")
            stop = stops_by_id.get(tool_use_id) if isinstance(tool_use_id, str) else None
            if stop:
                skip.add(stop[0])
                blocks.append(format_subagent_block(idx, ev, stop[0], stop[1], short))
            else:
                blocks.append(format_subagent_block(idx, ev, None, None, short))
            continue
        if is_subagent_stop(ev):
            blocks.append(format_subagent_block(None, None, idx, ev, short))
            continue
        block = format_plain_block(idx, ev, short)
        if block:
            blocks.append(block)
    return blocks


def _omit_marker(omitted_from: int, omitted_to: int, omitted_chars: int, cid: str, offset: int, limit: int) -> str:
    cmd = f"show {cid} --offset {offset} -n {limit}" if cid else f"--offset {offset} -n {limit}"
    return (
        f"[... events #{omitted_from}–#{omitted_to} omitted · ~{omitted_chars:,} chars]\n"
        f"{cmd}"
    )


def pack_blocks(
    blocks: list[Block], budget: int, conversation_id: str = ""
) -> tuple[list[str], dict | None]:
    if not blocks:
        return [], None
    if budget <= 0:
        return [b.text for b in blocks], None

    def joined_len(texts: list[str]) -> int:
        if not texts:
            return 0
        return sum(len(t) for t in texts) + len(BLOCK_SEP) * (len(texts) - 1)

    all_texts = [b.text for b in blocks]
    if joined_len(all_texts) <= budget:
        return all_texts, None

    head_i = 0
    for i, b in enumerate(blocks):
        if b.category == "user":
            head_i = i
            break
    head = blocks[head_i]

    tail: list[Block] = []
    marker_placeholder = "[... events #9999–#9999 omitted · ~99,999,999 chars]"
    for b in reversed(blocks):
        if b.start_idx <= head.end_idx:
            break
        trial = [head.text, marker_placeholder, b.text] + [
            x.text for x in reversed(tail)
        ]
        if joined_len(trial) > budget:
            break
        tail.append(b)
    tail.reverse()

    if not tail:
        omitted_from = head.end_idx + 1
        omitted_to = blocks[-1].end_idx
        if omitted_from > omitted_to:
            return [head.text], None
        omitted_chars = sum(
            len(b.text) for b in blocks[head_i + 1 :]
        )
        info = {
            "from": omitted_from,
            "to": omitted_to,
            "chars": omitted_chars,
            "offset": head_i + 1,
            "limit": len(blocks) - head_i - 1,
        }
        marker = _omit_marker(
            omitted_from, omitted_to, omitted_chars, conversation_id, info["offset"], info["limit"]
        )
        return [head.text, marker], info

    omitted_from = head.end_idx + 1
    omitted_to = tail[0].start_idx - 1
    if omitted_from > omitted_to:
        return [head.text] + [b.text for b in tail], None

    omitted_blocks = [
        b for b in blocks if b.end_idx >= omitted_from and b.start_idx <= omitted_to
    ]
    omitted_chars = sum(len(b.text) for b in omitted_blocks)
    first_omitted_i = head_i + 1
    last_kept_tail_i = len(blocks) - len(tail)
    info = {
        "from": omitted_from,
        "to": omitted_to,
        "chars": omitted_chars,
        "offset": first_omitted_i,
        "limit": last_kept_tail_i - first_omitted_i,
    }
    marker = _omit_marker(
        omitted_from, omitted_to, omitted_chars, conversation_id, info["offset"], info["limit"]
    )
    return [head.text, marker] + [b.text for b in tail], info


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


USAGE_BRIEF = (
    "brief: not a spawn line. Pass your spawn line verbatim, one of:\n"
    '  "Advise. <executor_id>"     (advisor — full transcript view)\n'
    '  "CID:<executor_id>"         (alias — same full view)'
)


@dataclass(frozen=True)
class Ref:
    id: str

    @property
    def senior_token(self) -> str:
        return f"CID:{self.id}"


@dataclass(frozen=True)
class TriageToken:
    ref: Ref | None


@dataclass(frozen=True)
class SeniorToken:
    ref: Ref


@dataclass(frozen=True)
class TokenError:
    given: str
    usage: str


@dataclass(frozen=True)
class Capture:
    ref: Ref
    source: str
    events: list[dict]


@dataclass(frozen=True)
class Missing:
    ref: Ref | None
    reason: str
    tried: tuple[str, ...]


SpawnToken = TriageToken | SeniorToken
Resolution = Capture | Missing
Fetcher = Callable[[Ref], Capture | None]


def parse_ref(raw: str) -> Ref | None:
    cid = raw.strip()
    if not cid or any(ch.isspace() for ch in cid):
        return None
    if ".." in cid or "/" in cid:
        return None
    return Ref(cid)


def parse_spawn_token(raw: str) -> SpawnToken | TokenError:
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    if text[:7].lower() == "advise.":
        rest = text[7:].strip()
        if not rest:
            return TriageToken(None)
        ref = parse_ref(rest)
        if ref is None:
            return TokenError(raw, USAGE_BRIEF)
        return SeniorToken(ref)
    if text[:4] == "CID:":
        rest = text[4:].strip()
        ref = parse_ref(rest)
        if ref is None:
            return TokenError(raw, USAGE_BRIEF)
        return SeniorToken(ref)
    ref = parse_ref(text)
    if ref is not None:
        return TriageToken(ref)
    return TokenError(raw, USAGE_BRIEF)


def cursor_project_slug(root: Path) -> str:
    try:
        resolved = root.resolve()
    except Exception:
        resolved = root
    posix = resolved.as_posix()
    if posix.startswith("/"):
        posix = posix[1:]
    return posix.replace("/", "-")


def _message_text(raw: dict) -> str:
    msg = raw.get("message")
    if isinstance(msg, str):
        return msg
    if not isinstance(msg, dict):
        return str(raw.get("text") or raw.get("content") or "")
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if text:
                parts.append(str(text))
    return "\n".join(parts)


def _tool_uses(raw: dict) -> list[dict]:
    msg = raw.get("message")
    if not isinstance(msg, dict):
        return []
    content = msg.get("content")
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict) and item.get("type") == "tool_use"]


def normalize_agent_event(raw: dict) -> list[dict]:
    if raw.get("hook_event_name"):
        return [raw]
    role = str(raw.get("role") or "").lower()
    if role == "user":
        text = _message_text(raw)
        return [{"hook_event_name": "beforeSubmitPrompt", "prompt": text}] if text else []
    if role == "assistant":
        out: list[dict] = []
        text = _message_text(raw)
        if text:
            out.append({"hook_event_name": "afterAgentResponse", "text": text})
        for tu in _tool_uses(raw):
            out.append(
                {
                    "hook_event_name": "preToolUse",
                    "tool_name": tu.get("name") or "tool",
                    "tool_input": tu.get("input") or {},
                }
            )
        return out
    return []


def load_capture(path: Path, ref: Ref, source: str) -> Capture | None:
    try:
        if not path.is_file():
            return None
    except (OSError, PermissionError):
        return None
    events, _skipped = load_transcript(path)
    normalized: list[dict] = []
    for ev in events:
        if ev.get("hook_event_name"):
            normalized.append(ev)
        else:
            normalized.extend(normalize_agent_event(ev))
    return Capture(ref, source, normalized)


def fetch_plugin_capture(ref: Ref) -> Capture | None:
    return load_capture(transcript_dir() / f"{ref.id}.jsonl", ref, "plugin-capture")


def workspace_agent_transcript_path(ref: Ref) -> Path | None:
    base = Path.home() / ".cursor" / "projects" / cursor_project_slug(project_root()) / "agent-transcripts"
    nested = base / ref.id / f"{ref.id}.jsonl"
    flat = base / f"{ref.id}.jsonl"
    try:
        if nested.is_file():
            return nested
        if flat.is_file():
            return flat
    except (OSError, PermissionError):
        return None
    return None


def fetch_cursor_agent_transcripts(ref: Ref) -> Capture | None:
    path = workspace_agent_transcript_path(ref)
    if path is None:
        return None
    return load_capture(path, ref, "cursor-agent-transcripts")


def miss_cloud_dash(_ref: Ref) -> Capture | None:
    return None


def sources_for(_ref: Ref) -> tuple[tuple[str, Fetcher], ...]:
    return (
        ("plugin-capture", fetch_plugin_capture),
        ("cursor-agent-transcripts", fetch_cursor_agent_transcripts),
        ("cloud-dash", miss_cloud_dash),
    )


def resolve(ref: Ref) -> Resolution:
    tried: list[str] = []
    for name, fetch in sources_for(ref):
        tried.append(name)
        cap = fetch(ref)
        if cap is not None:
            return cap
    return Missing(ref, "not-found", tuple(tried))


def first_objective(events: list[dict]) -> str:
    for ev in events:
        if category_for(ev) == "user":
            return collapse_ws(str(ev.get("prompt", "")))
    return ""


def render_recent(events: list[dict], last_n: int = 10) -> str:
    indexed = _filter_indexed(events, {"user", "assistant", "tool"}, hide_thinking=True)
    page = indexed[-last_n:]
    blocks = render_blocks(page, short=False)
    return BLOCK_SEP.join(b.text for b in blocks)


def render_missing(missing: Missing, audience: str) -> str:
    ref_attr = f' ref="{missing.ref.id}"' if missing.ref else ""
    tried = ",".join(missing.tried)
    tried_attr = f' tried="{tried}"' if tried else ""
    return (
        f'<brief audience="{audience}"{ref_attr}>\n'
        f'<no_transcript reason="{missing.reason}"{tried_attr}/>\n'
        f"</brief>"
    )


def render_triage(cap: Capture, recent: int = 10) -> str:
    objective = first_objective(cap.events)
    body = render_recent(cap.events, recent)
    obj_block = f"<objective>\n{objective}\n</objective>\n" if objective else ""
    recent_block = f"<recent>\n{body}\n</recent>\n" if body else "<recent/>\n"
    return (
        f'<brief audience="triage" ref="{cap.ref.id}" '
        f'source="{cap.source}" events="{len(cap.events)}">\n'
        f"{obj_block}"
        f"{recent_block}"
        f"<escalate>{cap.ref.senior_token}</escalate>\n"
        f"</brief>"
    )


def render_senior(cap: Capture, budget: int = DEFAULT_BUDGET) -> str:
    indexed = _filter_indexed(cap.events, None, hide_thinking=True)
    blocks = render_blocks(indexed, short=False)
    texts, omitted = pack_blocks(blocks, budget, cap.ref.id)
    truncated = "true" if omitted is not None else "false"
    body = BLOCK_SEP.join(texts)
    return (
        f'<brief audience="senior" ref="{cap.ref.id}" '
        f'source="{cap.source}" events="{len(cap.events)}" truncated="{truncated}">\n'
        f"<transcript>\n{body}\n</transcript>\n"
        f"</brief>"
    )


def cmd_brief(args: argparse.Namespace) -> int:
    token = parse_spawn_token(args.spawn_line)
    if isinstance(token, TokenError):
        print(token.usage, file=sys.stderr)
        return 2
    if isinstance(token, TriageToken):
        print(render_missing(Missing(None, "unstamped", ()), "senior"))
        return 0
    resolution = resolve(token.ref)
    if isinstance(resolution, Missing):
        print(render_missing(resolution, "senior"))
        return 0
    print(render_senior(resolution))
    return 0


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
    try:
        mtime = path.stat().st_mtime
    except (OSError, PermissionError) as e:
        log_error(f"Cannot stat {path}: {e}")
        return None

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
        "mtime": mtime,
    }


def collect_summaries() -> list[dict]:
    tdir = transcript_dir()
    try:
        if not tdir.is_dir():
            return []
    except (OSError, PermissionError):
        return []

    summaries = []
    try:
        for path in tdir.glob("*.jsonl"):
            summary = summarize_file(path)
            if summary:
                summaries.append(summary)
    except (OSError, PermissionError) as e:
        log_error(f"Failed during globbing {tdir}: {e}")

    summaries.sort(key=lambda s: s["mtime"], reverse=True)
    return summaries


def print_list(summaries: list[dict]) -> None:
    rows = [("CONVERSATION_ID", "START", "USER", "EVENTS", "SUMMARY")]
    for s in summaries:
        rows.append(
            (
                s["conversation_id"],
                format_ts(s["start_ts"]),
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
    print(f"  {prog} show {example_id}          # conversation view (~60k chars)")
    print(f"  {prog} show {example_id} --only user,assistant")
    print(f"  {prog} search \"keywords\" [-n N]      # keyword search across transcripts")
    print()
    print("Categories for --only: user, assistant, thinking, tool, error, meta")
    print("Default show hides thinking; see the footer for optional flags.")
    return 0


def _parse_only(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {p.strip() for p in raw.split(",") if p.strip()}


def _filter_indexed(
    events: list[dict], only: set[str] | None, hide_thinking: bool
) -> list[tuple[int, dict]]:
    indexed: list[tuple[int, dict]] = []
    for idx, ev in enumerate(events, start=1):
        cat = category_for(ev)
        if hide_thinking and cat == "thinking":
            continue
        if only is not None and cat not in only:
            continue
        indexed.append((idx, ev))
    return indexed


def _print_show_header(conversation_id: str, events: list[dict]) -> None:
    start = format_header_ts(events[0].get("ts") if events else None)
    print(f"# {conversation_id}  ·  {start}  ·  {len(events)} events")
    print()


def _print_show_footer(conversation_id: str) -> None:
    print("--- END OF USER TRANSCRIPT")
    print()
    print(
        f".cursor/chat-transcripts/_transcripts.py show {conversation_id} [--only user,assistant,thinking] [--full]"
    )


def cmd_show(args: argparse.Namespace) -> int:
    path = transcript_dir() / f"{args.conversation_id}.jsonl"
    try:
        if not path.is_file():
            print(f"No transcript: {args.conversation_id}", file=sys.stderr)
            return 1
    except (OSError, PermissionError) as e:
        print(f"Cannot access transcript: {args.conversation_id} ({e})", file=sys.stderr)
        return 1

    only = _parse_only(args.only)
    events, skipped = load_transcript(path)
    last_n = args.last
    if last_n is not None and last_n < 1:
        last_n = None
    if args.json:
        if last_n is not None and only is None:
            only = {"user", "assistant", "tool"}
        selected = [ev for ev in events if not only or category_for(ev) in only]
        if last_n is not None:
            selected = selected[-last_n:]
        for ev in selected:
            print(json.dumps(ev, ensure_ascii=False))
        if skipped:
            print(f"# skipped {skipped} malformed line(s)", file=sys.stderr)
        return 0

    hide_thinking = not args.full and (only is None or "thinking" not in only)
    if last_n is not None and only is None:
        only = {"user", "assistant", "tool"}
        hide_thinking = True
    indexed = _filter_indexed(events, only, hide_thinking)
    short = bool(args.short)
    paging = args.offset is not None or args.limit is not None
    cid = args.conversation_id

    if last_n is not None:
        page = indexed[-last_n:]
        blocks = render_blocks(page, short=short)
        texts = [b.text for b in blocks]
        body = BLOCK_SEP.join(texts)
        if body:
            print(body)
        if skipped:
            print(f"# skipped {skipped} malformed line(s)", file=sys.stderr)
        return 0

    _print_show_header(cid, events)

    if paging:
        total = len(indexed)
        offset = args.offset if args.offset is not None else 0
        if offset < 0:
            offset = max(0, total + offset)
        limit = args.limit if args.limit is not None else 20
        page = indexed[offset : offset + limit]
        blocks = render_blocks(page, short=short)
        texts = [b.text for b in blocks]
        body = BLOCK_SEP.join(texts)
        if body:
            print(body)
            print()
        _print_show_footer(cid)
    else:
        blocks = render_blocks(indexed, short=short)
        budget = 0 if args.full else args.budget
        texts, _omitted = pack_blocks(blocks, budget, cid)
        body = BLOCK_SEP.join(texts)
        if body:
            print(body)
            print()
        _print_show_footer(cid)

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
        parts.append(compact_json(tool_input))
    return "\n".join(parts)


def cmd_search(args: argparse.Namespace) -> int:
    tdir = transcript_dir()
    try:
        if not tdir.is_dir():
            return 0
    except (OSError, PermissionError):
        return 0

    term = args.term.lower()
    context = args.context
    matches = 0
    
    try:
        paths = sorted(tdir.glob("*.jsonl"))
    except (OSError, PermissionError) as e:
        log_error(f"Failed to glob search directory {tdir}: {e}")
        return 0

    for path in paths:
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
        help="Truncate bodies to 200 characters",
    )
    show_p.add_argument(
        "--full",
        action="store_true",
        help="Ignore budget; include thinking; do not truncate",
    )
    show_p.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_BUDGET,
        help="Max characters for default view (0 = unlimited). Ignored with --offset/-n or --full",
    )
    show_p.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help="Max events per page (enables paging mode)",
    )
    show_p.add_argument(
        "--offset",
        type=int,
        default=None,
        help="Skip first N matching events; negative = from the end (enables paging mode)",
    )
    show_p.add_argument(
        "--last",
        type=int,
        default=None,
        metavar="N",
        help="Last N user/assistant/tool events; body only (no header/footer)",
    )
    show_p.add_argument("--json", action="store_true", help="Output raw JSON lines")
    show_p.set_defaults(func=cmd_show)

    brief_p = sub.add_parser("brief", help="Expand a spawn line into the reader's view")
    brief_p.add_argument(
        "spawn_line",
        help='Your spawn line verbatim: "Advise. <id>" or "CID:<id>"',
    )
    brief_p.set_defaults(func=cmd_brief)

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
    try:
        return args.func(args)
    except BrokenPipeError:
        # Python flushes standard streams on exit; redirect leftover output to devnull
        # to prevent tracebacks when piping to utilities like head, grep, or pager tools.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        log_error(f"Unhandled CLI exception: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())