# nb-nn-eval — Plan & Roadmap

A living document. Keep it honest: what exists, what doesn't, what might. The `README.md` is for users running the tool; this file is for the person (or future Claude) deciding what to work on next.

---

## 1. Purpose

Find out which freely available machine translation model is actually *good enough* for translating Norwegian Bokmål → Nynorsk in production — specifically, good enough that a human proofreader spends less time fixing the output than they would writing from scratch.

The broader question is: **what does the cost/quality frontier actually look like for nb→nn?** The answer matters because:

- **ki.norge.no** (and many other public-sector sites) are expected to offer content in both målformer. Today this is mostly handled by either (a) not translating at all, (b) paying for NTB's `nynorsk-robot`, or (c) manual translation. None of those scale well for small teams.
- **NTB Nynorsk-robot** is the de-facto gold standard in Norwegian news publishing, but it's a paid B2B product — pricing is per-article and non-transparent. We need a data-driven answer to "is the free open-weight alternative close enough?"
- The language pair is unusually easy (maybe ~85% of "translation" is deterministic morphological substitution), so small models should in theory work well. But small Norwegian-specific models on HF turn out to be broken or untrained — the winners so far are multilingual giants that happened to see enough Norwegian during pretraining. That's worth documenting.

The tool is the thing that lets us answer those questions with real numbers instead of vibes.

---

## 2. What's built (current state)

### Core

- **HTTP server** (`src/server.py`) — stdlib only, no Flask/FastAPI. Serves JSON APIs and static UI files on `:5055`.
- **Model registry** (`src/models/__init__.py`) — lazy-loaded adapters so nothing is downloaded until you actually pick a model.
- **Six pre-registered models**:
  - `nllb-600M` / `nllb-1.3B` / `nllb-3.3B` — Meta NLLB-200 family, native `nob_Latn` ↔ `nno_Latn` support
  - `marian-gmq` — Helsinki-NLP `opus-mt-gmq-gmq` (North Germanic multi-target)
  - `madlad-3b` — Google MADLAD-400 3B, 400+ languages
  - `navjordj-t5` — Norwegian-specific T5 baseline (generally poor quality; kept for comparison)
- **BLEU + chrF scoring** (`src/bleu.py`) — via `sacrebleu`. Both sentence-level and corpus-level.
- **Wikipedia parallel-corpus fetcher** (`src/sources/wikipedia.py`) — uses MediaWiki `langlinks` to find matching nb/nn article pairs, extracts plain text, aligns paragraphs positionally.

### UI

- **Playground** (`/`) — pick one or many models, paste text, see all outputs side-by-side with per-model timing.
- **BLEU evaluator** (`/eval`) — load a corpus (Wikipedia search, TSV paste, or manual entry), pick models, get corpus-level BLEU + chrF and a per-segment breakdown.

### Known-good result

Smoke-tested with a 3-pair synthetic corpus: `nllb-600M` scored BLEU 43.12 / chrF 81.94 in ~1.8s on CPU. NLLB consistently produces real nynorsk forms (`ein`, `Noreg`, `verksemder`, `ansvarsfull`) where the smaller Norwegian-specific models just copy input through unchanged.

---

## 3. Known limitations

These are things that *aren't bugs* but will bite you if you forget about them.

- **Wikipedia paragraph alignment is positional and crude.** nb and nn Wikipedia articles are often written independently, not translated from each other. For parallel corpora with real alignment guarantees we need a different source (see §5).
- **BLEU is unkind to nb↔nn.** Small inflectional differences (`en → ein`, `gjør → gjer`) tank BLEU scores even when the output is perfectly good nynorsk. chrF is more forgiving but still imperfect. See §6 for what we probably need instead.
- **Memory footprint stacks.** Lazy loading keeps startup cheap, but models stay loaded once used. Loading all six ≈ 35+ GB RAM. There's an `/api/unload` endpoint but nothing in the UI uses it yet.
- **No caching of translations.** Same input + same model hits the model every time. Fine for exploration, wasteful for real eval runs against large corpora.
- **No test suite.** The pipeline is small enough to poke at manually; once we start making real decisions from the output we should lock in some regression tests.
- **Python 3.9 compatibility.** Had to add `from __future__ import annotations` in a few places. Worth bumping to 3.11+ at some point, especially if we start using features like `typing.Self` or pattern matching.

---

## 4. Short-term TODOs

Things that would make the tool immediately more useful, roughly ordered by impact-per-effort:

### Corpora

