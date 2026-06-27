MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
Everling Lab, Centre for Functional and Metabolic Mapping, University of
Western Ontario. Created May 2026.

# Synthetic fixture (publishable)

A fully **synthetic, self-contained** demo — **no real or external data**. Fake
monkey names (Pixel/m90, Quasar/m91 — not real lab animals), fake conditions, and
small **real, dcm2niix-convertible** 4-D DICOMs. A fresh clone can run the entire
pipeline end-to-end against a **demo sheet** without touching any real data.

## Run it

```bash
bash fixtures/synthetic/run_demo.sh          # auto mode (do-all-then-report)
bash fixtures/synthetic/run_demo.sh review   # stop-and-wait at each gate
```

`run_demo.sh` is the demo profile: it points the `MARMOMIND_*` path overrides at
this fixture + `demo_sheet.xlsx`, and sends all outputs (and a working copy of the
sheet) to a throwaway temp dir, so the committed fixture stays pristine.

## Regenerate

```bash
python fixtures/synthetic/make_fixture.py    # needs pydicom, numpy, openpyxl, pyyaml
```

## Contents — one session, subject "Pixel" (m90), date 2023-10-25

| Series | Label | Volumes | Conditions (note) | Regressor `.1D` | Note |
|--------|-------|---------|-------------------|-----------------|------|
| 80001  | ap    | 3 | — | — | none (ap is never noted) |
| 140001 | r1    | 6 | Vocal, Nonvocal | `Vocal_r1.1D`, `Nonvocal_r1.1D` | `m90_run1_20231025.yaml` (clean run) |
| 180001 | r2    | 6 | Vocal, Nonvocal | `Vocal_r2.1D`, `Nonvocal_r2.1D` | `m90_run2_20231025.yaml` (code crashed) |
| 200001 | r3    | 6 | Vocal, Nonvocal | `Vocal_r3.1D`, `Nonvocal_r3.1D` | `m90_run3_20231025.yaml` (restless) |

Regressors use the **current layout** — one session subfolder
`incoming_regressors/m90_20231025/` holding `{Condition}_r{N}.1D`.

What the demo run exercises (expected sorts):
- **run-order inference** — smallest series (80001) → `ap`; the rest → r1, r2, r3.
- **r1 → clean** — awake/attentive, regressors clean, volumes match.
- **r2 → broken** — comment "the stimulus code crashed" → events after invalid
  (still logged + converted + filed, flagged skip-analysis).
- **r3 → compromised** — "restless" → kept but sorted to `review/`.
- **volume cross-check, regressor sanity, and the motion tripwire** all run.

`demo_sheet.xlsx` is the **published** sheet: a `Summary` tab (Pixel/m90,
Quasar/m91) plus `m90_Pixel` and `m91_Quasar` per-monkey tabs with the real column
structure and a few sample sessions. The real lab sheet is **not** published.

> NOTE on motion: the synthetic images are tiny, so mcflirt reports a few mm of
> relative RMS — above the 0.2 mm threshold, so every run gets a "recommend visual
> inspection" flag. That is expected for synthetic data and is a flag, not an error.
