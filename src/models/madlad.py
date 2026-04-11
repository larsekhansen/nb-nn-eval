"""
MADLAD-400 adapter (google/madlad400-*).

MADLAD-400 is a T5-style multilingual translation model covering 400+
languages. The target language is selected by a `<2xx>` prefix token
in the input, e.g. `<2nn> Hei`.

The 3B-mt variant is the smallest MT checkpoint and is still ~6GB.
"""
import time

from .base import Model


class MADLAD(Model):
    def __init__(self, hf_name: str, target_lang: str = "nn"):
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        from .device import get_device
        self.device = get_device()
        self.hf_name = hf_name
        self.display_name = f"MADLAD ({hf_name.split('/')[-1]})"
        self.target_lang = target_lang

        t0 = time.time()
        self.tokenizer = AutoTokenizer.from_pretrained(hf_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(hf_name).to(self.device)
        self.model.eval()
        self.param_count = _format_params(self.model.num_parameters())
        print(f"  loaded in {time.time() - t0:.1f}s, {self.param_count} params, device={self.device}", flush=True)

    def translate(self, text: str, direction: str = "nb-nn") -> str:
        lang = "nn" if direction == "nb-nn" else "nb"
        prefixed = f"<2{lang}> {text}"
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
