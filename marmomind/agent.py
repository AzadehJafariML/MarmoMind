# MarmoMind : An Agentic AI designed and built by Azadeh Jafari (jfr.azadeh@gmail.com).
# Created May 2026. Developed during my Ph.D. research in computational neuroscience.
# See README for the published protocol this work builds on.
"""MarmoMind entry point.

Execution runs through the DETERMINISTIC pipeline (marmomind/pipeline.py), so
human approval reliably blocks at each mutating step and never depends on how a
model turn ends. Two modes:

    python -m marmomind.agent --mode review   # stop-and-wait at each step (default)
    python -m marmomind.agent --mode auto     # do-all-then-report; nothing pauses
    python -m marmomind.agent --paths         # print resolved data paths
    python -m marmomind.agent --dry-run       # show SDK tool registry, no run

The @tool/MCP wiring below (build_options) is retained for optional interactive
LLM use and is what --dry-run inspects; it is NOT the execution path.
"""
import argparse

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, create_sdk_mcp_server

from .common import PROJECT_ROOT, resolved_paths
from .system_prompt import SYSTEM_PROMPT
from .permissions import READ_ONLY_TOOLS, can_use_tool, block_destructive_bash
from .pipeline import run as run_pipeline
from .tools.detect import detect_ready_run
from .tools.dicom import parse_dicom_filenames
from .tools.notes import read_note
from .tools.regressors import check_regressor_files
from .tools.sheets import lookup_monkey_id, get_next_session_number, append_run_rows
from .tools.convert import convert_and_rename_run
from .tools.volumes import cross_check_volumes
from .tools.motion import motion_check
from .tools.filing import file_run_into_folder

ALL_TOOLS = [
    detect_ready_run, parse_dicom_filenames, read_note, check_regressor_files,
    lookup_monkey_id, get_next_session_number, append_run_rows,
    convert_and_rename_run, cross_check_volumes, motion_check, file_run_into_folder,
]


def build_options() -> ClaudeAgentOptions:
    server = create_sdk_mcp_server(name="marmomind", version="0.1.0", tools=ALL_TOOLS)
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,                  # full replacement (domain agent)
        mcp_servers={"marmomind": server},
        # ONLY read-only tools are pre-allowed; mutating tools are deliberately
        # left out so they fall through to can_use_tool for human approval.
        allowed_tools=sorted(READ_ONLY_TOOLS),
        # The agent must NEVER shell out to LOCATE its folders — paths come
        # deterministically from common.data_path(), not from the LLM searching.
        disallowed_tools=["Bash", "Glob", "Grep", "WebFetch"],
        permission_mode="default",
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[block_destructive_bash])]},
        cwd=str(PROJECT_ROOT),
        model="opus",
        setting_sources=[],                           # isolate from ambient CLAUDE.md/settings
    )


def _print_paths() -> None:
    """Print every resolved path so the operator can confirm they point at real
    data. Precedence per path: env MARMOMIND_<NAME> > settings.yaml > project-relative."""
    paths = resolved_paths()
    print("MarmoMind resolved paths (project root auto-detected, fully portable):\n")
    for name, p in paths.items():
        exists = "" if name == "PROJECT_ROOT" else ("  [exists]" if p.exists() else "  [MISSING]")
        print(f"  {name:20} {p}{exists}")


def _dry_run() -> None:
    """Validate wiring without contacting the API."""
    opts = build_options()
    print("system_prompt chars :", len(opts.system_prompt))
    print("mcp server          :", list(opts.mcp_servers))
    print("registered tools    :", [t.name for t in ALL_TOOLS])
    print("allowed (pre-approved):")
    for t in opts.allowed_tools:
        print("   -", t)
    print("gated via can_use_tool: append_run_rows, convert_and_rename_run, "
          "file_run_into_folder, Bash")
    print("permission_mode     :", opts.permission_mode)
    print("model               :", opts.model)
    print("DRY RUN OK — no API call made.")


def main() -> None:
    p = argparse.ArgumentParser(description="MarmoMind processing agent")
    p.add_argument("--mode", choices=["review", "auto"], default="review",
                  help="review = stop-and-wait for approval at each mutating step "
                       "(default); auto = do-all-then-report, nothing pauses")
    p.add_argument("--paths", action="store_true", help="print resolved paths and exit")
    p.add_argument("--dry-run", action="store_true", help="validate SDK tool wiring, no run")
    args = p.parse_args()

    if args.paths:
        _print_paths()
        return
    if args.dry_run:
        _dry_run()
        return
    run_pipeline(mode=args.mode)        # deterministic, blocking-approval pipeline


if __name__ == "__main__":
    main()
