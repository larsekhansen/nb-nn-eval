"""
navjordj/t5_nb_nn adapter — T5 fine-tuned for nb→nn.

Included as a baseline for comparison. Quality is poor in our testing
(often copies input unchanged), but it's one of the few Norwegian-
specific HF models that still has working config files.
"""
import time

from .base import Model


class NavjordjT5(Model):
    def __init__(self, hf_name: str):
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        from .device import get_device
        self.device = get_device()
        self.hf_name = hf_name
        self.display_name = f"navjordj T5 ({hf_name.split('/')[-1]})"

        t0 = time.time()
        self.tokenizer = AutoTokenizer.from_pretrained(hf_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(hf_name).to(self.device)
        self.model.eval()
        self.param_count = _format_params(self.model.num_parameters())
        print(f"  loaded in {time.time() - t0:.1f}s, {self.param_count} params, device={self.device}", flush=True)

    supports_reverse = False

    def translate(self, text: str, direction: str = "nb-nn") -> str:
        if direction != "nb-nn":
            raise ValueError("navjordj/t5_nb_nn støttar berre nb→nn")
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
