"""
HTTP server for the nb-nn-eval playground and BLEU evaluator.

Pure stdlib — no Flask, no FastAPI, no build step. Serves:

    GET  /                     → playground UI
    GET  /eval                 → BLEU evaluation UI
    GET  /ui/<file>            → static assets
    GET  /api/models           → list registered models
    POST /api/translate        → translate text with one model
    POST /api/translate-many   → translate text with several models
    POST /api/bleu             → score hypotheses against references
    GET  /api/wiki/search      → search nb Wikipedia
    GET  /api/wiki/parallel    → fetch nb/nn parallel paragraphs
"""
import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# Make `from src.models import ...` work regardless of how server.py is invoked.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src.models import REGISTRY, get_model, list_models, unload  # noqa: E402
from src import bleu as bleu_mod  # noqa: E402
from src.sources import wikipedia  # noqa: E402

PORT = int(os.environ.get("PORT", "5055"))
UI_DIR = os.path.join(ROOT, "ui")
CORPORA_DIR = os.path.join(ROOT, "corpora")
RESULTS_DIR = os.path.join(ROOT, "results")

# Ring buffer of recent log entries (kept in memory, not persisted).
_LOG_BUFFER: list = []
_LOG_MAX = 500


def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    _LOG_BUFFER.append(entry)
    if len(_LOG_BUFFER) > _LOG_MAX:
        _LOG_BUFFER.pop(0)
    sys.stderr.write(entry + "\n")


