# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""convert_and_rename_run — dcm2niix conversion + standardized naming."""
import glob
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from ..common import ok, fail, resolve, load_settings, data_path
from ..nifti import read_volumes
from .dicom import series_of


def _output_dir(date: str) -> Path:
    root = data_path("output_root")
    d = root / f"Raw_Nifti_Data_{date}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stem(mid: str, session: str, label: str) -> str:
    # ONE NIfTI per run — a run is a single continuous timeseries. Conditions are
    # regressors (.1D), modeled later in the GLM; they are NOT part of the image
    # name. `mid` is the sheet ID and ALREADY includes the leading 'm' (e.g. m15),
    # so it is used verbatim. label is 'ap' or 'r1','r2',...
    return f"{mid}_s{session}_{label}"


def convert_run(mid, session, label, series, date, dicom_dir=None) -> dict:
    settings = load_settings()
    dcm2niix = settings["binaries"]["dcm2niix"]
    src = resolve(dicom_dir) if dicom_dir else data_path("incoming_dicom")
    out_dir = _output_dir(date)
    stem = _stem(mid, session, label)
    target = out_dir / f"{stem}.nii"

    if target.exists():   # already standardized -> skip A-F
        return {"output_path": str(target), "skipped": True, "reason": "already standardized",
                "n_volumes": read_volumes(target)}

    series_files = [p for p in src.glob("*.dcm") if series_of(p.name) == int(series)]
    if not series_files:
        return {"error": "no DICOMs found for series", "series": series, "dicom_dir": str(src)}

    with tempfile.TemporaryDirectory() as tmp:
        for p in series_files:
            shutil.copy(p, tmp)
        proc = subprocess.run([dcm2niix, "-z", "n", "-f", stem, "-o", tmp, tmp],
                              capture_output=True, text=True)
        produced = glob.glob(f"{tmp}/{stem}*.nii")
        if not produced:
            return {"error": "dcm2niix produced no .nii", "returncode": proc.returncode,
                    "stderr": proc.stderr[-600:]}
        shutil.move(produced[0], target)
    return {"output_path": str(target), "skipped": False, "n_dicoms": len(series_files),
            "n_volumes": read_volumes(target)}     # TRUE volume count from the data


@tool(
    "convert_and_rename_run",
    "Convert ONE run's DICOMs to NIfTI with dcm2niix (full path from settings) "
    "into Raw_Nifti_Data_<DATE>/. There is exactly ONE NIfTI per run: functionals "
    "-> m{id}_s{session}_{label}.nii (label r1, r2, ...); phase-reverse -> "
    "m{id}_s{session}_ap.nii. No condition (cnd) in the name — conditions are "
    "regressors handled separately. If the target already exists in standardized "
    "form, skip. Every run is converted regardless of quality (log-and-convert "
    "first). MUTATING — requires approval.",
    {"id": str, "session": str, "label": str, "series": int, "date": str,
     "dicom_dir": str},
)
async def convert_and_rename_run(args: dict[str, Any]) -> dict[str, Any]:
    res = convert_run(args["id"], args["session"], args["label"], args["series"],
                      args["date"], args.get("dicom_dir"))
    return fail(res["error"], **res) if "error" in res else ok(res)
