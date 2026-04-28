from __future__ import annotations

import importlib.util
from pathlib import Path

_legacy_path = Path(__file__).resolve().parents[1] / "config.py"
_spec = importlib.util.spec_from_file_location("ai._legacy_config", _legacy_path)
_legacy = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_legacy)

__all__ = []
for _name in dir(_legacy):
    if _name.isupper():
        globals()[_name] = getattr(_legacy, _name)
        __all__.append(_name)
