# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""motion_check — mcflirt relative-RMS tripwire, numbers only."""
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from ..common import ok, fail, resolve, load_settings, load_lab_rules


def run_motion_check(nifti_path) -> dict:
    mcflirt = load_settings()["binaries"]["mcflirt"]
    threshold = load_lab_rules()["motion"]["relative_rms_mm"]
    nifti = Path(resolve(nifti_path))
    if not nifti.exists():
        return {"error": "nifti not found", "nifti_path": str(nifti)}

    with tempfile.TemporaryDirectory() as tmp:
        base = f"{tmp}/mc"
        proc = subprocess.run([mcflirt, "-in", str(nifti), "-out", base, "-rmsrel"],
                              capture_output=True, text=True)
        rel = Path(f"{base}_rel.rms")
        if not rel.exists():
            return {"error": "mcflirt produced no rel.rms", "returncode": proc.returncode,
                    "stderr": proc.stderr[-600:]}
        vals = [float(x) for x in rel.read_text().split()]

    rel_max = max(vals) if vals else None
    rel_mean = (sum(vals) / len(vals)) if vals else None
    exceeds = rel_max is not None and rel_max > threshold
    return {
        "rel_rms_max_mm": rel_max,
        "rel_rms_mean_mm": rel_mean,
        "threshold_mm": threshold,
        "exceeds": exceeds,
        "note": ("relative RMS displacement elevated — recommend visual inspection in FSLeyes"
                 if exceeds else "relative RMS within threshold"),
    }


@tool(
    "motion_check",
    "Run mcflirt on one functional run's NIfTI and return relative RMS "
    "displacement as NUMBERS only (max + mean) plus whether it exceeds the "
    "lab-rules threshold. A numeric tripwire, NOT a stop/go verdict; it does NOT "
    "assert a motion artifact exists. Do not run on 'ap' or runs sorted broken. "
    "Read-only (writes only a small temp .rms file).",
    {"nifti_path": str},
)
async def motion_check(args: dict[str, Any]) -> dict[str, Any]:
    res = run_motion_check(args["nifti_path"])
    return fail(res["error"], **res) if "error" in res else ok(res)
