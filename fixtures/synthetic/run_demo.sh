#!/usr/bin/env bash
# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
#
# Demo profile: run the FULL pipeline end-to-end against the SYNTHETIC fixture and
# the DEMO sheet only — no real or external data. Outputs and the working sheet go
# to a throwaway temp dir, so the committed fixture stays pristine.
#
#   bash fixtures/synthetic/run_demo.sh            # auto mode (do-all-then-report)
#   bash fixtures/synthetic/run_demo.sh review     # stop-and-wait at each gate
set -euo pipefail

cd "$(dirname "$0")/../.."                          # repo root
MODE="${1:-auto}"
OUT="$(mktemp -d)"
cp fixtures/synthetic/demo_sheet.xlsx "$OUT/demo_sheet.xlsx"   # write to a copy, not the committed sheet

export MARMOMIND_INCOMING_DICOM="fixtures/synthetic/incoming_dicom"
export MARMOMIND_INCOMING_REGRESSORS="fixtures/synthetic/incoming_regressors"
export MARMOMIND_NOTES="fixtures/synthetic/notes"
export MARMOMIND_XLSX="$OUT/demo_sheet.xlsx"
export MARMOMIND_OUTPUT_ROOT="$OUT"

echo "MarmoMind DEMO — synthetic fixture + demo sheet (outputs in $OUT)"
python3 -m marmomind.agent --mode "$MODE"
echo
echo "Demo outputs written under: $OUT  (safe to delete)"
