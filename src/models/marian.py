"""
Marian MT adapter (Helsinki-NLP/opus-mt-*).

Multi-target Marian models (like opus-mt-gmq-gmq, covering North Germanic
languages) need a target-language token at the start of the input,
e.g. `>>nno<< ...`.
"""
from __future__ import annotations

import time

from .base import Model


class Marian(Model):
    def __init__(self, hf_name: str, target_token: str | None = None):
        from transformers import MarianMTModel, MarianTokenizer

        from .device import get_device
        self.device = get_device()
        self.hf_name = hf_name
        self.display_name = f"Marian ({hf_name.split('/')[-1]})"
        self.target_token = target_token

        t0 = time.time()
        self.tokenizer = MarianTokenizer.from_pretrained(hf_name)
        self.model = MarianMTModel.from_pretrained(hf_name).to(self.device)
        self.model.eval()
        self.param_count = _format_params(self.model.num_parameters())
        print(f"  loaded in {time.time() - t0:.1f}s, {self.param_count} params, device={self.device}", flush=True)

    def translate(self, text: str, direction: str = "nb-nn") -> str:
        token = ">>nno<<" if direction == "nb-nn" else ">>nob<<"
        prefixed = f"{token} {text}"
        inputs = self.tokenizer(prefixed, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        output = self.model.generate(
            **inputs,
            max_length=512,
            num_beams=4,
            early_stopping=True,
        )
        return self.tokenizer.decode(output[0], skip_special_tokens=True)


def _format_params(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    return str(n)
