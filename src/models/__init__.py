"""
Model registry.

Each model is lazy-loaded — the weights aren't touched until the first
translation request. This keeps startup fast and keeps memory low when
you only want to test one model.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List

from .base import Model
from .nllb import NLLB
from .marian import Marian
from .navjordj import NavjordjT5
from .madlad import MADLAD
from .pere import PereNbNn
from .normistral import NorMistralTranslate, NorMistralInstruct
from .apertium import Apertium
from .llm_api import OpenAIModel, AnthropicModel


# Key → factory. Factories are called lazily when the model is first used.
# Add new models here. Keep keys short and stable — they're part of the URL.
REGISTRY: Dict[str, Callable[[], Model]] = {
    # ── Norwegian-specific translation models ────────────────────
    # pere/nb-nn-translation — T5-base, most-downloaded nb→nn on HF.
    # Uses tokenizer from pere/norwegian-t5-base-NCC-fast (the repo's
    # own tokenizer files are broken LFS pointers).
    "pere-nb-nn": lambda: PereNbNn(),
    # navjordj T5 nb→nn (generally poor quality, kept for comparison).
    "navjordj-t5": lambda: NavjordjT5("navjordj/t5_nb_nn"),
    # Apertium rule-based nob→nno. Requires Docker:
    #   docker run -d -p 2737:2737 apertium/apy
    "apertium": lambda: Apertium(),

    # ── Norwegian LLMs (generative, prompt-based) ────────────────
    # NorMistral-11b-translate — UiO, fine-tuned for translation.
    # Best on nynorsk grammar per Språkrådet 2025. ~22GB.
    "normistral-translate": lambda: NorMistralTranslate(
        "norallm/normistral-11b-translate",
        display="NorMistral 11B translate",
    ),
    # NorMistral-7b-instruct — smaller, faster for iterating.
    "normistral-7b": lambda: NorMistralInstruct(
        "norallm/normistral-7b-warm-instruct",
        display="NorMistral 7B instruct",
    ),

    # ── Multilingual translation models ──────────────────────────
    # NLLB family: native nob_Latn ↔ nno_Latn support.
    "nllb-600M": lambda: NLLB("facebook/nllb-200-distilled-600M"),
    "nllb-1.3B": lambda: NLLB("facebook/nllb-200-distilled-1.3B"),
    "nllb-3.3B": lambda: NLLB("facebook/nllb-200-3.3B"),
    # Helsinki North Germanic Marian (smallest, fastest).
    "marian-gmq": lambda: Marian("Helsinki-NLP/opus-mt-gmq-gmq", target_token=">>nno<<"),
    # MADLAD-400 — Google multilingual (400+ languages). ~12GB.
    "madlad-3b": lambda: MADLAD("google/madlad400-3b-mt", target_lang="nn"),

    # ── Closed-source / API models ───────────────────────────────
    # Set API keys in .env at project root or as env vars.
    "gpt-4o": lambda: OpenAIModel("gpt-4o"),
    "gpt-4.1-mini": lambda: OpenAIModel("gpt-4.1-mini"),
    "claude-sonnet": lambda: AnthropicModel("claude-sonnet-4-20250514"),
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


def _check_available(key: str) -> tuple:
    """Lightweight check if a model can be loaded (without loading it).
    Returns (available: bool, reason: str | None)."""
    import urllib.request
    if key in ("gpt-4o", "gpt-4.1-mini"):
        if os.environ.get("OPENAI_API_KEY"):
            return True, None
        return False, "OPENAI_API_KEY mangler i .env"
    if key == "claude-sonnet":
        if os.environ.get("ANTHROPIC_API_KEY"):
            return True, None
        return False, "ANTHROPIC_API_KEY mangler i .env"
    if key == "apertium":
        url = os.environ.get("APERTIUM_URL", "http://localhost:2737")
        try:
            urllib.request.urlopen(f"{url}/listPairs", timeout=2)
            return True, None
        except Exception:
            return False, "Apertium APY ikkje tilgjengeleg (docker run -d -p 2737:2737 apertium/apy)"
    return True, None


# Model display metadata (shown before loading).
_META: Dict[str, dict] = {
    "pere-nb-nn":             {"display_name": "pere/nb-nn-translation", "group": "Norsk-spesifikke", "size": "~1 GB", "speed": "~0.5s/setning", "supports_reverse": False},
    "navjordj-t5":            {"display_name": "navjordj T5 nb-nn", "group": "Norsk-spesifikke", "size": "~2.4 GB", "speed": "~1s/setning", "supports_reverse": False},
    "apertium":               {"display_name": "Apertium (regelbasert)", "group": "Norsk-spesifikke", "size": "Docker", "speed": "~0.1s/setning"},
    "normistral-translate":   {"display_name": "NorMistral 11B translate", "group": "Norske LLM-ar", "size": "~22 GB", "speed": "~30-60s/setning", "warning": "Stor modell — treg på CPU"},
    "normistral-7b":          {"display_name": "NorMistral 7B instruct", "group": "Norske LLM-ar", "size": "~14 GB", "speed": "~15-30s/setning", "warning": "Stor modell — treg på CPU"},
    "nllb-600M":              {"display_name": "NLLB 600M", "group": "Fleirspråklege", "size": "~2.4 GB", "speed": "~1s/setning"},
    "nllb-1.3B":              {"display_name": "NLLB 1.3B", "group": "Fleirspråklege", "size": "~5 GB", "speed": "~3s/setning"},
    "nllb-3.3B":              {"display_name": "NLLB 3.3B", "group": "Fleirspråklege", "size": "~13 GB", "speed": "~10s/setning"},
    "marian-gmq":             {"display_name": "Marian gmq-gmq", "group": "Fleirspråklege", "size": "~300 MB", "speed": "~0.5s/setning"},
    "madlad-3b":              {"display_name": "MADLAD-400 3B", "group": "Fleirspråklege", "size": "~12 GB", "speed": "~10s/setning"},
    "gpt-4o":                 {"display_name": "GPT-4o", "group": "API (lukka kjeldekode)", "size": "API", "speed": "~1-2s/setning"},
    "gpt-4.1-mini":           {"display_name": "GPT-4.1-mini", "group": "API (lukka kjeldekode)", "size": "API", "speed": "~0.5s/setning"},
    "claude-sonnet":          {"display_name": "Claude Sonnet", "group": "API (lukka kjeldekode)", "size": "API", "speed": "~1-2s/setning"},
}


def list_models() -> List[dict]:
    """Return metadata about every registered model (loaded or not)."""
    out = []
    for key in REGISTRY:
        m = _loaded.get(key)
        meta = _META.get(key, {})
        available, reason = _check_available(key)
        out.append({
            "key": key,
            "loaded": m is not None,
            "available": available,
            "unavailable_reason": reason,
            "display_name": m.display_name if m else meta.get("display_name", key),
            "group": meta.get("group", ""),
            "hf_name": m.hf_name if m else None,
            "param_count": m.param_count if m else None,
            "supports_reverse": m.supports_reverse if m else meta.get("supports_reverse", True),
            "size": meta.get("size", ""),
            "speed": meta.get("speed", ""),
            "warning": meta.get("warning", ""),
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
