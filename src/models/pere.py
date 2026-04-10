"""
pere/nb-nn-translation adapter — T5-base fine-tuned for nb→nn.

The model's own HF repo has broken config files (Git LFS pointers that
never resolved). The fix: load the tokenizer from the BASE model
`pere/norwegian-t5-base-NCC-fast` (which has a working tokenizer.json
with 50103 tokens matching the model's embedding table) and the weights
from `pere/nb-nn-translation`.

Quality is modest — the model was trained on the Norwegian Colossal
Corpus and fine-tuned with Flax. The PyTorch conversion may have
artifacts. Still worth including as it's the most-downloaded
Norwegian-specific nb→nn model on HF.
"""
from __future__ import annotations

import time

from .base import Model


class PereNbNn(Model):
    def __init__(self):
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        self.hf_name = "pere/nb-nn-translation"
        self.display_name = "Pere nb-nn (T5-base)"

        t0 = time.time()
        # Tokenizer from the base model — the one in nb-nn-translation is broken.
        self.tokenizer = AutoTokenizer.from_pretrained("pere/norwegian-t5-base-NCC-fast")
        self.model = AutoModelForSeq2SeqLM.from_pretrained("pere/nb-nn-translation")
        self.model.eval()
        self.param_count = _format_params(self.model.num_parameters())
        print(f"  loaded in {time.time() - t0:.1f}s, {self.param_count} params", flush=True)

    def translate(self, text: str) -> str:
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
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
