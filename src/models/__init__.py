"""
Model registry.

Each model is lazy-loaded — the weights aren't touched until the first
translation request. This keeps startup fast and keeps memory low when
you only want to test one model.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from .base import Model
from .nllb import NLLB
from .marian import Marian
from .navjordj import NavjordjT5
from .madlad import MADLAD


# Key → factory. Factories are called lazily when the model is first used.
# Add new models here. Keep keys short and stable — they're part of the URL.
REGISTRY: Dict[str, Callable[[], Model]] = {
    # NLLB family: native support for both nob_Latn and nno_Latn.
    "nllb-600M": lambda: NLLB("facebook/nllb-200-distilled-600M"),
    "nllb-1.3B": lambda: NLLB("facebook/nllb-200-distilled-1.3B"),
    "nllb-3.3B": lambda: NLLB("facebook/nllb-200-3.3B"),
    # Helsinki North Germanic Marian model (smallest, fastest).
    "marian-gmq": lambda: Marian("Helsinki-NLP/opus-mt-gmq-gmq", target_token=">>nno<<"),
    # MADLAD-400 — Google multilingual (400+ languages). Large downloads.
    "madlad-3b": lambda: MADLAD("google/madlad400-3b-mt", target_lang="nn"),
    # Norwegian-specific T5 baseline (generally poor, for comparison).
    "navjordj-t5": lambda: NavjordjT5("navjordj/t5_nb_nn"),
}


_loaded: Dict[str, Model] = {}


def get_model(key: str) -> Model:
    if key not in REGISTRY:
        raise ValueError(f"Unknown model '{key}'. Known: {list(REGISTRY.keys())}")
    if key not in _loaded:
        print(f"[registry] Lazy-loading {key} ...", flush=True)
        _loaded[key] = REGISTRY[key]()
        print(f"[registry] {key} ready", flush=True)
    return _loaded[key]


def list_models() -> List[dict]:
    """Return metadata about every registered model (loaded or not)."""
    out = []
    for key in REGISTRY:
        m = _loaded.get(key)
        out.append({
            "key": key,
            "loaded": m is not None,
            "display_name": m.display_name if m else key,
            "hf_name": m.hf_name if m else None,
            "param_count": m.param_count if m else None,
        })
    return out


def unload(key: str) -> bool:
    if key in _loaded:
        del _loaded[key]
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        return True
    return False
