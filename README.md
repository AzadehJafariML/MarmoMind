**MarmoMind** is an **AI agent** that automates the data handling and quality control stage (pre-preprocessing) that precedes the awake marmoset fMRI preprocessing pipeline used in our research group, published as:

   Zanini A, Dureux A, **Jafari A**, Gilbert KM, Zeman P, Bellyou M, Li A,
   Vander Tuin C, Everling S (2023). *In vivo functional brain mapping using
   ultra-high-field fMRI in awake common marmosets.* STAR Protocols 4(4):102586.

   Version 1 of this agent handles detection, conversion, naming, logging, and quality control, 
   the stage that feeds processing pipeline. Future versions will implement the
   preprocessing and fMRI analysis steps described in the protocol directly. Please attention no real data is published here.

# MarmoMind

MarmoMind is a **human-in-the-loop** processing agent for awake, head-fixed marmoset
fMRI. I built it to sit in the preparation room and do the work I cannot do alone in
real time while scanning marmosets: log every run, convert the raw data (DICOM) to Nifti, and reason about whether the data is worth analyzing (it is correct and clean considering the task and experimental conditions), while I keep my attention on the animal and experiment in the lab!
It recommends and sorts. I decide whenever is needed. It never pools data into a final analysis on its own, and it never claims to read or interpret a brain image. It reasons only over the text of my (experimenter) notes and the numeric outputs of its tools.

## The idea of building MarmoMind comes from:

The idea came from a problem I kept running into myself during my Ph.D. studies at the Centre for Functional and Metabolic Mapping (CFMM), University of Western Ontario, London, Canada. When I was alone in the scanner suite with an awake marmoset inside the scanner, I could not do two demanding things at once. I counld not keep monitoring the animal and the experimental conditions (subject arousal, its movements or active vocalization, whether the task was actually engaging it, and ...) and at the same time pull each run off the scanner, convert it, check it, and decide whether it is clean. So the pre-preprocessing and quality control always happened after one whole day when scanning was done, sometimes too late! A run that was contaminated partway through would only reveal itself once I sat down to check the session and analyze data (typically the day after experiment day), and by then the scanner time was already spent. That waste of time (and of course $) was what I wanted to fix.

Although the idea of MarmoMind initiated in early years of my Ph.D., I objectified MarmoMind in May 2026, just after finishing my Ph.D. in April 2026. It pulls together skills I had built up separately over the years (my B.Sc. in electronics engineering [4.5 year], my M.Sc. in medical data engineering (biomedical Eng) [3 years], and my Ph.D. in computational neuroscience [4.5 years]) and had never combined in one place. None of those skills on their own solved the problem in front of me. Putting these skills together, around a problem I had actually lived, did.

I am not claiming nobody has ever automated data analysis pipelines. What is mine is the
origin and the approach: this grew out of a problem I faced firsthand at the
lab, and I designed and implemented it in my own way, with my own experience in working with live animal subjects and my own judgement about where a human must stay in the loop. The design decisions throughout are mine; I directed and reasoned through the whole architecture.

## The governing principle

Log and convert every run first; judge quality after. Scanner time was already
spent, so every functional run gets logged to the summary sheet and converted to NIfTI no
matter how it looks. Only the quality judgement is conditional. This means a bad
run is still recorded and still on disk in a standard form and I never silently
lose a run, I only sort it.

## What it does, per session

1. Detect a ready session. It watches the DICOM folder and the regressor folder (Condition onsets)
   and waits until both have arrived and the folders have gone quiet, so it never
   acts on a half-transferred run. (in the next versions, the MarmoMind will be able to connect the data management server and download the raw data herself (she is a female agent!))
2. Parse the raw DICOM filenames and infer run order. It collects the series
   numbers, sorts them, and assigns the smallest to the phase-reverse (`ap`) and
   the rest to `r1, r2, r3...`. The order is inferred every time, never hardcoded,
   because the absolute series numbers change between sessions and subjects. This was the standard format I used for labeling the raw data.
