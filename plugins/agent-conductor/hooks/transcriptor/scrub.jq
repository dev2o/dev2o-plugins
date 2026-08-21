# 1. Safety Clamp: Prevent regex CPU stalls and memory bloat on unexpected massive payloads
def cap_length($max):
  if (type == "string") and (length > $max) then 
    (.[:$max] + "... [TRUNCATED: original length \(length) bytes]") 
  else . end;

# 2. Secret scrubbing, one gsub pass per pattern with no backtracking blowup.
# Leverages Oniguruma \K to reset match start, replacing only the secret while preserving keys.
def redact_secrets:
  if type == "string" then
    gsub("\\b(?:OP_|TAVILY)[A-Z0-9_]+\\s*[=:]\\s*\\K(?!\\[REDACTED\\])\\S+"; "[REDACTED]")
    | gsub("\\b[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)[A-Za-z0-9_]*\\s*[=:]\\s*\\K(?!\\[REDACTED\\])\\S+"; "[REDACTED]")
    # Redact known standalone token formats globally
    | gsub("sk-[A-Za-z0-9_-]{16,}"; "[REDACTED]")
    | gsub("gh[poa]_[A-Za-z0-9]{30,}"; "[REDACTED]")
    | gsub("github_pat_[A-Za-z0-9_]+"; "[REDACTED]")
    | gsub("xox[baprs]-[A-Za-z0-9-]+"; "[REDACTED]")
    | gsub("ops_[A-Za-z0-9]{16,}"; "[REDACTED]")
    | gsub("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+"; "[REDACTED]")
  else . end;

# 3. Safe recursive application wrapper
# Uses walk/1 to guarantee strings nested inside JSON objects/arrays are found and scrubbed!
def maybe_redact:
  walk(
    if type == "string" then 
      (cap_length(16384) | redact_secrets) 
    else . end
  );

# 4. Main transcript transformation pipeline
# Guard root against non-object payloads (e.g. null or array) to prevent fatal ". + {}" crashes
if type == "object" then
  . + {ts: ($ts // null)}
  # Safe string type-guard before splitting email
  | if (.user_email | type) == "string" then 
      .user_email |= (split("@")[0] // .) 
    else . end
  | del(.session_id, .workspace_roots, .transcript_path)
  # Drop file bodies on direct read attempts
  | if .hook_event_name == "beforeReadFile" then 
      del(.content) 
    else . end
  # Drop edit bodies; keep file_path and edit metadata safely
  | if .hook_event_name == "afterFileEdit" and (.edits | type) == "array" then
      .edits |= map(if type == "object" then del(.old_string, .new_string) else . end)
    else . end
  | if .hook_event_name == "preToolUse" and (.tool_input | type) == "object" then
      .tool_input |= del(.old_string, .new_string)
    else . end
  # Drop bulky tool output on read-like postToolUse (with string type-guard on tool_name)
  | if ((.tool_name | strings) // "" | test("read|fetch"; "i")) and .hook_event_name == "postToolUse" then
      if .tool_output != null then 
        .tool_output = "[OMITTED: Tool output dropped to prevent audit log bloat]" 
      else . end
    else . end
  # Keep the tail of shell stdout (afterShellExecution uses .output, not
  # .tool_output). An advisor that sees every command and no result can only
  # guess; errors and summary lines land at the end, so the tail is what earns
  # its budget. Capped tight because shell output is the bulkiest field here.
  | if .hook_event_name == "afterShellExecution" and (.output | type) == "string" then
      .output |= (
        if length > 1200 then
          "[TRUNCATED: kept the last 1200 of \(length) bytes]\n" + .[-1200:]
        else . end
      )
    else . end
  # Apply redaction recursively across all potential text or structured payloads
  | if .command != null then .command |= maybe_redact else . end
  | if .prompt != null then .prompt |= maybe_redact else . end
  | if .tool_input != null then .tool_input |= maybe_redact else . end
  | if .tool_output != null then .tool_output |= maybe_redact else . end
  | if .output != null then .output |= maybe_redact else . end
  | if .text != null then .text |= maybe_redact else . end
  | if .error_message != null then .error_message |= maybe_redact else . end
else . end