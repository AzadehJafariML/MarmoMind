# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""The ONLY LLM step: the per-run quality judgment.

Everything else in MarmoMind is deterministic Python. Here the model reasons BY
MEANING over the experimenter's free-text note plus the numeric tool outputs
(regressor check, volume cross-check, motion number) and returns a sort
(clean / compromised / broken / ambiguous) with a written rationale. It RECOMMENDS
only — never auto-rejects, never pools into analysis; genuinely unclear cases come
back as 'ambiguous' (deferred, not guessed). It never sees images.

If the model is unreachable, judge_run falls back to a transparent rule so the
deterministic pipeline never breaks (and says so in the rationale/source).
"""
import asyncio
import json
import re

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

from .common import load_settings, load_lab_rules

JUDGE_SYSTEM = """\
You are MarmoMind's quality-judgment step for awake, head-fixed marmoset fMRI.
For ONE functional run, decide a single sort by reasoning about the MEANING of the
experimenter's free-text note plus the numeric tool outputs you are given. You
RECOMMEND only; a human makes the final call.

SORTS:
- "broken": the run did not validly execute as designed — e.g. the stimulus code
  or scanner failed/stopped mid-run, a false start, an abort. Data may exist, but
  the paradigm did not run correctly, so events after the failure are invalid.
  (skip analysis)
- "compromised": the run is valid but its quality is reduced in a way that matters
  for THIS paradigm — e.g. drowsiness on a task that needs an alert animal, or
  equipment that partially failed. (keep, but separate for review)
- "clean": no meaningful problem. (main)
- "ambiguous": the note is genuinely vague, missing, or self-contradictory and you
  cannot responsibly decide. (defer to the human — do NOT guess)

DOMAIN KNOWLEDGE (apply by reading the run's description, never by keyword):
- Arousal is PARADIGM-DEPENDENT. Auditory paradigms tolerate low arousal —
  auditory processing persists under light sleep / anesthesia. So drowsiness ALONE
  on an auditory run is NOT a quality reduction: sort it CLEAN (you may note the
  drowsiness for the record), do NOT mark it compromised for drowsiness. Visual
  paradigms require alertness with eyes open, so drowsiness / eye-closure DOES
  compromise them. Judge a drowsy animal against what THIS run's paradigm needs;
  any OTHER problem in the note is still judged normally.

RULES:
- The experimenter's free-text COMMENT plus the experiment DESCRIPTION are the
  single source of truth for quality. There is no separate label or hint field.
- Reason about MEANING, never keywords. "the code failed at volume 200" means the
  stimulus program crashed -> broken (events after vol 200 are invalid).
  "conked out / partly sleepy" means the animal became drowsy -> weigh that for the
  described paradigm.
- If the comment plainly instructs a verdict (e.g. "this run is invalid, do not
  analyze"), understand and respect it as part of reading the comment.
- Reason ONLY over the note text and the numeric facts provided (regressor check,
  volume cross-check, motion number). You never see images and never assert an
  image artifact. Motion is a tripwire that may justify a human visual check; on
  its own it does NOT make a run broken.
- Never auto-reject and never pool into analysis. When genuinely unsure -> "ambiguous".

Output STRICT JSON and nothing else:
{"sort": "clean|compromised|broken|ambiguous", "rationale": "<one or two sentences>"}
"""


def _prompt(note: dict, ctx: dict) -> str:
    lines = ["Judge this single functional run.\n", "NOTE (experimenter's own words):"]
    for k in ("experiment", "description", "state", "task", "comments", "conditions"):
        v = note.get(k)
        if v not in (None, "", []):
            lines.append(f"- {k}: {v}")
    lines.append("\nNUMERIC TOOL OUTPUTS:")
    lines.append(f"- regressor check: {ctx.get('regressor', 'n/a')}")
    lines.append(f"- volume cross-check: {ctx.get('volume', 'n/a')}")
    lines.append(f"- motion: {ctx.get('motion', 'n/a')}")
    lines.append('\nReturn STRICT JSON: {"sort": "...", "rationale": "..."}')
    return "\n".join(lines)


async def _ask_llm(note: dict, ctx: dict, model: str) -> str:
    opts = ClaudeAgentOptions(
        system_prompt=JUDGE_SYSTEM,
        allowed_tools=[],
        disallowed_tools=["Bash", "Glob", "Grep", "WebFetch", "Read", "Write", "Edit"],
        permission_mode="default",
        setting_sources=[],
        max_turns=1,
        model=model,
    )
    text = ""
    async for msg in query(prompt=_prompt(note, ctx), options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    text += b.text
    return text


def _parse(text: str):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    sort = str(d.get("sort", "")).strip().lower()
    if sort not in {"clean", "compromised", "broken", "ambiguous"}:
        return None
    return {"sort": sort, "rationale": str(d.get("rationale", "")).strip()}


def _rule_fallback(note: dict):
    """Transparent fallback if the LLM is unreachable — clearly labeled. Reads only
    the comment/description text (no hint field)."""
    rules = load_lab_rules().get("keywords", {})
    text = " ".join(str(x) for x in (note.get("comments"), note.get("description"),
                                     note.get("state")) if x).lower()
    if any(k.lower() in text for k in rules.get("broken", [])):
        return "broken", "matched a broken cue in the comment (rule fallback)"
    if any(k.lower() in text for k in rules.get("compromised", [])):
        return "compromised", "matched a compromised cue in the comment (rule fallback)"
    return "clean", "no broken/compromised cue in the comment (rule fallback)"


def judge_run(note: dict, context: dict = None) -> dict:
    """Return {'sort', 'rationale', 'source'}. LLM meaning-judge by default; rule
    fallback only if the model is unreachable."""
    ctx = context or {}
    model = load_settings().get("judge", {}).get("model", "sonnet")
    try:
        text = asyncio.run(_ask_llm(note, ctx, model))
    except Exception as e:                       # model unreachable -> deterministic fallback
        sort, reason = _rule_fallback(note)
        return {"sort": sort, "rationale": f"[LLM unavailable: {type(e).__name__}] {reason}",
                "source": "rule-fallback"}
    parsed = _parse(text)
    if parsed:
        parsed["source"] = "llm"
        return parsed
    return {"sort": "ambiguous",                 # unparseable -> defer, never guess
            "rationale": f"LLM judge output could not be parsed; deferring. raw: {text[:160]}",
            "source": "llm-parsefail"}
