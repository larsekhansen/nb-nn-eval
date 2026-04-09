"""
Base class for translation models.

All models in the registry implement the same tiny interface: give it
bokmål text, get back nynorsk. Subclasses handle their own tokenizer
quirks, language tokens and prefix formats.
"""
from abc import ABC, abstractmethod


class Model(ABC):
    hf_name: str
    display_name: str
    param_count: str  # Human-readable, e.g. "600M"

    @abstractmethod
    def translate(self, text: str) -> str:
        ...
