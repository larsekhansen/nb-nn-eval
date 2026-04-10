"""
pere/nb-nn-translation adapter — T5-base fine-tuned for nb→nn.

The repo's spiece.model is wrong (mT5's 250100-token file instead of
the model's actual 50003-token vocab). This is a known issue:
  https://huggingface.co/pere/nb-nn-translation/discussions/1

The fix: use the FAST tokenizer (use_fast=True, the default), which
reads from tokenizer.json (correct 50003-token Unigram vocab) rather
than the broken spiece.model. Do NOT load with use_fast=False.

The most-downloaded Norwegian-specific nb→nn model on HF (~1500/month).
Quality is good — proper nynorsk forms.
"""
from __future__ import annotations

import time

from .base import Model


class PereNbNn(Model):
    def __init__(self):
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        self.hf_name = "pere/nb-nn-translation"
        self.display_name = "pere/nb-nn-translation"

        from .device import get_device
        self.device = get_device()

        t0 = time.time()
        # Must use use_fast=True (default) to get tokenizer.json, NOT spiece.model.
        # See: https://huggingface.co/pere/nb-nn-translation/discussions/1
        self.tokenizer = AutoTokenizer.from_pretrained("pere/nb-nn-translation")
        self.model = AutoModelForSeq2SeqLM.from_pretrained("pere/nb-nn-translation").to(self.device)
        self.model.eval()
        self.param_count = _format_params(self.model.num_parameters())
        print(f"  loaded in {time.time() - t0:.1f}s, {self.param_count} params, device={self.device}", flush=True)

    def translate(self, text: str) -> str:
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
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
