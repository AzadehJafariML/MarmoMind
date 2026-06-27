# MarmoMind : An Agentic AI designed and built by Azadeh Jafari (jfr.azadeh@gmail.com).
# Created May 2026. Developed during my Ph.D. research in computational neuroscience.
# See README for the published protocol this work builds on.
"""Generate the SYNTHETIC, PUBLISHABLE MarmoMind fixture. Fully reproducible.

EVERYTHING here is fake: fake monkey names (Pixel/m90, Quasar/m91 — NOT real lab
animals), fake conditions, and small SYNTHETIC 4-D DICOMs (real, dcm2niix-
convertible — not lab data). It lets a fresh clone run the whole pipeline
end-to-end against a DEMO sheet with no real or external data anywhere.

Layout produced (current conventions):
  incoming_dicom/                 Pixel multi-slice 4-D series (ap + r1/r2/r3)
  incoming_regressors/m90_20231025/{Condition}_r{N}.1D     (session subfolder)
  notes/m90_run{1,2,3}_20231025.yaml
  demo_sheet.xlsx                 Summary + per-monkey tabs (the published sheet)

Regenerate with:  python fixtures/synthetic/make_fixture.py
Requires (fixture-gen only): pydicom, numpy, openpyxl, pyyaml.
"""
import shutil
from pathlib import Path

import numpy as np
import openpyxl
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid, MRImageStorage

ROOT = Path(__file__).resolve().parent
SUBJECT, MID, DATE, ISO = "Pixel", "m90", "20231025", "2023-10-25"
CONDITIONS = ["Vocal", "Nonvocal"]
# series number -> (run label, n_volumes)
SERIES = {80001: ("ap", 3), 140001: ("r1", 6), 180001: ("r2", 6), 200001: ("r3", 6)}
N, NSLICE = 16, 4
HDR = ("# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the\n"
       "# Everling Lab, Centre for Functional and Metabolic Mapping, University of\n"
       "# Western Ontario. Created May 2026.\n")

# Auditory paradigm; comments chosen to exercise clean / broken / compromised sorts.
NOTES = {
    1: {"comments": "fully awake and attentive throughout; clean run"},
    2: {"comments": "the stimulus code crashed around volume 3; run did not complete as designed"},
    3: {"comments": "animal was a little restless partway through"},
}


def _gen_series(out_dir: Path, series: int, n_vol: int) -> None:
    study_uid, series_uid = generate_uid(), generate_uid()
    cube = np.zeros((N, N, NSLICE), np.int16)
    cube[4:12, 4:12, 1:3] = 800                       # a stable feature for registration
    inst = 0
    for t in range(n_vol):
        vol = (cube + np.random.default_rng(t).integers(0, 8, cube.shape)).astype(np.int16)
        for z in range(NSLICE):
            inst += 1
            fm = FileMetaDataset()
            fm.MediaStorageSOPClassUID = MRImageStorage
            fm.MediaStorageSOPInstanceUID = generate_uid()
            fm.TransferSyntaxUID = ExplicitVRLittleEndian
            ds = FileDataset(None, {}, file_meta=fm, preamble=b"\0" * 128)
            ds.PatientName = SUBJECT
            ds.PatientID = SUBJECT
            ds.Modality = "MR"
            ds.SeriesNumber = series
            ds.InstanceNumber = inst
            ds.StudyInstanceUID = study_uid
            ds.SeriesInstanceUID = series_uid
            ds.SOPClassUID = MRImageStorage
            ds.SOPInstanceUID = fm.MediaStorageSOPInstanceUID
            ds.Rows, ds.Columns = N, N
            ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
            ds.ImagePositionPatient = [0.0, 0.0, float(z * 2)]
            ds.SliceThickness = 2.0
            ds.SliceLocation = float(z * 2)
            ds.PixelSpacing = [1.5, 1.5]
            ds.SamplesPerPixel = 1
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.BitsAllocated = 16
            ds.BitsStored = 16
            ds.HighBit = 15
            ds.PixelRepresentation = 0
            ds.NumberOfTemporalPositions = n_vol
            ds.TemporalPositionIdentifier = t + 1
            ds.AcquisitionNumber = t + 1
            ds.PixelData = vol[:, :, z].tobytes()
            h = f"{series:06d}{inst:04d}"
            name = f"{SUBJECT}^^^^.MR.Everling^Marmoset.{series}.1.{DATE}.{h}.dcm"
            ds.save_as(out_dir / name, enforce_file_format=True)


