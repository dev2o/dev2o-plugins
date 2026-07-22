. + {ts: $ts}
| if (.user_email // null) != null then .user_email = (.user_email | split("@")[0]) else . end
| del(.session_id, .workspace_roots, .transcript_path)
| if .hook_event_name == "beforeReadFile" then del(.content) else . end
