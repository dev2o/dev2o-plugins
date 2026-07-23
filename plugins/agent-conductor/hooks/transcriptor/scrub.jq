def redact_pass($re):
  if test($re + "\\s*[=:]\\s*(?!\\[REDACTED\\])\\S+") then
    capture("(?<prefix>" + $re + ")\\s*[=:]\\s*(?<val>\\S+)") as $c
    | gsub($c.prefix + "\\s*[=:]\\s*" + $c.val; $c.prefix + "=[REDACTED]")
  else . end;

def redact_secrets:
  def once:
    . as $before
    | redact_pass("OP_[A-Z0-9_]+")
    | redact_pass("TAVILY[A-Z0-9_]+")
    | redact_pass("[A-Za-z_][A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)[A-Za-z0-9_]+")
    | gsub("sk-[A-Za-z0-9_-]+"; "[REDACTED]")
    | gsub("ghp_[A-Za-z0-9]+"; "[REDACTED]")
    | gsub("gho_[A-Za-z0-9]+"; "[REDACTED]")
    | gsub("github_pat_[A-Za-z0-9_]+"; "[REDACTED]")
    | gsub("xox[baprs]-[A-Za-z0-9-]+"; "[REDACTED]")
    | gsub("ops_[A-Za-z0-9]+"; "[REDACTED]")
    | gsub("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+"; "[REDACTED]")
    | if . == $before then . else once end;
  once;

def maybe_redact:
  if type == "string" then redact_secrets else . end;

. + {ts: $ts}
| if (.user_email // null) != null then .user_email = (.user_email | split("@")[0]) else . end
| del(.session_id, .workspace_roots, .transcript_path)
| if .hook_event_name == "beforeReadFile" then del(.content) else . end
| if .tool_output != null then .tool_output |= maybe_redact else . end
| if .text != null then .text |= maybe_redact else . end
| if .error_message != null then .error_message |= maybe_redact else . end
