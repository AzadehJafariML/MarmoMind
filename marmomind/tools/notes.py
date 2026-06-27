# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""read_note — load a per-run YAML note, matched by RUN NUMBER."""
from pathlib import Path
from typing import Any

import yaml
from claude_agent_sdk import tool

from ..common import ok, resolve, data_path
from ..matching import find_run_note

# Canonical fields the experimenter may fill (missing -> None, never an error).
_FIELDS = ["monkey", "run", "experiment", "description", "conditions", "state",
          "time_in", "time_out", "task", "comments", "volumes", "coil", "tr",
          "resolution"]

_BLANK = {k: None for k in _FIELDS}


def read_note_file(monkey_id: str, run: int, date: str, notes_dir=None) -> dict:
    """Locate and read notes/m{ID}_run{N}_{YYYYMMDD}.yaml, matched by the three
    DISTINCT fields (ID, run, date). The ID comes from the Summary lookup; the date
    is the session date from the DICOM parse. Tolerant of filename formatting noise
    (case, separators, spaces — including within a token); strict that the date is
    a valid YYYYMMDD. Missing file or field -> nulls, found=False; never raises.
    Two matching files, or a file with a non-YYYYMMDD date, flags 'ambiguous' and
    defers (does NOT pick one)."""
    base = resolve(notes_dir) if notes_dir else data_path("notes")
    hit = find_run_note(monkey_id, run, date, base)

    if hit["status"] == "ambiguous":
        return {"found": False, "ambiguous": True, "message": hit["message"],
                "candidates": hit["candidates"], **_BLANK}
    if hit["status"] == "absent":
        return {"found": False, "path": hit["path"], **_BLANK}

    fp = Path(hit["path"])
    try:
        data = yaml.safe_load(fp.read_text()) or {}
    except yaml.YAMLError as e:
        # unreadable note -> flag, do not invent content
        return {"found": True, "path": str(fp), "parse_error": str(e),
                "message": f"note '{fp.name}' could not be parsed — deferring to human.",
                **_BLANK}
    out = {k: data.get(k) for k in _FIELDS}
    out["found"] = True
    out["path"] = str(fp)
    return out


@tool(
    "read_note",
    "Read the per-run note matched by (monkey ID, run number, session date): "
    "notes/m{ID}_run{N}_{Date}.yaml. The ID comes from lookup_monkey_id and the "
    "date from parse_dicom_filenames, so call this AFTER both. Filename matching is "
    "TOLERANT of case, separators, and date-format variants. Returns fields as "
    "structured data; missing file or field -> null (found=False, which is "
    "normal). If TWO files match the same (ID, run, date), or a note can't be "
    "parsed, returns an 'ambiguous'/parse-error flag for the human instead of "
    "guessing. The note-filename date is always YYYYMMDD; formatting noise (case, "
    "separators, spaces — including within a token) is tolerated, but a date that "
    "is not a valid YYYYMMDD is flagged, never guessed. The phase-reverse (ap) has "
    "no note. Read-only.",
    {"id": str, "run": int, "date": str, "notes_dir": str},
)
async def read_note(args: dict[str, Any]) -> dict[str, Any]:
    return ok(read_note_file(args["id"], int(args["run"]), args["date"],
                             args.get("notes_dir")))
