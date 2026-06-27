# MarmoMind: AI Agent designed by Azadeh Jafari (jfr.azadeh@gmail.com) for the
# Everling Lab, Centre for Functional and Metabolic Mapping, University of
# Western Ontario. Created May 2026.
#
# Shared helpers: portable path resolution, config loading, tool return shaping.
# Not agent logic — pure infrastructure used by the deterministic tools.

import os
import json
import functools
from pathlib import Path

import yaml

# PROJECT ROOT resolved from THIS file's location, so MarmoMind is fully portable
# — wherever a student unpacks the folder, the root is found automatically with no
# absolute paths and no guessing. common.py lives at <root>/marmomind/common.py,
# so the project root is two levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=1)
def load_settings() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "config" / "settings.yaml").read_text())


@functools.lru_cache(maxsize=1)
def load_lab_rules() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "config" / "lab_rules.yaml").read_text())


def resolve(p) -> Path:
    """Absolute path stays as-is; a relative one is anchored to PROJECT_ROOT."""
    p = Path(p)
    return p if p.is_absolute() else PROJECT_ROOT / p


# Logical path name -> (settings section, key). Defaults in settings.yaml are
# project-relative; an absolute value there (or the env override) wins for
# production (e.g. real scanner directories).
_PATHS = {
    "incoming_dicom":      ("paths", "incoming_dicom"),
    "incoming_regressors": ("paths", "incoming_regressors"),
    "notes":               ("paths", "notes"),
    "output_root":         ("paths", "output_root"),
    "xlsx":                ("sheet", "xlsx_path"),
    "logs":                ("logging", "audit_dir"),
}


def data_path(name: str) -> Path:
    """Resolve a logical path. Precedence: env MARMOMIND_<NAME> > settings.yaml >
    project-relative default. The result is always absolute."""
    section, key = _PATHS[name]
    override = os.environ.get("MARMOMIND_" + name.upper())
    raw = override if override else load_settings()[section][key]
    return resolve(raw)


def resolved_paths() -> dict:
    """Every resolved path (plus PROJECT_ROOT) — for the --paths printout."""
    out = {"PROJECT_ROOT": PROJECT_ROOT}
    for name in _PATHS:
        out[name] = data_path(name)
    return out


def ok(data: dict) -> dict:
    """Wrap a structured result as the agent-readable tool return."""
    return {"content": [{"type": "text", "text": json.dumps(data, default=str, indent=2)}]}


def fail(message: str, **extra) -> dict:
    """Soft error: the agent reads it and continues — tools NEVER crash the loop."""
    payload = {"error": message, **extra}
    return {"content": [{"type": "text", "text": json.dumps(payload, default=str, indent=2)}],
            "is_error": True}
