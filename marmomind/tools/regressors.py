# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""check_regressor_files — filename-only sanity check of .1D regressors vs note.

Real lab layout: one subfolder per session named m{ID}_{YYYYMMDD}, holding files
named {Condition}_r{N}.1D (e.g. m15_20231025/Chatter_r1.1D). For a given run the
tool gathers that run's .1D files, reads the condition NAMES from the filenames,
and compares them to the note's declared conditions. It only lists/compares
filenames — it never opens a .1D file, and never blocks.
"""
import re
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from ..common import ok, resolve, data_path
from ..matching import normalize_date

# Filenames look like "{Condition}_r{N}.1D" — tolerant of the separator before r.
_REG_RE = re.compile(r"^(?P<cond>.+?)[ _\-.]*r(?P<run>\d+)$", re.IGNORECASE)


def _norm(s) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def _compact(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def parse_regressor_stem(stem: str):
    """('Chatter_r1') -> ('Chatter', 1); None if it has no run suffix."""
    m = _REG_RE.match(str(stem).strip())
    if not m:
        return None
    return m.group("cond").strip(" _-."), int(m.group("run"))


def find_session_dir(monkey_id, date, root) -> dict:
    """Locate the per-session regressor subfolder m{ID}_{YYYYMMDD} under `root`,
    tolerant of case/separators. Falls back to a flat layout (.1D directly in
    root). Returns {status, dir|candidates}."""
    root = Path(resolve(root))
    if not root.exists():
        return {"status": "absent", "root": str(root)}
    target_id = _compact(monkey_id)
    iso = normalize_date(date).get("iso")
    target_digits = iso.replace("-", "") if iso else re.sub(r"\D", "", str(date))

    matches = []
    for sub in root.iterdir():
        if not sub.is_dir():
            continue
        m = re.match(r"^m(\d+)(\d{8})$", _compact(sub.name))
        if m and ("m" + m.group(1)) == target_id and m.group(2) == target_digits:
            matches.append(sub)

    if len(matches) == 1:
        return {"status": "found", "dir": matches[0]}
    if len(matches) > 1:
        return {"status": "ambiguous", "candidates": [str(p) for p in matches]}
    if any(root.glob("*.1D")):                       # flat fallback
        return {"status": "found", "dir": root}
    return {"status": "absent", "root": str(root)}


def check_regressors(conditions, run, monkey_id=None, date=None, regressor_dir=None) -> dict:
    """Compare the run's declared condition NAMES against the {Condition}_r{N}.1D
    files present for that run. Reports missing / stray / name-mismatch; never
    opens a file, never blocks. Resolves the session subfolder from (id, date)
    unless an explicit regressor_dir is given."""
    conditions = conditions or []
    run = int(run)

    if regressor_dir:
        sess = {"status": "found", "dir": Path(resolve(regressor_dir))}
    else:
        sess = find_session_dir(monkey_id, date, data_path("incoming_regressors"))
    if sess["status"] != "found":
        return {"ok": False, "run": run, "declared": conditions, "present": [],
                "missing": conditions, "stray": [], "warnings": [],
                "regressors_status": sess["status"],
                "message": f"could not resolve a regressor folder for {monkey_id} {date} "
                           f"({sess['status']}) — deferring to human."}

    sdir = sess["dir"]
    # Only this run's files, mapped normalized-name -> original condition string.
    present = {}
    for p in sdir.glob("*.1D"):
        parsed = parse_regressor_stem(p.stem)
        if parsed and parsed[1] == run:
            present[_norm(parsed[0])] = parsed[0]

    declared = {_norm(c): c for c in conditions}
    missing = [declared[k] for k in declared if k not in present]
    stray = [f"{present[k]}_r{run}.1D" for k in present if k not in declared]
    warnings = [f"name differs: note '{declared[k]}' vs file '{present[k]}_r{run}.1D' (case/spacing)"
                for k in declared if k in present and declared[k] != present[k]]

    return {
        "ok": not missing and not stray and not warnings,
        "run": run,
        "regressor_dir": str(sdir),
        "declared": conditions,
        "present": sorted(present.values()),
        "missing": missing,
        "stray": stray,
        "warnings": warnings,
    }


@tool(
    "check_regressor_files",
    "For one run, compare the condition NAMES declared in the note against the "
    "{Condition}_r{N}.1D regressor files present for that run. The session folder "
    "(m{ID}_{YYYYMMDD}) is resolved from the monkey ID and date. REPORTS (never "
    "blocks) missing condition files, stray/extra files, and name mismatches "
    "(case/spacing = warnings). Lists/compares filenames ONLY; never opens a .1D "
    "file. Read-only.",
    {"conditions": list, "run": int, "id": str, "date": str, "regressor_dir": str},
)
async def check_regressor_files(args: dict[str, Any]) -> dict[str, Any]:
    return ok(check_regressors(args.get("conditions"), args["run"], args.get("id"),
                               args.get("date"), args.get("regressor_dir")))
