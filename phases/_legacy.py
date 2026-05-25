"""Backward-compatible imports for legacy ``phase_*`` module paths."""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys

_LEGACY_PREFIXES = (
    "phase_01_multimodal_ingestion",
    "phase_02_long_doc_retrieval",
    "phase_03_scalable_ingestion",
    "phase_04_taxonomy_generation",
    "phase_05_evaluation",
    "phase_06_production",
)


class _LegacyPhaseLoader(importlib.abc.Loader):
    def __init__(self, fullname: str, real_name: str) -> None:
        self.fullname = fullname
        self.real_name = real_name

    def exec_module(self, module) -> None:
        real = importlib.import_module(self.real_name)
        module.__dict__.update(real.__dict__)
        module.__name__ = self.fullname
        module.__file__ = getattr(real, "__file__", None)
        module.__path__ = getattr(real, "__path__", None)
        module.__package__ = self.fullname.rpartition(".")[0] or self.fullname
        module.__loader__ = self
        sys.modules[self.fullname] = module


class _LegacyPhaseFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path, target=None):
        for prefix in _LEGACY_PREFIXES:
            if fullname == prefix or fullname.startswith(prefix + "."):
                real_name = f"phases.{fullname}"
                real_spec = importlib.util.find_spec(real_name)
                if real_spec is None:
                    return None
                return importlib.util.spec_from_loader(
                    fullname,
                    _LegacyPhaseLoader(fullname, real_name),
                    is_package=real_spec.submodule_search_locations is not None,
                )
        return None


def install_legacy_imports() -> None:
    if any(isinstance(finder, _LegacyPhaseFinder) for finder in sys.meta_path):
        return
    sys.meta_path.insert(0, _LegacyPhaseFinder())
