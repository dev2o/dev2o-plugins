# 1. Safety Clamp: Prevent regex CPU stalls and memory bloat on unexpected massive payloads
def cap_length($max):
  if type == "string" and length > $max then 
    (.[:$max] + "... [TRUNCATED: original length \(length) bytes]") 
  else . end;

# 2. Optimized single-pass secret scrubbing (O(1) complexity, zero ReDoS, zero recursion)
def redact_secrets:
  # Use Oniguruma \K (keep match start) to replace only the secret value, preserving the variable name
  gsub("\\b(?:OP_|TAVILY)[A-Z0-9_]+\\s*[=:]\\s*\\K(?!\\[REDACTED\\])\\S+"; "[REDACTED]")
  | gsub("\\b[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)[A-Za-z0-9_]*\\s*[=:]\\s*\\K(?!\\[REDACTED\\])\\S+"; "[REDACTED]")
  # Redact known standalone token formats globally
  | gsub("sk-[A-Za-z0-9_-]{16,}"; "[REDACTED]")
  | gsub("gh[poa]_[A-Za-z0-9]{30,}"; "[REDACTED]")
  | gsub("github_pat_[A-Za-z0-9_]+"; "[REDACTED]")
  | gsub("xox[baprs]-[A-Za-z0-9-]+"; "[REDACTED]")
  | gsub("ops_[A-Za-z0-9]{16,}"; "[REDACTED]")
  | gsub("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+"; "[REDACTED]");

# 3. Safe application wrapper (caps any string to 16KB before running regexes)
def maybe_redact:
  if type == "string" then 
    (cap_length(16384) | redact_secrets) 
  else . end;

# 4. Main transcript transformation pipeline
. + {ts: $ts}
| if (.user_email // null) != null then 
    .user_email = (.user_email | split("@")[0]) 
  else . end
| del(.session_id, .workspace_roots, .transcript_path)
# Drop file bodies on direct read attempts
| if .hook_event_name == "beforeReadFile" then 
    del(.content) 
  else . end
# Drop edit bodies; keep file_path and edit metadata
| if .hook_event_name == "afterFileEdit" and (.edits | type) == "array" then
    .edits |= map(del(.old_string, .new_string))
  else . end
# Drop bulky tool output on read-like postToolUse
| if (.tool_name // "" | test("read|fetch"; "i")) and .hook_event_name == "postToolUse" then
    if .tool_output != null then 
      .tool_output = "[OMITTED: Tool output dropped to prevent audit log bloat]" 
    else . end
  else . end
# Drop shell stdout (afterShellExecution uses .output, not .tool_output)
| if .hook_event_name == "afterShellExecution" and .output != null then
    .output = "[OMITTED: Shell output dropped to prevent audit log bloat]"
  else . end
# Apply redaction cleanly across all potential text payloads
| if .tool_output != null then .tool_output |= maybe_redact else . end
| if .output != null then .output |= maybe_redact else . end
| if .text != null then .text |= maybe_redact else . end
| if .error_message != null then .error_message |= maybe_redact else . end