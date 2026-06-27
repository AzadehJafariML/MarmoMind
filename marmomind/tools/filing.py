# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""file_run_into_folder — sort a converted run into main vs review/."""
import shutil
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from ..common import ok, fail

_SORTS = {"clean", "compromised", "broken"}


def file_run(nifti_path, sort: str, reason: str = "") -> dict:
    """clean/broken stay in the main Raw_Nifti_Data_<DATE>/ folder; compromised
    goes to the review/ subfolder (kept separate, never pooled). broken is filed
    but flagged skip-analysis (it was still logged and converted).

    `sort` is case-insensitive (Clean == clean == CLEAN)."""
    sort = str(sort).strip().lower()
    if sort not in _SORTS:
        return {"error": f"sort must be one of {sorted(_SORTS)}", "got": sort}
    nifti = Path(nifti_path)
    if not nifti.exists():
        return {"error": "nifti not found", "nifti_path": str(nifti)}

    dest_dir = nifti.parent / "review" if sort == "compromised" else nifti.parent
    dest_dir.mkdir(exist_ok=True)
    final = dest_dir / nifti.name
    if str(nifti.resolve()) != str(final.resolve()):
        shutil.move(str(nifti), str(final))
    return {"final_path": str(final), "sort": sort, "reason": reason,
            "skip_analysis": sort == "broken"}


@tool(
    "file_run_into_folder",
    "Move a converted functional .nii to its destination by the agent's sort: "
    "'clean' -> main folder; 'compromised' -> review/ subfolder (kept separate, "
    "never pooled with clean); 'broken' -> stays in main but flagged "
    "skip-analysis. 'reason' is recorded for the human. MUTATING — requires approval.",
    {"nifti_path": str, "sort": str, "reason": str},
)
async def file_run_into_folder(args: dict[str, Any]) -> dict[str, Any]:
    res = file_run(args["nifti_path"], args["sort"], args.get("reason", ""))
    return fail(res["error"], **res) if "error" in res else ok(res)
