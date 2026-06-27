# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""cross_check_volumes — standard QC check: data volume count vs note's declared.

Run for EVERY functional run. The agent does NOT decide the cause and does NOT
skip the run; it logs the TRUE count and surfaces the possibilities for the human.
"""
from typing import Any

from claude_agent_sdk import tool

from ..common import ok


def volume_cross_check(data_volumes, note_volumes) -> dict:
    """Compare the real volume count from the data against the note's declared
    count. On a mismatch, emit a warning that names both possibilities — a note
    typo, or a TRUNCATED run whose regressors (built for the declared count) may
    not align with the acquired volumes (a GLM corruption risk)."""
    dv = None if data_volumes is None else int(data_volumes)
    nv = None if note_volumes is None else int(note_volumes)

    if dv is None or nv is None:
        return {"match": None, "data_volumes": dv, "note_volumes": nv,
                "log_volumes": dv,
                "note": "missing a volume count (data or note) — cannot cross-check; "
                        "log the real data count if available."}

    if dv == nv:
        return {"match": True, "data_volumes": dv, "note_volumes": nv, "log_volumes": dv}

    return {
        "match": False,
        "data_volumes": dv,
        "note_volumes": nv,
        "log_volumes": dv,                      # ALWAYS log the real data count
        "warning": (
            f"Volume mismatch: data has {dv} volumes but the note declared {nv}. "
            f"This may be a note typo, OR the run may have been truncated (designed "
            f"for {nv} but the scanner stopped at {dv}). If truncated, regressors "
            f"built for {nv} volumes may not align with the {dv} acquired volumes "
            f"(events scheduled after vol {dv} did not occur), which could corrupt "
            f"the GLM. Please verify before analysis."),
    }


@tool(
    "cross_check_volumes",
    "Standard per-run QC check: compare the TRUE volume count from the converted "
    "data (n_volumes returned by convert_and_rename_run) against the note's "
    "declared 'volumes'. Returns log_volumes = the REAL data count to record in "
    "the sheet (never the note's), and on a mismatch a warning naming both "
    "possibilities (note typo vs truncated run with regressor/GLM misalignment). "
    "Run this for every functional run; do NOT skip or decide the cause — surface "
    "it for the human. Read-only.",
    {"data_volumes": int, "note_volumes": int},
)
async def cross_check_volumes(args: dict[str, Any]) -> dict[str, Any]:
    return ok(volume_cross_check(args.get("data_volumes"), args.get("note_volumes")))
