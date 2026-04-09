# nb-nn-eval

A local playground for evaluating Norwegian Bokmål → Nynorsk machine translation models.

## What it does

- **Playground**: Paste bokmål text, pick one or many models, see them all translate it side-by-side.
- **BLEU evaluator**: Load a parallel nb/nn corpus (from Wikipedia, pasted TSV, or manual entry) and get BLEU + chrF scores for each model.
- **Wikipedia corpus fetcher**: Search nb.wikipedia.org and auto-pull the matching nn.wikipedia.org article via langlinks. Paragraphs are aligned positionally.

All models run locally on CPU. Nothing leaves your machine. No API keys.

## Included models

| Key | Model | Size |
|---|---|---|
| `nllb-600M` | `facebook/nllb-200-distilled-600M` | ~2.4 GB |
| `nllb-1.3B` | `facebook/nllb-200-distilled-1.3B` | ~5.2 GB |
| `nllb-3.3B` | `facebook/nllb-200-3.3B` | ~13 GB |
| `marian-gmq` | `Helsinki-NLP/opus-mt-gmq-gmq` | ~300 MB |
| `madlad-3b` | `google/madlad400-3b-mt` | ~12 GB |
| `navjordj-t5` | `navjordj/t5_nb_nn` | ~2.4 GB |

Models are **lazy-loaded** — nothing is downloaded until you pick a model and hit translate. Once loaded, a model stays in memory until you stop the server.

To add more models, drop a new adapter file in `src/models/` and register it in `src/models/__init__.py`.

## Setup

```bash
cd /Users/lars/projects/nb-nn-eval
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m src.server
```

Open http://localhost:5055 for the playground or http://localhost:5055/eval for the BLEU evaluator.

## BLEU evaluation workflow

1. Open `/eval`
2. Pick the models you want to compare
3. Load a parallel corpus:
   - **Wikipedia**: search for an nb article title, the UI will auto-fetch and paragraph-align the corresponding nn article
   - **TSV paste**: one pair per line, tab-separated: `nb<TAB>nn`
   - **Manual**: click "+ Legg til eit par" and type
4. Click **Kjør BLEU**

The results table shows corpus-level BLEU and chrF for each model. Expand the details section for per-segment scoring.

### About chrF

BLEU penalizes word-form differences harshly, which is a problem for nb↔nn because much of the language-pair difference is inflectional (e.g. `en → ein`, `sted → stad`, `gjør → gjer`). chrF uses character n-grams instead, so it's more robust for morphologically rich language pairs. Both are shown side-by-side.

## Corpus sources

- **Wikipedia**: built-in — the server uses the MediaWiki langlinks API to find matching nb/nn article pairs, then pulls plain-text extracts from both.
- **regjeringen.no**: not yet implemented. Most regjeringen.no pages have an `nn-NO` counterpart at a predictable URL slug swap. Adding a scraper would go in `src/sources/regjeringen.py`.
- **TSV paste**: any corpus you have as tab-separated pairs. Useful for test sets you curate by hand.

## Project structure

```
nb-nn-eval/
├── src/
│   ├── server.py          # HTTP server (stdlib only)
│   ├── bleu.py            # sacrebleu wrapper
│   ├── models/
│   │   ├── __init__.py    # registry — add new models here
│   │   ├── base.py        # Model interface
│   │   ├── nllb.py        # NLLB adapter
│   │   ├── marian.py      # Marian MT adapter
│   │   ├── madlad.py      # MADLAD-400 adapter
│   │   └── navjordj.py    # navjordj/t5_nb_nn adapter
│   └── sources/
│       └── wikipedia.py   # Wikipedia parallel fetcher
├── ui/
│   ├── index.html         # Playground
│   ├── eval.html          # BLEU evaluator
│   ├── app.js             # Playground JS
│   ├── eval.js            # BLEU eval JS
│   └── style.css
└── requirements.txt
```

## Adding a new model

Create `src/models/my_model.py`:

```python
from .base import Model

class MyModel(Model):
    def __init__(self, hf_name):
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        self.hf_name = hf_name
        self.display_name = "My Model"
        self.tokenizer = AutoTokenizer.from_pretrained(hf_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(hf_name)
        self.model.eval()
        self.param_count = f"{self.model.num_parameters() // 1_000_000}M"

    def translate(self, text: str) -> str:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        out = self.model.generate(**inputs, num_beams=4, max_length=512)
        return self.tokenizer.decode(out[0], skip_special_tokens=True)
```

Then register it in `src/models/__init__.py`:

```python
from .my_model import MyModel

REGISTRY["my-key"] = lambda: MyModel("org/my-model-name")
```

Restart the server and your model will show up in both UIs.
