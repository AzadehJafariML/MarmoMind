# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""Human-in-the-loop gating.

- can_use_tool: auto-allow read-only tools; ask the operator (terminal y/N) before
  every MUTATING tool (sheet append, conversion, file move) and any Bash. If there
  is no interactive terminal, deny mutating tools (fail safe).
- block_destructive_bash: a PreToolUse hook that hard-denies destructive shell
  commands regardless of permission mode — defense in depth.
"""
import asyncio
import os
import re
import sys

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

READ_ONLY_TOOLS = {
    "mcp__marmomind__detect_ready_run",
    "mcp__marmomind__parse_dicom_filenames",
    "mcp__marmomind__read_note",
    "mcp__marmomind__check_regressor_files",
    "mcp__marmomind__lookup_monkey_id",
    "mcp__marmomind__get_next_session_number",
    "mcp__marmomind__cross_check_volumes",
    "mcp__marmomind__motion_check",
    "Read",
}
MUTATING_TOOLS = {
    "mcp__marmomind__append_run_rows",
    "mcp__marmomind__convert_and_rename_run",
    "mcp__marmomind__file_run_into_folder",
    "Bash",
}

# Destructive shell patterns blocked unconditionally.
_DESTRUCTIVE = [
    r"\brm\s+-[a-z]*[rf]", r"\bmkfs\b", r"\bdd\s+if=", r">\s*/dev/(sd|disk|nvme)",
    r":\(\)\s*\{", r"\bshutdown\b", r"\breboot\b", r"\bmkswap\b",
    r"\bchmod\s+-R\s+0*00\b", r"\bgit\s+push\b", r"\bgit\s+remote\b",
]


def _summarize(tool_name: str, data: dict) -> str:
    if tool_name.endswith("append_run_rows"):
        return f"APPEND {len(data.get('rows', []))} row(s) to sheet tab '{data.get('tab')}' (session {data.get('session')})"
    if tool_name.endswith("convert_and_rename_run"):
        return f"CONVERT series {data.get('series')} -> m{data.get('id')}_s{data.get('session')}_{data.get('label')} (dcm2niix)"
    if tool_name.endswith("file_run_into_folder"):
        return f"MOVE {os.path.basename(str(data.get('nifti_path')))} -> '{data.get('sort')}' folder"
    if tool_name == "Bash":
        return f"RUN shell: {data.get('command', '')[:120]}"
    return f"{tool_name} {data}"


async def can_use_tool(tool_name: str, input_data: dict, context):
    """Permission policy. Read-only -> allow; mutating -> ask the operator."""
    if tool_name in READ_ONLY_TOOLS:
        return PermissionResultAllow(updated_input=input_data)

    summary = _summarize(tool_name, input_data)
    if os.environ.get("MARMOMIND_AUTO_APPROVE") == "1":
        return PermissionResultAllow(updated_input=input_data)
    if not sys.stdin or not sys.stdin.isatty():
        return PermissionResultDeny(
            message=f"Declined (no interactive approval available) for: {summary}")

    answer = await asyncio.get_event_loop().run_in_executor(
        None, lambda: input(f"\n[MarmoMind] Approve — {summary}?  [y/N] "))
    if answer.strip().lower() in ("y", "yes"):
        return PermissionResultAllow(updated_input=input_data)
    return PermissionResultDeny(message=f"Operator declined: {summary}")


async def block_destructive_bash(input_data: dict, tool_use_id, context):
    """PreToolUse hook: hard-deny destructive Bash regardless of permission mode."""
    if input_data.get("tool_name") != "Bash":
        return {}
    command = (input_data.get("tool_input") or {}).get("command", "")
    for pat in _DESTRUCTIVE:
        if re.search(pat, command):
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Blocked destructive command (pattern {pat!r}): {command[:120]}",
            }}
    return {}
