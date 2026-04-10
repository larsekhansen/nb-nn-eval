"""
NorMistral adapter — Norwegian Mistral models from UiO/NorAllm.

NorMistral-11b scored best on nynorsk grammar in Språkrådet's 2025
evaluation. There's also a `normistral-11b-translate` variant
specifically fine-tuned for translation.

These are generative (causal) LLMs, not seq2seq models. Translation is
done via prompting. The 11B models are ~22 GB and SLOW on CPU — plan
for 30-60+ seconds per sentence. Consider using the 7b-instruct
variant for faster iteration.

Available variants registered:
  - normistral-translate  → norallm/normistral-11b-translate (translation fine-tune)
  - normistral-7b         → norallm/normistral-7b-warm-instruct (smaller, faster)
"""
from __future__ import annotations

import time

from .base import Model


class NorMistral(Model):
    def __init__(self, hf_name: str, display: str | None = None):
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        from .device import get_device

        self.hf_name = hf_name
        self.display_name = display or f"NorMistral ({hf_name.split('/')[-1]})"
        self.device = get_device()

        t0 = time.time()
        self.tokenizer = AutoTokenizer.from_pretrained(hf_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            hf_name,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        ).to(self.device)
        self.model.eval()
        self.param_count = _format_params(self.model.num_parameters())

        # Pad token fallback (common for Mistral-based models).
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        print(f"  loaded in {time.time() - t0:.1f}s, {self.param_count} params", flush=True)

    def translate(self, text: str) -> str:
        prompt = (
            "Oversett følgende tekst fra bokmål til nynorsk.\n\n"
            f"Bokmål: {text}\n\n"
            "Nynorsk:"
        )

        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        input_len = inputs["input_ids"].shape[1]

        output = self.model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=False,
            num_beams=1,
            repetition_penalty=1.2,
        )

        generated = output[0][input_len:]
        result = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        # Strip any trailing continuation the model might add.
        for stop in ["\n\nBokmål:", "\nBokmål:", "\n\n"]:
            if stop in result:
                result = result[:result.index(stop)]
        return result.strip()


def _format_params(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    return str(n)