class Handler(BaseHTTPRequestHandler):
    # ── Routing ──────────────────────────────────────────────────
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            return self._serve_file(os.path.join(UI_DIR, "index.html"), "text/html; charset=utf-8")
        if path == "/eval":
            return self._serve_file(os.path.join(UI_DIR, "eval.html"), "text/html; charset=utf-8")
        if path.startswith("/ui/"):
            name = path[len("/ui/"):]
            return self._serve_static(name)
        if path == "/api/models":
            return self._reply(200, list_models())
        if path == "/api/device":
            from src.models.device import device_name
            return self._reply(200, {"device": device_name()})
        if path == "/api/logs":
            n = int((query.get("n") or ["100"])[0])
            return self._reply(200, {"logs": _LOG_BUFFER[-n:]})
        if path == "/api/wiki/search":
            q = (query.get("q") or [""])[0]
            if not q:
                return self._reply(400, {"error": "Missing q"})
            return self._reply(200, wikipedia.search_nb(q, limit=20))
        if path == "/api/wiki/parallel":
            title = (query.get("title") or [""])[0]
            if not title:
                return self._reply(400, {"error": "Missing title"})
            try:
                pairs = wikipedia.fetch_parallel_article(title)
                nn_title = wikipedia.find_nn_title(title)
                return self._reply(200, {"nb_title": title, "nn_title": nn_title, "pairs": pairs})
            except Exception as e:
                return self._reply(500, {"error": str(e)})
        if path == "/api/corpora":
            return self._list_corpora()
        if path == "/api/corpora/load":
            name = (query.get("name") or [""])[0]
            if not name:
                return self._reply(400, {"error": "Missing name"})
            return self._load_corpus(name)
        if path == "/api/results":
            return self._list_results()
        if path == "/api/results/load":
            name = (query.get("name") or [""])[0]
            if not name:
                return self._reply(400, {"error": "Missing name"})
            return self._load_result(name)
        if path == "/results":
            return self._serve_file(os.path.join(UI_DIR, "results.html"), "text/html; charset=utf-8")
        return self._reply(404, {"error": f"Not found: {path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            return self._reply(400, {"error": f"Invalid JSON: {e}"})

        try:
            if path == "/api/translate":
                return self._handle_translate(body)
            if path == "/api/translate-many":
                return self._handle_translate_many(body)
            if path == "/api/bleu":
                return self._handle_bleu(body)
            if path == "/api/unload":
                key = body.get("model")
                if not key:
                    return self._reply(400, {"error": "Missing model"})
                return self._reply(200, {"unloaded": unload(key)})
            if path == "/api/corpora/save":
                return self._save_corpus(body)
            if path == "/api/results/save":
                return self._save_result(body)
            if path == "/api/results/delete":
                return self._delete_result(body)
            return self._reply(404, {"error": f"Not found: {path}"})
        except Exception as e:
            traceback.print_exc()
            return self._reply(500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── Handlers ─────────────────────────────────────────────────
    def _handle_translate(self, body: dict):
        key = body.get("model")
        text = body.get("text", "")
        direction = body.get("direction", "nb-nn")
        if not key or not text:
            return self._reply(400, {"error": "Missing model or text"})
        _log(f"translate: model={key}, direction={direction}, input={len(text)} chars")
        m = get_model(key)
        t0 = time.time()
        translation = m.translate(text, direction=direction)
        ms = int((time.time() - t0) * 1000)
        _log(f"translate: model={key}, output={len(translation)} chars, {ms}ms")
        return self._reply(200, {
            "model": key,
            "hf_name": m.hf_name,
            "translation": translation,
            "ms": ms,
        })

    def _handle_translate_many(self, body: dict):
        keys = body.get("models") or []
        text = body.get("text", "")
        direction = body.get("direction", "nb-nn")
        if not keys or not text:
            return self._reply(400, {"error": "Missing models or text"})
        results = []
        for key in keys:
            try:
                m = get_model(key)
                t0 = time.time()
                translation = m.translate(text, direction=direction)
                results.append({
                    "model": key,
                    "hf_name": m.hf_name,
                    "translation": translation,
                    "ms": int((time.time() - t0) * 1000),
                })
            except Exception as e:
                results.append({"model": key, "error": str(e)})
        return self._reply(200, {"results": results})

    def _handle_bleu(self, body: dict):
        """
        Body:
          { "pairs": [{"nb": "...", "nn": "..."}, ...],
            "models": ["nllb-600M", "marian-gmq"] }

        For each model, translate every nb → nn_hat and score against the
        provided nn reference. Returns per-sentence and corpus-level scores.
        """
        pairs = body.get("pairs") or []
        keys = body.get("models") or []
        if not pairs or not keys:
            return self._reply(400, {"error": "Need pairs and models"})

        _log(f"bleu: {len(keys)} model(s) × {len(pairs)} pairs")
        results = []
        for key in keys:
            try:
                _log(f"bleu: loading model {key}")
                m = get_model(key)
            except Exception as e:
                _log(f"bleu: FAILED to load {key}: {e}")
                results.append({"model": key, "error": str(e)})
                continue

            per_segment = []
            hyps, refs = [], []
            t0 = time.time()
            for i, pair in enumerate(pairs):
                nb = (pair.get("nb") or "").strip()
                nn = (pair.get("nn") or "").strip()
                if not nb or not nn:
                    continue
                try:
                    t1 = time.time()
                    hyp = m.translate(nb)
                    seg_ms = int((time.time() - t1) * 1000)
                    _log(f"bleu: {key} seg {i+1}/{len(pairs)}: {seg_ms}ms, in={len(nb)}c out={len(hyp)}c")
                except Exception as e:
                    _log(f"bleu: {key} seg {i+1}/{len(pairs)}: ERROR {e}")
                    per_segment.append({"error": str(e), "nb": nb, "nn": nn})
                    continue
                scores = bleu_mod.sentence_scores(hyp, nn)
                per_segment.append({
                    "nb": nb,
                    "nn_ref": nn,
                    "nn_hyp": hyp,
                    **scores,
                })
                hyps.append(hyp)
                refs.append(nn)

            corpus = bleu_mod.corpus_scores(hyps, refs) if hyps else {"bleu": 0, "chrf": 0, "n": 0}
            results.append({
                "model": key,
                "hf_name": m.hf_name,
                "corpus": corpus,
                "segments": per_segment,
                "elapsed_ms": int((time.time() - t0) * 1000),
            })
        return self._reply(200, {"results": results})

    # ── Corpora ───────────────────────────────────────────────────
    def _list_corpora(self):
        os.makedirs(CORPORA_DIR, exist_ok=True)
        files = sorted(f for f in os.listdir(CORPORA_DIR) if f.endswith(".json"))
        corpora = []
        for f in files:
            try:
                with open(os.path.join(CORPORA_DIR, f)) as fh:
                    data = json.load(fh)
                corpora.append({
                    "name": f[:-5],  # strip .json
                    "description": data.get("description", ""),
                    "source": data.get("source", ""),
                    "pairs": len(data.get("pairs", [])),
                })
            except Exception:
                pass
        return self._reply(200, corpora)

    def _load_corpus(self, name: str):
        safe = name.replace("/", "").replace("..", "")
        path = os.path.join(CORPORA_DIR, f"{safe}.json")
        if not os.path.exists(path):
            return self._reply(404, {"error": f"Corpus '{name}' not found"})
        with open(path) as f:
            data = json.load(f)
        return self._reply(200, data)

    def _save_corpus(self, body: dict):
        name = body.get("name", "").strip()
        if not name:
            return self._reply(400, {"error": "Missing name"})
        safe = "".join(c for c in name if c.isalnum() or c in "-_ ").strip().replace(" ", "-")
        if not safe:
            return self._reply(400, {"error": "Invalid name"})
        os.makedirs(CORPORA_DIR, exist_ok=True)
        path = os.path.join(CORPORA_DIR, f"{safe}.json")
        data = {
            "name": name,
            "description": body.get("description", ""),
            "source": body.get("source", ""),
            "pairs": body.get("pairs", []),
        }
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return self._reply(200, {"saved": safe, "pairs": len(data["pairs"])})

    # ── Results ───────────────────────────────────────────────────
    def _list_results(self):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        files = sorted(
            (f for f in os.listdir(RESULTS_DIR) if f.endswith(".json")),
            reverse=True,  # newest first (filenames are timestamped)
        )
        results = []
        for f in files:
            try:
                with open(os.path.join(RESULTS_DIR, f)) as fh:
                    data = json.load(fh)
                results.append({
                    "name": f[:-5],
                    "label": data.get("label", ""),
                    "corpus": data.get("corpus_name", ""),
                    "models": [r.get("model") for r in data.get("results", []) if not r.get("error")],
                    "runs": data.get("runs", 1),
                    "timestamp": data.get("timestamp", ""),
                })
            except Exception:
                pass
        return self._reply(200, results)

    def _load_result(self, name: str):
        safe = name.replace("/", "").replace("..", "")
        path = os.path.join(RESULTS_DIR, f"{safe}.json")
        if not os.path.exists(path):
            return self._reply(404, {"error": f"Result '{name}' not found"})
        with open(path) as f:
            data = json.load(f)
        return self._reply(200, data)

    def _save_result(self, body: dict):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        label = body.get("label", "").strip()
        safe_label = "".join(c for c in label if c.isalnum() or c in "-_ ").strip().replace(" ", "-") if label else ""
        name = f"{ts}-{safe_label}" if safe_label else ts
        path = os.path.join(RESULTS_DIR, f"{name}.json")
        body["timestamp"] = ts
        with open(path, "w") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
        return self._reply(200, {"saved": name})

    def _delete_result(self, body: dict):
        name = body.get("name", "")
        safe = name.replace("/", "").replace("..", "")
        path = os.path.join(RESULTS_DIR, f"{safe}.json")
        if os.path.exists(path):
            os.remove(path)
            return self._reply(200, {"deleted": name})
        return self._reply(404, {"error": f"Not found: {name}"})

    # ── Plumbing ─────────────────────────────────────────────────
    def _serve_file(self, path: str, content_type: str):
        if not os.path.exists(path):
            return self._reply(404, {"error": f"Missing file: {path}"})
        with open(path, "rb") as f:
            payload = f.read()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, name: str):
        # Prevent path traversal.
        if "/" in name or ".." in name:
            return self._reply(403, {"error": "Forbidden"})
        path = os.path.join(UI_DIR, name)
        ext = os.path.splitext(name)[1].lower()
        types = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".html": "text/html; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
        }
        return self._serve_file(path, types.get(ext, "application/octet-stream"))

    def _reply(self, status: int, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {fmt % args}\n")


def main():
    from src.models.device import device_name
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"nb-nn-eval listening on http://127.0.0.1:{PORT}")
    print(f"  Playground:  http://127.0.0.1:{PORT}/")
    print(f"  BLEU eval:   http://127.0.0.1:{PORT}/eval")
    print(f"  Device:      {device_name()}")
    print(f"  Models:      {', '.join(REGISTRY.keys())}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.server_close()


if __name__ == "__main__":
    main()