def _write_notes(notes_dir: Path) -> None:
    for run, info in NOTES.items():
        body = (f"{HDR}\n"
                f"monkey:     {SUBJECT}\n"
                f"run:        {run}\n"
                f"experiment: Auditory\n"
                f"description: >\n"
                f"  Auditory run; only auditory stimuli are presented in a pseudorandom\n"
                f"  order while the marmoset rests quietly.\n"
                f"conditions:\n" + "".join(f"  - {c}\n" for c in CONDITIONS) +
                f"state:      awake\n"
                f"time_in:    \"11:00:00\"\n"
                f"time_out:   \"11:12:00\"\n"
                f"task:       \"vocalization\"\n"
                f"comments:   \"{info['comments']}\"\n"
                f"volumes:    6\n"
                f"coil:       \"8channel coil\"\n"
                f"tr:         \"1,5\"\n"
                f"resolution: \"1.0 mm iso\"\n")
        (notes_dir / f"{MID}_run{run}_{DATE}.yaml").write_text(body)


def _build_demo_sheet(path: Path) -> None:
    summary_cols = ["Animal name", "ID", "Sheet name", "Date of birth",
                    "Date of Perfus", "Sex", "Injection"]
    run_cols = ["Session", "Date of scan", "State of the animal", "Time In",
                "Time Out", "Run", "Volumes", "Resolution", "TR", "Coils", "Task", "Comments"]
    animals = [("Pixel", "m90", "m90_Pixel", "1/1/2021", "", "Male", ""),
               ("Quasar", "m91", "m91_Quasar", "2/2/2021", "", "Female", "")]

    wb = openpyxl.Workbook()
    sm = wb.active
    sm.title = "Summary"
    sm.append(summary_cols)
    for a in animals:
        sm.append(list(a))

    def sample_rows(n_sessions):
        rows = []
        for s in range(1, n_sessions + 1):
            rows.append([f"s{s}", "2023-09-%02d" % s, "awake", "10:00:00", "10:12:00",
                         "r1", 6, "1.0 mm iso", "1,5", "8channel coil", "vocalization", "clean"])
            rows.append(["", "", "", "", "", "r2", 6, "1.0 mm iso", "1,5",
                         "8channel coil", "vocalization", ""])
        return rows

    for name, sheet, n in [("m90_Pixel", "m90_Pixel", 5), ("m91_Quasar", "m91_Quasar", 3)]:
        ws = wb.create_sheet(sheet)
        ws.append(run_cols)
        for row in sample_rows(n):
            ws.append(row)
    wb.save(path)


def main() -> None:
    dicom = ROOT / "incoming_dicom"
    regs = ROOT / "incoming_regressors"
    notes = ROOT / "notes"
    for d in (dicom, regs, notes):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    for series, (label, n_vol) in SERIES.items():
        _gen_series(dicom, series, n_vol)

    sess_dir = regs / f"{MID}_{DATE}"            # session subfolder (current convention)
    sess_dir.mkdir(parents=True)
    for label, _ in [v for v in SERIES.values() if v[0].startswith("r")]:
        run = label[1:]
        for cond in CONDITIONS:
            (sess_dir / f"{cond}_r{run}.1D").write_text("12.0\n45.5\n78.0\n101.2\n")

    _write_notes(notes)
    _build_demo_sheet(ROOT / "demo_sheet.xlsx")
    print(f"fixture written under {ROOT}")
    print(f"  DICOMs: {len(list(dicom.glob('*.dcm')))} files (Pixel, 4 series)")
    print(f"  regressors: {len(list(sess_dir.glob('*.1D')))} .1D in {sess_dir.name}/")
    print(f"  notes: {len(list(notes.glob('*.yaml')))}   demo_sheet.xlsx: Summary + 2 tabs")


if __name__ == "__main__":
    main()