3. Identify the monkey and look it up in the lab sheet to get its ID and its
   per-monkey tab. (in the next versions, MarmoMind will be able to be directly connected the GoogleSheet where we typically saved the information of the subjects)
4. Work out the next session number by reading the last one already in the sheet.
   The MarmoMind is not the only writer, so it continues the existing sequence rather
   than counting its own runs.
5. Read each run's note, matched by monkey ID, run number, and date, and
   understand the free-text comment by **meaning**.
6. Check the regressors. It compares the condition names in the note against the
   `.1D` filenames present and reports anything missing, extra, or mismatched. It
   only ever compares filenames; it does not open a regressor file to see or investigate what is inside it.
7. Convert every run with `dcm2niix` into `Raw_Nifti_Data_<DATE>/`. There is
   exactly one NIfTI per run — a run is one continuous timeseries — named
   `m{ID}_s{session}_r{run}.nii`, with the phase-reverse as `m{ID}_s{session}_ap.nii`.
8. Cross-check volumes. It reads the true volume count from the converted NIfTI
   and compares it to the count in the note. If they disagree it logs the real
   number and raises a warning, because the gap might be a typo by the experimenter or it might be a
   truncated run whose regressors no longer line up with the data, leading to failed analysis.
9. Log one row per functional run to the summary sheet, using the real volume count.
10. Run a lightweight motion tripwire (`mcflirt` relative RMS displacement). This
    is numbers only. If the value is unusually high it adds a "recommend a visual
    check in FSLeyes" flag (the work I and my teammate typically did to ensure the quality of fMRI data). It is never a standalone verdict and it never asserts
    that an artefact exists. It will be my own assessment for those runs that indicate the next step.
11. Basd on the notes, MarmoMind will judge each functional run and sort it: clean goes to the main folder,valid-but-compromised goes to a separate `review/` folder, broken stays filed
    but flagged skip-analysis, and a genuinely unclear case is flagged and deferred to me rather than guessed.

## How it is built

Almost all of MarmoMind is plain, deterministic Python. The folder watching, filename parsing, sheet reads and writes, conversion, the motion
check, the file moves, and the approval gates are ordinary code that does the
same thing every time.

