# nb-nn-eval

Evaluate and compare Norwegian Bokmål → Nynorsk machine translation models. Everything runs locally on CPU — no API keys required for the open-source models.

![Screenshot of the playground](https://github.com/user-attachments/assets/placeholder.png)

## Quick start

```bash
git clone https://github.com/larsekhansen/nb-nn-eval.git
cd nb-nn-eval
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m src.server
```

Open **http://localhost:5055** — models are downloaded on first use.

## What's included

### 13 translation models

| Category | Model | Size | Notes |
|---|---|---|---|
| **Norwegian-specific** | `pere-nb-nn` | ~1 GB | T5-base, most-downloaded nb→nn on HF |
| | `navjordj-t5` | ~2.4 GB | T5, baseline comparison |
| | `apertium` | — | Rule-based (requires Docker) |
| **Norwegian LLMs** | `normistral-translate` | ~22 GB | UiO NorMistral 11B, best on nynorsk per Språkrådet 2025 |
| | `normistral-7b` | ~14 GB | NorMistral 7B instruct, faster |
| **Multilingual** | `nllb-600M` | ~2.4 GB | Meta NLLB-200 distilled |
| | `nllb-1.3B` | ~5 GB | Meta NLLB-200 distilled |
| | `nllb-3.3B` | ~13 GB | Meta NLLB-200 |
| | `marian-gmq` | ~300 MB | Helsinki-NLP, smallest/fastest |
| | `madlad-3b` | ~12 GB | Google MADLAD-400 |
| **API** | `gpt-4o` | — | Requires `OPENAI_API_KEY` |
| | `gpt-4.1-mini` | — | Requires `OPENAI_API_KEY` |
| | `claude-sonnet` | — | Requires `ANTHROPIC_API_KEY` |

Models are **lazy-loaded** — nothing is downloaded until you select one. Unavailable models (missing API keys, Docker not running) are grayed out in the UI.

### Three pages

- **Playground** (`/`) — Paste text, pick models, see translations side-by-side
- **BLEU-evaluering** (`/eval`) — Score models against a parallel corpus with BLEU + chrF metrics
- **Tidlegare resultat** (`/results`) — Browse, compare, and export saved evaluation runs

### Pre-built test corpora

| Corpus | Pairs | Source |
|---|---|---|
| `gull-standard` | 30 | Hand-written professional-quality nb/nn pairs |
| `wiki-byer` | 84 | Wikipedia: Bergen, Oslo, Trondheim, Stavanger, Tromsø |
| `wiki-samfunn` | 83 | Wikipedia: Stortinget, Klimaendring, Nynorsk, Bokmål |
| `wiki-natur` | 20 | Wikipedia: Fjord, Nasjonalpark, Fotball, Helse |
| `wiki-teknologi` | 6 | Wikipedia: Kunstig intelligens |

You can also build your own corpora from Wikipedia search, TSV paste, or manual entry — and save them for reuse.

## API models

To use GPT-4o, Claude, etc., create a `.env` file:

```bash
cp .env.example .env
# Edit .env and add your keys
```

## Apertium (rule-based)

```bash
docker run -d -p 2737:2737 apertium/apy
```

## Multi-run evaluation

Set "Køyringar" > 1 on the eval page to run the same evaluation multiple times. Useful for measuring variance in API models (deterministic local models produce identical scores every time).

The results table shows mean, spread (max−min), and standard deviation across runs.

## Adding a new model

1. Create `src/models/my_model.py` implementing the `Model` interface
2. Register it in `src/models/__init__.py`
3. Restart the server

See existing adapters for examples — each is ~40 lines.

## Project structure

```
nb-nn-eval/
├── src/
│   ├── server.py          # HTTP server (stdlib, no framework)
│   ├── bleu.py            # sacrebleu wrapper (BLEU + chrF)
│   ├── models/            # One adapter per model family
│   └── sources/
│       └── wikipedia.py   # Parallel corpus fetcher
├── ui/                    # Static HTML/CSS/JS frontend
├── corpora/               # Pre-built + user-saved test corpora
├── results/               # Saved evaluation runs (gitignored)
├── scripts/
│   └── build-corpora.py   # Re-fetch Wikipedia corpora
└── PLAN.md                # Roadmap and research notes
```

## License

MIT
