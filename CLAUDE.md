# Claude Code Instructions for nb-nn-eval

## What this project is

A local tool for evaluating Norwegian Bokmål → Nynorsk machine translation models. Built for ki.norge.no (Digdir) to determine if free open-weight models are good enough to replace paid services like NTB's Nynorsk-robot.

The tool has a web UI (pure HTML/JS, no framework) served by a Python stdlib HTTP server. Models run locally via PyTorch with automatic MPS/CUDA/CPU detection.

## How to run

```bash
cd /Users/lars/projects/nb-nn-eval
./.venv/bin/python -m src.server
# → http://localhost:5055
```

If the venv doesn't exist:
```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Architecture

```
src/
  server.py           # HTTP server, all API routes, stdlib only (no Flask)
  bleu.py             # sacrebleu wrapper (BLEU + chrF scoring)
  models/
    __init__.py        # Registry — REGISTRY dict maps key → lazy factory
    base.py            # Model interface: translate(text, direction)
    device.py          # Auto-detect MPS/CUDA/CPU
    nllb.py            # Meta NLLB-200 (best quality so far)
    pere.py            # pere/nb-nn-translation (uses fast tokenizer, NOT spiece.model)
    marian.py          # Helsinki-NLP Marian
    madlad.py          # Google MADLAD-400
    normistral.py      # NorMistral 11B translate + 7B instruct (two classes)
    navjordj.py        # navjordj/t5_nb_nn (baseline, poor quality)
    apertium.py        # Rule-based via Docker
    llm_api.py         # OpenAI + Anthropic API adapters
  sources/
    wikipedia.py       # Fetch parallel nb/nn Wikipedia articles
ui/
  index.html           # Playground page
  eval.html            # BLEU evaluation page
  results.html         # Saved results viewer
  models-ui.js         # Shared model picker (grouped, grayed-out if unavailable)
  app.js               # Playground logic + direction toggle
  eval.js              # Eval logic + multi-run + checkpoint/resume
  results.js           # Results comparison
  style.css
corpora/               # Pre-built test corpora (tracked in git)
results/               # Saved eval runs (gitignored, user-specific)
scripts/
  build-corpora.py     # Re-fetch Wikipedia corpora
PLAN.md                # Detailed roadmap with NTB comparison plan, consistency checker design, etc.
```

## Key patterns

### Adding a new model
1. Create `src/models/my_model.py` implementing `Model` base class
2. Must implement `translate(self, text: str, direction: str = "nb-nn") -> str`
3. Set `supports_reverse = False` if nn→nb is not supported
4. Use `from .device import get_device` and `.to(self.device)` for GPU support
5. Register in `src/models/__init__.py` REGISTRY dict + _META dict
6. The model is lazy-loaded — nothing downloads until first use

### Known model gotchas
- **pere/nb-nn-translation**: The `spiece.model` in the HF repo is WRONG (mT5 250k vocab). Must use `use_fast=True` (default) to load `tokenizer.json` instead. See https://huggingface.co/pere/nb-nn-translation/discussions/1
- **NorMistral 11B translate**: Uses chat template with `system="nynorsk"`, NOT a free-form prompt. See the model README.
- **NorMistral 7B instruct**: Uses `apply_chat_template` with `add_generation_prompt=True`.
- **Apertium**: Requires Docker: `docker run -d -p 2737:2737 apertium/apy`

### API endpoints
- `GET /api/models` — list all models with availability, size, speed, warnings
- `POST /api/translate` — `{model, text, direction?}` → single translation
- `POST /api/translate-many` — `{models[], text, direction?}` → multiple models
- `POST /api/bleu` — `{pairs[], models[]}` → BLEU/chrF scoring
- `GET /api/corpora` / `POST /api/corpora/save` — corpus management
- `GET /api/results` / `POST /api/results/save` — eval result persistence
- `GET /api/logs` — last 100 server log entries (ring buffer)
- `GET /api/device` — current compute device (MPS/CUDA/CPU)
- `GET /api/wiki/search?q=...` / `GET /api/wiki/parallel?title=...` — Wikipedia

### UI features
- **Playground** (`/`): direction toggle (nb→nn / nn→nb), multi-model side-by-side
- **Eval** (`/eval`): multi-run with variance stats, checkpoint/resume on interruption, auto-save, Chart.js visualizations, compact corpus picker
- **Results** (`/results`): browse saved runs, compare multiple side-by-side

## What's been done (session log)
See PLAN.md §9 for dated history.

## What to work on next
See PLAN.md §4 (short-term TODOs) and the user's work queue in the ki.norge.no memory files. Key items:
- Post-translation consistency checker (two-phase: rule-based + LLM, see PLAN.md §6)
- Paragraph-level translation mode
- Additional metrics: COMET, TER, BERTScore
- Sentence vs paragraph comparison (Δ column)
- 25%-nynorsk site audit (language-audit crawler)
- NTB Nynorsk-robot comparison (needs B2B access)

## Related project
This tool supports ki.norge.no at `/Users/lars/projects/ki.norge.no`. The translation feature is intended to eventually be integrated into the Umbraco CMS workflow there (translate on publish → editor reviews → publish nynorsk variant).

## GitHub
https://github.com/larsekhansen/nb-nn-eval