**The place I use a language model** in this version (V1 so far; June 2026) is the quality judgement itself. That is the step that genuinely needs to read a sentence like "the code failed at volume 200"
and understand that it means the run is broken, not merely noisy. The judge reasons
over the note's comment and experiment description together with the numeric
outputs it is handed (the regressor check, the volume cross-check, the motion
number she already checked) and returns one of clean, compromised, broken, or ambiguous, with a written logical reason. It runs through *`claude-agent-sdk`* (Anthropic's Agent SDK). If the model is
unreachable it falls back to a transparent rule and says so, so the pipeline never
breaks.

It runs in two modes, and only the gate behaviour differs:
1. review mode stops and waits for my Y/N before every step such as conversion, sheet write, and file moves. This is for close supervision .
2.auto mode does the whole job across every ready run without pausing, then hands
  me a single report at the end listing everything it did and every flag it
  raised. I stay in the loop through that report and the `review/` folder, not
  through per-step clicks.

A note on flags versus blockers, because the distinction matters. A flag(a
compromised sort, a volume mismatch, elevated motion, a regressor issue, a broken
run) never change the pipeline. The run is still logged, converted, and filed, and
the flag is recorded for me. Only genuinely irreversible actions are gated by
approval, and only in review mode.

## not exactly real-time because of the experimenter

In practice, each raw data is uploaded to the data management server immediately and is accessible if MarmoMind have access to the server in future versions. However, without access to the server, I might be able to upload every two or three runs/sessions in a folder where MarmoMind has access to it. So she is built to process whatever has accumulated in a predefined folder. it handles a backlog of
several sessions in one run, oldest first, telling them apart by acquisition date.

## What it will not do

These are the boundaries I designed in on purpose (using AI responsibly and morally), and they hold in both modes:
- It recommends; it does not reject. It sorts runs and explains itself, but it
  never throws data away and never decides the final analysis set. That is mine.
- It never pools runs into an analysis on its own.
- It reasons over text and numbers, never images. It has no tool that hands it a
  brain image for this version, so it cannot pretend to have looked at data. The motion check gives
  it a number to reason about, not a picture.
- When it is genuinely unsure, it says so and defers, rather than inventing an
  answer to look decisive.

## Two knowledge sources, kept separate

- The judge's reasoning principles live in its own instructions
  (`marmomind/judge.py`) and in the agent's identity (`marmomind/system_prompt.py`).
- The editable lab knowledge lives in `config/lab_rules.yaml`: the naming
  convention, the motion threshold, a few illustrative keyword cues (clearly
  marked as calibration, not matching rules), and a general fact about arousal
  being paradigm-dependent. The judge reasons from the meaning of my notes first;
  the lab rules only calibrate it.

## Setup and running it

```bash
pip install -r requirements.txt

# Authentication for the one model step. The tested setup uses my Claude
# subscription through the CLI, so that is the primary path:
claude login                               # primary: sign in with the Claude CLI

# Alternative, if you would rather use an API key than the subscription:
# export ANTHROPIC_API_KEY="sk-ant-..."
```

The external binaries are called by full path from `config/settings.yaml`:
`dcm2niix` (which ships inside FSL) and `mcflirt` (FSL). Version 1 logs to a local
copy of the lab sheet; a live Google Sheet swaps in later behind the same tool
interface.

To run against real data:

```bash
python -m marmomind.agent --mode review    # stop-and-wait (default)
python -m marmomind.agent --mode auto      # do-all-then-report
python -m marmomind.agent --paths          # show the resolved data paths
```

To try it end-to-end on entirely synthetic data, with fake monkeys and a demo
sheet and nothing real involved:

```bash
bash fixtures/synthetic/run_demo.sh        # runs the full pipeline in auto mode
```

## Limitations

I would rather state these plainly than let them surprise anyone.

- Motion values need calibration. The `mcflirt` relative-RMS numbers I am getting,
  on both real and synthetic data, come out far higher than is physically
  plausible for a head-fixed marmoset. The threshold (0.2 mm) is a reasoned
  starting point, anchored to a published figure for Everling lab's restraint system,
  but the metric and that figure are not the same measurement. Before I trust the
  motion flag in production I need to look at the runs in FSLeyes and check how
  mcflirt is being invoked. Today the motion flag fires on essentially every run,
  which is why it only ever recommends a visual check and never decides anything.
- The arousal knowledge lives in two places. The human-readable version is in the
  `lab_rules.yaml` header; the version the model actually reads is in the judge's
  instructions. The keyword lists in `lab_rules.yaml` currently only feed the
  offline fallback, not the model. So the editable lab file is not yet the single
  source the judge consumes. Reconciling that is a clear next cleanup.
- The judgement step is a language model, so on genuinely borderline runs it is
  not perfectly reproducible. It tends to surface those as ambiguous rather than
  flip-flop silently, but I want to be upfront that it is not deterministic.
- Version 1 is functional runs only (no anatomical handling), one subject per run
  (it does handle a multi-session backlog), and a local spreadsheet rather than a
  live one.

## Built to grow in phases

I designed MarmoMind to be released and upgraded step by step, not as a finished
product. Version 1 is the foundation: getting the data handled correctly and the
quality judgement trustworthy and honest. The later phases build on top of that:

- the preprocessing analysis and GLM pipeline, so it does not stop at pre-preprocessing steps;
- group-level analysis across sessions and animals;
- a live Google Sheet instead of a local copy;
- judgement grounded in the literature, not only in Everling lab rules;
- automated generation of the run notes themselves;
- and direct ingestion from CFMM lab's data-management system, so I do not stage
  files by hand.

## Status

Version 1 is built and has run a full real session end to end( detecting, logging,
converting, volume-checking, regressor-checking, motion-checking, judging, and sorting) as well as
a fully synthetic demo. The logic is tested.

## A note on data and distribution

Although MarmoMind was developed, built and tested on real data, no real animal data, no real lab sheet, and no credentials live in this repository for ethical rules. The public demo is entirely synthetic.