- [ ] **regjeringen.no scraper** (`src/sources/regjeringen.py`). Most pages on regjeringen.no have both `nb-NO` and `nn-NO` versions at predictable URL slug variants. A scraper that takes a list of page IDs (or a sitemap crawl) and produces a clean parallel corpus would give us a much better eval dataset than Wikipedia. Regjeringen translations are professional and content-aligned.
- [ ] **Stortinget corpus.** `data.stortinget.no` exposes debates and publications in both målformer. Might be more formal than we need, but it's high-quality parallel text.
- [ ] **Built-in reference corpora.** Ship 2–3 curated datasets under `corpora/` (gitignored but documented) so anyone can run `--corpus wiki-ki` or similar and get reproducible numbers without setting up sources themselves.
- [ ] **Corpus cache.** Store fetched Wikipedia articles on disk so re-running an eval doesn't re-download.

### Models

- [ ] **NbAiLab `translategemma-4b-it-nb-nn`**. Trained specifically on nb→nn. Currently gated — requires requesting access on HF. Once approved, add an adapter and see if a Norwegian-specific fine-tune beats the multilingual giants.
- [ ] **NLLB-200 54B (MoE).** The full fat NLLB. Probably not runnable locally, but we could add a proxy adapter that calls the HF Inference API for comparison.
- [ ] **Norallm / NB-BERT derivatives.** The National Library of Norway has released Norwegian LM checkpoints; check whether any have been fine-tuned for nb↔nn.
- [ ] **LLM prompt baselines.** Run gpt-4o / claude / llama-3-70b via a simple prompt like `"Oversett til nynorsk: {text}"`. These should be excellent at nb→nn and give us an upper bound for what "smart" translation looks like. Add as adapters behind env-var API keys.

### Evaluation quality

- [ ] **Per-feature error analysis.** Automatically flag common failure modes: wrong pronoun form, loanword pass-through, clausal restructuring. A diff viewer per segment would surface these fast.
- [ ] **Multiple references.** sacrebleu supports it; the API handles it; the UI doesn't. Useful when there are several valid translations.
- [ ] **COMET score.** A neural metric (`Unbabel/wmt22-comet-da`) that correlates much better with human judgement than BLEU/chrF. Adds a ~400 MB model but is the modern standard.
- [ ] **Human rating UI.** A page where you're shown a pair of (reference, model output) and rate 1-5 on accuracy + fluency. Stash the ratings in a local SQLite and compute correlations with automatic metrics.

### Quality-of-life

- [ ] **Unload button in the model cards.** Calls `/api/unload` so you can free RAM without restarting.
- [ ] **Save/load eval runs.** Export a run (corpus + model outputs + scores) as JSON so results are comparable over time.
- [ ] **Markdown/CSV export of the BLEU table.** Quick copy for writing up results.
- [ ] **Batch translation endpoint.** Right now the server translates one segment at a time. Real models batch much more efficiently; a `translate-batch` endpoint would cut eval time significantly on large corpora.
- [ ] **Dark mode.** Cheap.

---

## 5. Medium-term: comparing against NTB Nynorsk-robot

This is the whole point. NTB's `nynorsk-robot` (sometimes just "Nynorob") is the commercial incumbent, trusted by most major Norwegian news outlets. If a free open-weight model is within ε of NTB's quality, that's a meaningful finding for every small publisher in Norway.

### What we need to find out first

- **How do we get access?** NTB sells the robot via API, typically through a B2B contract. We need to figure out whether there's a demo / researcher tier, whether a one-off eval batch is possible, or whether we need an actual commercial relationship. First step: email them and ask directly.
- **What are they charging?** Per article? Per character? Per month? This is the axis against which "free" gets measured.
- **Can we publish results?** If they're willing to be evaluated openly, great. If they require NDA'd results, the exercise is less useful publicly but can still guide internal decisions.

### How the eval would work once access exists

