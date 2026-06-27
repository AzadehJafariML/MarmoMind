# MarmoMind : An Agentic AI designed and built by Azadeh Jafari (jfr.azadeh@gmail.com).
# Created May 2026. Developed during my Ph.D. research in computational neuroscience.
# See README for the published protocol this work builds on.
"""Deterministic processing pipeline with reliable, blocking human approval.

Why this exists: gating used to live in the SDK's can_use_tool callback, which
only fires when the model actually CALLS a mutating tool. If the model instead
asked "may I proceed?" in prose and ended its turn, nothing blocked and the
program exited. Here the control flow is plain Python and approval is a real
blocking input() — it cannot be skipped by how a model turn ends.

FLAGS vs BLOCKERS:
- FLAGS (compromised sort, volume mismatch, motion-exceeds, regressor issues,
  broken runs, missing notes) NEVER halt the pipeline. They are recorded and
  surfaced in the final report.
- BLOCKERS are the irreversible mutating actions (convert / sheet write / file
  move). In 'review' mode each waits for y/n. In 'auto' mode none pause.

The agent RECOMMENDS and sorts; it never pools data into analysis on its own.
"""
import sys

from .judge import judge_run            # the ONLY LLM step
from .tools.detect import detect_sessions
from .tools.sheets import lookup_id, next_session, append_rows
from .tools.notes import read_note_file
from .tools.regressors import check_regressors
from .tools.convert import convert_run
from .tools.volumes import volume_cross_check
from .tools.motion import run_motion_check
from .tools.filing import file_run


# --------------------------------------------------------------- approval ---
def make_approver(mode: str):
    """Return approver(title, detail) -> bool.
    'auto'   : never pauses (records intent, returns True).
    'review' : BLOCKS on input() until the operator answers y/n."""
    if mode == "auto":
        def approver(title, detail):
            print(f"  [auto] {title}: {detail}")
            return True
        return approver

    def approver(title, detail):
        print(f"\n  >>> APPROVAL NEEDED — {title}")
        print(f"      {detail}")
        try:
            ans = input("      Approve? [y/N] ").strip().lower()
        except EOFError:                      # stdin exhausted/closed -> fail safe
            print("      (no input available) -> DECLINED")
            return False
        ok = ans in ("y", "yes")
        print("      ->", "APPROVED" if ok else "DECLINED")
        return ok
    return approver


# ----------------------------------------------------- numeric context ---
def _vol_ctx(vc) -> str:
    if vc.get("match") is True:
        return f"{vc['data_volumes']} volumes, matches the note"
    if vc.get("match") is False:
        return f"data {vc['data_volumes']} vs note {vc['note_volumes']} — MISMATCH"
    return "note volume blank or data unreadable; no cross-check"


def _motion_ctx(mr) -> str:
    if mr.get("error"):
        return f"unavailable ({mr['error']})"
    return (f"relative RMS max {mr['rel_rms_max_mm']:.3f}mm vs threshold "
            f"{mr['threshold_mm']}mm ({'EXCEEDS' if mr.get('exceeds') else 'within'})")


def _reg_ctx(rc) -> str:
    return "clean" if rc.get("ok") else \
        f"missing={rc.get('missing')} stray={rc.get('stray')} warnings={rc.get('warnings')}"


def _dest(sort) -> str:
    return {"compromised": "review", "ambiguous": "defer(stays in main)"}.get(sort, "main")


