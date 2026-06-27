# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""parse_dicom_filenames — parse raw DICOM names, group by session, INFER run order."""
import re
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Optional

from claude_agent_sdk import tool

from ..common import ok, resolve, data_path

_DATE_RE = re.compile(r"^\d{8}$")


def parse_one(fname: str) -> Optional[dict]:
    """Parse one DICOM filename.

    Pattern: Subject^^^^.MR.Everling^Marmoset.SERIES.1.YYYYMMDD.HASH.dcm
    The 8-digit acquisition date anchors the parse; series sits two dot-fields
    before it (the instance number sits one before). Subject is the leading token
    with its trailing '^' padding stripped.
    """
    parts = fname.split(".")
    date_idx = next((i for i, p in enumerate(parts) if _DATE_RE.match(p)), None)
    if date_idx is None or date_idx < 2:
        return None
    series = parts[date_idx - 2]
    if not series.isdigit():
        return None
    raw = parts[date_idx]
    return {
        "subject": parts[0].split("^")[0],
        "series": int(series),
        "date": f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}",
    }


def series_of(fname: str) -> Optional[int]:
    p = parse_one(fname)
    return p["series"] if p else None


def parse_sessions(dicom_dir) -> dict:
    """Group DICOMs into sessions (one per subject+date) and label runs.

    Backlog-aware: multiple dates -> multiple sessions, returned oldest-first.
    Within a session: unique series sorted ascending -> smallest = 'ap', rest =
    r1, r2, r3...
    """
    d = Path(resolve(dicom_dir))
    files = sorted(p.name for p in d.glob("*.dcm")) if d.exists() else []
    groups: dict = defaultdict(Counter)
    for f in files:
        rec = parse_one(f)
        if rec:
            groups[(rec["subject"], rec["date"])][rec["series"]] += 1

    sessions = []
    for (subject, date), counter in groups.items():
        series_sorted = sorted(counter)
        runs = []
        for i, s in enumerate(series_sorted):
            runs.append({
                "series": s,
                "label": "ap" if i == 0 else f"r{i}",
                "run": None if i == 0 else i,
                "n_dicoms": counter[s],
            })
        sessions.append({
            "subject": subject,
            "date": date,
            "n_functional_runs": max(len(series_sorted) - 1, 0),
            "runs": runs,
        })
    sessions.sort(key=lambda s: s["date"])
    return {"sessions": sessions, "n_sessions": len(sessions), "n_dicom_files": len(files)}


@tool(
    "parse_dicom_filenames",
    "Parse raw DICOM filenames and group them into sessions (one per subject+date; "
    "handles a multi-session backlog, oldest first). Within each session, sort "
    "series ascending: smallest -> phase-reverse 'ap'; the rest -> r1, r2, r3... "
    "Run order is INFERRED, never hardcoded. Read-only.",
    {"dicom_dir": str},
)
async def parse_dicom_filenames(args: dict[str, Any]) -> dict[str, Any]:
    d = args.get("dicom_dir") or data_path("incoming_dicom")
    return ok(parse_sessions(d))
