# MarmoMind : An Agentic AI designed and built by Azadeh Jafari (jfr.azadeh@gmail.com).
# Created May 2026. Developed during my Ph.D. research in computational neuroscience.
# See README for the published protocol this work builds on.
"""Tolerant matching with an explicit ambiguity safety boundary.

Principle: interpret human-provided inputs the way a colleague would — forgiving
about FORMATTING (case, separators, ordinary date variants), strict about
MEANING. Tolerance must NOT become guessing: when an input could mean more than
one thing, or cannot be resolved, return a clear flag for the human instead of
inventing an interpretation. Every resolver returns a status:

    "matched"/"resolved"/"found"  -> a single confident answer
    "ambiguous"                   -> >1 plausible answer; DEFER to human
    "unmatched"/"unresolved"/"absent" -> none; flag (absent notes are normal)
"""
import re
from pathlib import Path
from typing import Optional


def canon(s) -> str:
    """Casefold; collapse any run of non-alphanumerics to a single space; strip.
    'M12-20231015' / 'm12_20231015' / 'm12 20231015' -> 'm12 20231015'."""
    return re.sub(r"[^a-z0-9]+", " ", str(s).casefold()).strip()


def tokens(s) -> list:
    return [t for t in canon(s).split(" ") if t]


# ---------------------------------------------------------------- monkey id ---
def resolve_monkey(query, candidates: list) -> dict:
    """Resolve a name/token (DICOM subject, or a note's 'monkey' field) to a
    single sheet animal. candidates: [{'name','id','sheet_name'}].

    Matches on animal name (whole-string or as a discrete token of the query) or
    on the ID as a discrete token (token equality, so 'm1' never matches 'm12').
    Returns matched / ambiguous / unmatched — never guesses between two animals.
    """
    q_tokens = set(tokens(query))
    q_canon = canon(query)
    hits = {}
    for c in candidates:
        if not c.get("name"):
            continue
        name_c = canon(c["name"])
        id_c = canon(c.get("id") or "")
        matched = bool(name_c) and (name_c == q_canon or name_c in q_tokens)
        matched = matched or (bool(id_c) and id_c in q_tokens)
        if matched:
            hits[c.get("id") or c["name"]] = c

    uniq = list(hits.values())
    if len(uniq) == 1:
        return {"status": "matched", **uniq[0]}
    if len(uniq) > 1:
        listing = ", ".join(f"{c['name']}({c.get('id')})" for c in uniq)
        return {"status": "ambiguous", "query": query, "candidates": uniq,
                "message": f"'{query}' could refer to {len(uniq)} monkeys: {listing} "
                           f"— deferring to human."}
    return {"status": "unmatched", "query": query,
            "message": f"no monkey in the sheet matches '{query}' — deferring to human."}


# --------------------------------------------------------------------- date ---
def normalize_date(value) -> dict:
    """Validate a date as YYYYMMDD (any non-digit separators are ignored, so
    '20231025' and '2023-10-25' both work). The lab standardizes note-filename
    dates to YYYYMMDD, so nothing exotic is parsed: if the 8 digits are not a
    valid calendar date, flag and defer — never guess.
    """
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 8:
        y, mo, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return {"status": "resolved", "iso": f"{y:04d}-{mo:02d}-{d:02d}"}
    return {"status": "unresolved",
            "message": f"date '{value}' is not a valid YYYYMMDD — deferring to human."}


# Note filename, once case/separators/spaces are stripped: m{digits}run{digits}{8 digits}.
_NOTE_RE = re.compile(r"^m(\d+)run(\d+)(\d{8})$")


def parse_note_stem(stem: str) -> dict:
    """Parse a note filename stem into its three DISTINCT fields, tolerating
    harmless human formatting noise: case, interchangeable separators, and spaces
    ANYWHERE (including within a token). 'M 15 . Run 2 20231025',
    'm15_run2_20231025', and 'M15.Run2.20231025' all parse the same. Returns
    {id, run, date_digits} or None if it does not fit m{ID}_run{N}_{YYYYMMDD}."""
    compact = re.sub(r"[^a-z0-9]", "", str(stem).lower())   # drop case, separators, spaces
    m = _NOTE_RE.match(compact)
    if not m:
        return None
    return {"id": "m" + m.group(1), "run": int(m.group(2)), "date_digits": m.group(3)}


# -------------------------------------------------------------- note lookup ---
def find_run_note(monkey_id, run: int, date, notes_dir) -> dict:
    """Locate notes/m{ID}_run{N}_{YYYYMMDD}.yaml, matched by the three DISTINCT
    fields (ID, run, date). Tolerant of case, separators, and spaces (including
    within a token); strict that the date is a valid YYYYMMDD. An ABSENT note is
    normal. Two files matching the same (ID, run, date), or a file matching ID+run
    whose date is not valid YYYYMMDD, is 'ambiguous' and flagged — never guessed.
    """
    base = Path(notes_dir)
    target_id = re.sub(r"[^a-z0-9]", "", str(monkey_id).lower())
    target_run = int(run)
    target_iso = normalize_date(date).get("iso")
    target_digits = target_iso.replace("-", "") if target_iso else re.sub(r"\D", "", str(date))
    expected = f"{monkey_id}_run{run}_{target_digits}.yaml"
    if not base.exists():
        return {"status": "absent", "path": str(base / expected)}

    matched, malformed = [], []
    for p in list(base.glob("*.yaml")) + list(base.glob("*.yml")):
        parsed = parse_note_stem(p.stem)
        if not parsed or parsed["id"] != target_id or parsed["run"] != target_run:
            continue                                           # different note (id != m16 for m1, etc.)
        dv = normalize_date(parsed["date_digits"])
        if dv["status"] != "resolved":
            malformed.append(p)                                # right monkey+run, bad date -> flag
        elif dv["iso"] == target_iso:
            matched.append(p)
        # else: valid date for a DIFFERENT session -> not this run's note

    if len(matched) == 1 and not malformed:
        return {"status": "found", "path": str(matched[0])}
    candidates = matched + malformed
    if not candidates:
        return {"status": "absent", "path": str(base / expected)}
    if malformed and not matched:
        msg = (f"a note for {monkey_id} run {run} has a filename date that is not "
               f"valid YYYYMMDD — deferring to human.")
    else:
        msg = (f"{len(candidates)} note files match {monkey_id} run {run} on "
               f"{target_iso} — deferring to human.")
    return {"status": "ambiguous", "candidates": [str(p) for p in candidates], "message": msg}
