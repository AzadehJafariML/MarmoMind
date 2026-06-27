# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""detect_ready_run — readiness watcher over the two incoming folders."""
import time
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from ..common import ok, load_settings, data_path
from .dicom import parse_sessions


def _newest_mtime(path: Path) -> float:
    files = list(path.rglob("*")) if path.exists() else []
    return max((f.stat().st_mtime for f in files), default=0.0)


def detect_sessions(already_processed=None) -> dict:
    """Scan the DICOM + regressor folders and return the backlog of sessions with
    readiness annotations. Ready = DICOM series present + .1D regressors arrived +
    folders quiescent for the settings window. Folders come from data_path() —
    never searched for."""
    settings = load_settings()
    already = set(already_processed or [])
    dpath = data_path("incoming_dicom")
    rpath = data_path("incoming_regressors")
    quiescence = settings["detection"]["quiescence_seconds"]

    parsed = parse_sessions(dpath)
    last_change = max(_newest_mtime(dpath), _newest_mtime(rpath))
    secs = (time.time() - last_change) if last_change else None
    stable = secs is not None and secs >= quiescence
    # Count .1D files RECURSIVELY — the lab nests them in a per-session subfolder.
    reg_files = [p.name for p in rpath.rglob("*.1D")] if rpath.exists() else []
    has_regressors = bool(reg_files)

    sessions = []
    for sess in parsed["sessions"]:
        runs = [r for r in sess["runs"] if r["series"] not in already]
        if not runs:
            continue
        s = dict(sess)
        s["runs"] = runs
        s["regressors_present"] = has_regressors
        s["seconds_since_last_change"] = round(secs, 1) if secs is not None else None
        s["stable"] = stable
        s["ready"] = stable and has_regressors
        sessions.append(s)

    return {
        "sessions": sessions,
        "n_ready_sessions": sum(1 for s in sessions if s["ready"]),
        "regressor_files": reg_files,
        "quiescence_seconds": quiescence,
    }


@tool(
    "detect_ready_run",
    "Scan the DICOM and regressor folders and return the backlog of sessions that "
    "are READY to process. A session is ready when its DICOM series are present, "
    "regressor (.1D) files have arrived, and the folders have been QUIESCENT (no "
    "new files) for the settings quiescence window. The regressor folder is a "
    "readiness SIGNAL only; contents are not parsed here. Read-only.",
    {"already_processed": list},
)
async def detect_ready_run(args: dict[str, Any]) -> dict[str, Any]:
    return ok(detect_sessions(args.get("already_processed")))
