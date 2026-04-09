"""
NLLB-200 adapter (facebook/nllb-200-*).

NLLB uses a src_lang on the tokenizer and a forced_bos_token_id on
generate() to pick the target language. Norwegian bokmål is `nob_Latn`
and nynorsk is `nno_Latn`.
"""
import time

from .base import Model


class NLLB(Model):
    def __init__(self, hf_name: str):
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        self.hf_name = hf_name
        self.display_name = f"NLLB ({hf_name.split('/')[-1]})"

        t0 = time.time()
        self.tokenizer = AutoTokenizer.from_pretrained(hf_name, src_lang="nob_Latn")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(hf_name)
        self.model.eval()
        self.tgt_token_id = self.tokenizer.convert_tokens_to_ids("nno_Latn")
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
            forced_bos_token_id=self.tgt_token_id,
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