# --------------------------------------------------------------- pipeline ---
def process_session(sess, approver, actions, flags):
    subject, date = sess["subject"], sess["date"]
    info = lookup_id(subject)
    if not info.get("found"):
        flags.append({"type": "identity", "run": "-",
                      "detail": info.get("message", f"could not resolve monkey '{subject}'")})
        print(f"  Cannot resolve monkey for '{subject}' — flagged, session skipped.")
        return

    mid, tab = info["id"], info["tab"]
    session = next_session(tab)["next_session"]      # "s108"
    sn = session.lstrip("s")                          # "108" (filename form)
    runs = sess["runs"]
    functional = [r for r in runs if r["label"] != "ap"]
    print(f"\n=== Session {session}  {subject} ({mid})  {date}  — "
          f"{len(functional)} functional runs ===")

    # read notes + regressor checks (read-only; flags only)
    notes, reg_results = {}, {}
    for r in functional:
        n = read_note_file(mid, r["run"], date)
        notes[r["run"]] = n
        if not n["found"]:
            flags.append({"type": "note", "run": f"r{r['run']}",
                          "detail": "no note found — logged with blanks"})
        rc = check_regressors(n.get("conditions"), r["run"], monkey_id=mid, date=date)
        reg_results[r["run"]] = rc
        if not rc["ok"]:
            flags.append({"type": "regressor", "run": f"r{r['run']}",
                          "detail": f"missing={rc['missing']} stray={rc['stray']} warnings={rc['warnings']}"})

    # GATE 1 — convert (log-and-convert FIRST, every run)
    series_desc = ", ".join(f"{r['label']}({r['series']})" for r in runs)
    if not approver("CONVERT", f"dcm2niix all {len(runs)} series into Raw_Nifti_Data_{date}/: {series_desc}"):
        flags.append({"type": "skipped", "run": "-",
                      "detail": "conversion declined — session not processed further"})
        return
    converted = {}
    for r in runs:
        res = convert_run(mid, sn, r["label"], r["series"], date)
        converted[r["label"]] = res
        actions.append({"action": "convert", "run": r["label"],
                        "output": res.get("output_path"), "n_volumes": res.get("n_volumes"),
                        "skipped": res.get("skipped"), "error": res.get("error")})

    # volume cross-check per functional run (FLAG, never halts); record the real count to log
    vol_results = {}
    for r in functional:
        n = notes[r["run"]]
        dv = converted.get(r["label"], {}).get("n_volumes")
        vc = volume_cross_check(dv, n.get("volumes"))
        vol_results[r["run"]] = vc
        n["_log_volumes"] = vc.get("log_volumes")
        if vc.get("match") is False:
            flags.append({"type": "volume_mismatch", "run": f"r{r['run']}", "detail": vc["warning"]})

    # GATE 2 — sheet write (one row per functional run; real volume count)
    rows = []
    for i, r in enumerate(functional):
        n = notes[r["run"]]
        row = {"Run": f"r{r['run']}", "Volumes": n.get("_log_volumes"),
               "Resolution": n.get("resolution"), "TR": n.get("tr"), "Coils": n.get("coil"),
               "Task": n.get("task"), "Comments": n.get("comments")}
        if i == 0:
            row.update({"Date of scan": date, "State of the animal": n.get("state"),
                        "Time In": n.get("time_in"), "Time Out": n.get("time_out")})
        rows.append(row)
    if approver("SHEET WRITE", f"append {len(rows)} functional rows to tab '{tab}' as {session}"):
        res = append_rows(tab, session, rows)
        actions.append({"action": "sheet_append", "tab": tab, "session": session,
                        "rows": res.get("rows"), "error": res.get("error")})
    else:
        flags.append({"type": "skipped", "run": "-", "detail": "sheet write declined"})

    # motion tripwire for ALL functional runs (read-only; flag) — feeds the judge
    motion_results = {}
    for r in functional:
        path = converted.get(r["label"], {}).get("output_path")
        mr = run_motion_check(path) if path else {"error": "no nifti"}
        motion_results[r["run"]] = mr
        if mr.get("exceeds"):
            flags.append({"type": "motion", "run": f"r{r['run']}",
                          "detail": f"{mr['note']} (rel_rms_max={mr['rel_rms_max_mm']:.3f}mm "
                                    f"> {mr['threshold_mm']}mm)"})

    # JUDGMENT — the ONLY LLM step: reason by meaning over note + numeric outputs
    sorts = {}
    for r in functional:
        ctx = {"regressor": _reg_ctx(reg_results[r["run"]]),
               "volume": _vol_ctx(vol_results[r["run"]]),
               "motion": _motion_ctx(motion_results[r["run"]])}
        res = judge_run(notes[r["run"]], ctx)
        sorts[r["run"]] = res
        sort = res["sort"]
        if sort in ("broken", "compromised", "ambiguous"):
            flags.append({"type": sort, "run": f"r{r['run']}", "detail": res["rationale"]})

    print("  LLM judgment (meaning-based):")
    for r in functional:
        res = sorts[r["run"]]
        print(f"    r{r['run']}: {res['sort']:11} [{res['source']}] {res['rationale']}")

    # GATE 3 — file moves. clean->main, compromised->review, broken->main(skip-analysis),
    # ambiguous->left in main and flagged (deferred, not guessed).
    plan = ", ".join(f"r{r['run']}->{_dest(sorts[r['run']]['sort'])}" for r in functional)
    if approver("FILE MOVES", f"file {len(functional)} runs: {plan}"):
        for r in functional:
            res = sorts[r["run"]]
            sort = res["sort"]
            path = converted.get(r["label"], {}).get("output_path")
            if not path:
                continue
            if sort == "ambiguous":      # defer: do not move, leave in main, record
                actions.append({"action": "file", "run": f"r{r['run']}", "sort": "ambiguous",
                                "dest": path, "skip_analysis": False})
                continue
            fr = file_run(path, sort, res["rationale"])
            actions.append({"action": "file", "run": f"r{r['run']}", "sort": sort,
                            "dest": fr.get("final_path"), "skip_analysis": fr.get("skip_analysis")})
    else:
        flags.append({"type": "skipped", "run": "-", "detail": "file moves declined"})


def run(mode: str = "review") -> dict:
    mode = mode if mode in ("review", "auto") else "review"
    approver = make_approver(mode)
    print(f"MarmoMind — {mode.upper()} mode "
          + ("(stop-and-wait at each mutating step)" if mode == "review"
             else "(do-all-then-report; nothing pauses)"))

    det = detect_sessions([])
    ready = [s for s in det["sessions"] if s["ready"]]
    if not ready:
        print("\nNo ready sessions to process.")
        return {"actions": [], "flags": [], "sessions": 0}

    actions, flags = [], []
    for sess in ready:
        process_session(sess, approver, actions, flags)
    _report(mode, actions, flags)
    return {"actions": actions, "flags": flags, "sessions": len(ready)}


def _report(mode, actions, flags):
    print("\n" + "=" * 72)
    print(f"MarmoMind run report  ({mode} mode)")
    print("=" * 72)
    print(f"\nActions performed ({len(actions)}):")
    for a in actions or ["  (none)"]:
        if isinstance(a, dict):
            extra = f"  vols={a['n_volumes']}" if a.get("n_volumes") is not None else ""
            extra += "  SKIP-ANALYSIS" if a.get("skip_analysis") else ""
            extra += f"  ERROR={a['error']}" if a.get("error") else ""
            print(f"  - {a['action']:13} {a.get('run','') or '':4} "
                  f"{a.get('dest') or a.get('output') or a.get('tab','') or ''}{extra}")
        else:
            print(a)
    print(f"\nFlags for your review ({len(flags)}):")
    if not flags:
        print("  (none)")
    for f in flags:
        print(f"  [{f['type']:15}] {f.get('run','-') or '-':4} {f['detail']}")
    print("\nMarmoMind RECOMMENDS and sorts — nothing was pooled into analysis. "
          "Review the flags above\nand the review/ folder before analyzing.")
