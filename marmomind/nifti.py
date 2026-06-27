# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
"""Minimal NIfTI header reader — the TRUE number of volumes from the data.

No nibabel dependency: parse the NIfTI-1 header directly (dim field at byte 40).
Handles plain .nii and gzipped .nii.gz.
"""
import gzip
import struct
from pathlib import Path


def read_volumes(path) -> int:
    """Return the number of volumes (dim[4]) in a NIfTI file, or None if it can't
    be read. A 3-D image (single volume) returns 1."""
    p = str(path)
    opener = gzip.open if p.endswith(".gz") else open
    try:
        with opener(p, "rb") as f:
            hdr = f.read(348)
    except OSError:
        return None
    if len(hdr) < 348:
        return None
    sizeof = struct.unpack("<i", hdr[:4])[0]
    endian = "<" if sizeof == 348 else ">"        # 348 little-endian, else byte-swapped
    dim = struct.unpack(endian + "8h", hdr[40:56])
    ndim = dim[0]
    if ndim < 1 or ndim > 7:
        return None
    return dim[4] if ndim >= 4 else 1