1. Add `src/models/ntb.py` — adapter that calls NTB's API instead of running a local model. It implements the same `Model` interface so it plugs into everything automatically.
2. Curate a fair test set:
   - News-adjacent text (since that's what NTB is trained for)
   - Government/public-sector prose (since that's what we care about)
   - Informal web copy
   - Technical/scientific text
   - ~100–200 segments, human-translated by a professional nynorsk writer as ground truth
3. Run all models (NLLB family, Marian, MADLAD, NTB, plus any LLMs) against the test set.
4. Compute BLEU + chrF + COMET + human ratings.
5. Publish the result somewhere useful. Digdir and regjeringen both have platforms for this kind of finding.

### What we'd probably learn

Educated guess: NTB wins on fluency (because it's a custom-trained system) but is indistinguishable from NLLB-3.3B on short factual text. The interesting question is whether the *price delta* matches the *quality delta* for the average publisher — and whether a small publisher could realistically use NLLB-600M as a first draft with light human editing, at zero marginal cost.

---

## 6. Long-term: general-purpose translation service

If the nb-nn evaluation goes well, the natural next step is a self-hostable translation service covering more language pairs, that public-sector Norwegian teams can point at from their CMS. Think: **"DeepL for nb/nn/en/se (sámi)/kven that runs on one box"**.

### Why this matters

- **Data sovereignty.** Government content routinely can't be sent to DeepL/Google for translation — leaving the EEA, third-party processing, sometimes outright forbidden by GDPR risk assessments. A self-hosted service sidesteps all of it.
- **Languages the big vendors underserve.** Sámi languages, kven, and nynorsk are systematically underserved by commercial MT. NLLB actually covers all of them. A wrapper that exposes them through a friendly API is surprisingly valuable.
- **Cost.** Running NLLB-3.3B on a single CPU box serves thousands of small-publisher translation requests per day for the cost of electricity.

### What it'd take

The current repo is ~80% of the way there:

- [ ] Promote the server from "research tool" to "stable API". Add versioning, auth (optional — some deployments want open), rate limiting, structured logging.
- [ ] Docker image. The model weights are the pain point (10+ GB for NLLB-3.3B) — probably ship with lazy-download on first boot rather than baking into the image.
- [ ] Helm chart for Azure Container Apps / K8s.
- [ ] Direction-agnostic API: take `source_lang`, `target_lang`, route to the appropriate model adapter. Today the server assumes nb→nn.
- [ ] Language detection for auto-routing (`fasttext` or similar small model).
- [ ] Glossary / do-not-translate list support. Critical for government content where agency names, official titles, and statutes must not be auto-translated.
- [ ] Batch API endpoint with async job queue (for big publishing workflows).
- [ ] Prometheus metrics, health checks, readiness probes.
- [ ] A minimal admin UI (reuse what we have, extended) so editors can submit texts and grab translations without any API integration.
- [ ] Documentation + example client libraries (TypeScript, Python, C#/.NET for Umbraco integrations).

### What this is NOT

- Not a replacement for human translators of consequential text.
- Not a real-time streaming API (at least not in v1).
- Not trained or fine-tuned by us — we're a routing and evaluation layer on top of open models.

### Who might care

- ki.norge.no itself
- Other Digdir properties with nynorsk requirements
- Small-to-medium municipalities and county admins who can't afford NTB
- Sámi-language publishers (if we support it properly)
- Research groups who want reproducible MT baselines without cloud costs

---

## 7. Open questions

Things we don't have answers to yet. Mostly need data or external input to resolve.

- **Is BLEU actually tracking what we care about?** chrF is better but still a proxy. Human eval is the only real answer. How do we run a cheap-but-honest human eval?
- **How does model size actually scale on nb→nn?** Does NLLB-3.3B beat NLLB-600M enough to justify 5× the disk and RAM? Need the test corpus first.
- **Are the Norwegian-specific small models (pere, navjordj, NbAiLab) worth fixing?** Some have broken HF repos (LFS pointer files for configs). If someone republished proper weights, they might actually compete. Not our job to fix them, but worth filing issues.
- **What do editors actually want?** If NTB produces 85 BLEU output and NLLB produces 72 BLEU output, which do human editors prefer when post-editing? (Intuition: sometimes the worse score is easier to fix because the errors are more predictable.)
- **Domain sensitivity.** A model trained on news probably flops on legal text. The public-sector corpus we build has to be balanced.

---

## 8. Non-goals

Just as important to write down. These are things that sound tempting but should stay off the table unless the project grows:

- **Training or fine-tuning our own models.** Expensive, requires expertise we don't have on hand, and there's no evidence we'd beat NLLB with small-scale fine-tuning.
- **Building a new metric.** BLEU is old; chrF and COMET already exist. We don't need to invent anything here.
- **Becoming a product company.** If the general-purpose service happens, it should be as a tool Digdir or another public-sector body owns, not a commercial offering.
- **Covering every target language.** Scope creeps fast. Start with nb, nn, en, then add one language at a time only when there's a real user asking.

---

## 9. Session log

Rough notes on what was done when, so future context is not lost.

- **2026-04-09** — Initial commit. Rescued from a throwaway demo page in `ki.norge.no`. Established model registry pattern, built Playground + BLEU UI, added Wikipedia fetcher. Found that `pere/nb-nn-translation` on HF is broken (config files stuck as unresolved LFS pointers); switched to NLLB-200 as the working default. Helsinki Marian and navjordj T5 added as comparison baselines. Tested end-to-end with a 3-pair synthetic corpus — everything functional.
