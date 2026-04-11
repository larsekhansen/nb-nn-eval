"""
NorMistral adapter — Norwegian Mistral models from UiO/NorAllm.

Two variants with different prompt formats:

  normistral-translate (norallm/normistral-11b-translate):
    Fine-tuned specifically for translation. Uses a chat template with
    system message "nynorsk" to set target language. Best quality.
    See: https://huggingface.co/norallm/normistral-11b-translate

  normistral-7b (norallm/normistral-7b-warm-instruct):
    General instruct model, translation via free-form prompt.
    Smaller and faster.
"""
from __future__ import annotations

import time

from .base import Model


class NorMistralTranslate(Model):
    """Adapter for normistral-11b-translate (chat-template based)."""

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
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True,
        ).to(self.device)
        self.model.eval()
        self.param_count = _format_params(self.model.num_parameters())

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        print(f"  loaded in {time.time() - t0:.1f}s, {self.param_count} params, device={self.device}", flush=True)

    def translate(self, text: str, direction: str = "nb-nn") -> str:
        target = "nynorsk" if direction == "nb-nn" else "bokmål"
        messages = [
            {"role": "system", "content": target},
            {"role": "user", "content": text},
        ]
        input_tokens = self.tokenizer.apply_chat_template(
            messages, return_tensors="pt",
        ).to(self.device)
        input_len = input_tokens.shape[1]

        output = self.model.generate(
            input_tokens,
            max_new_tokens=2048,
            do_sample=False,
        )

        generated = output[0][input_len:]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()


class NorMistralInstruct(Model):
    """Adapter for normistral-7b-warm-instruct (free-form prompt)."""

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

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        print(f"  loaded in {time.time() - t0:.1f}s, {self.param_count} params, device={self.device}", flush=True)

    def translate(self, text: str, direction: str = "nb-nn") -> str:
        if direction == "nb-nn":
            prompt = f"Oversett følgjande tekst frå bokmål til nynorsk. Returner berre omsetjinga, ingen forklaringar.\n\n{text}"
        else:
            prompt = f"Oversett følgjande tekst frå nynorsk til bokmål. Returner berre oversettelsen, ingen forklaringer.\n\n{text}"
        messages = [
            {"role": "user", "content": prompt},
        ]
        input_tokens = self.tokenizer.apply_chat_template(
            messages, return_tensors="pt", add_generation_prompt=True,
        ).to(self.device)
        input_len = input_tokens.shape[1]

        output = self.model.generate(
            input_tokens,
            max_new_tokens=512,
            do_sample=False,
        )

        generated = output[0][input_len:]
        result = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        # Strip trailing continuation.
        for stop in ["\n\n"]:
            if stop in result:
                result = result[:result.index(stop)]
        return result.strip()


def _format_params(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    return str(n)
