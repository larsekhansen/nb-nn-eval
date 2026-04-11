"""
Base class for translation models.

All models implement translate(text, direction). Direction is either
"nb-nn" (bokmål→nynorsk) or "nn-nb" (nynorsk→bokmål).

Models that only support one direction should set supports_reverse = False
and raise ValueError if called with the wrong direction.
"""
from abc import ABC, abstractmethod


class Model(ABC):
    hf_name: str
    display_name: str
    param_count: str  # Human-readable, e.g. "600M"
    supports_reverse: bool = True  # Override to False for nb→nn-only models

    @abstractmethod
    def translate(self, text: str, direction: str = "nb-nn") -> str:
        ...
