"""
Apertium nob→nno adapter — rule-based MT.

Apertium is a classic rule-based translation system. The nob→nno pair is
maintained by the Apertium community and available through the official
Apertium APY (API server) Docker image.

Since installing Apertium natively on macOS is non-trivial (no Homebrew
package), this adapter supports two backends:

  1. Docker: `docker run -p 2737:2737 apertium/apy`
     Then set APERTIUM_URL=http://localhost:2737 (the default).

  2. Custom API URL: Set APERTIUM_URL to any running Apertium APY instance.

If neither is available, the model will raise a clear error on first use.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse

from .base import Model

DEFAULT_URL = "http://localhost:2737"


class Apertium(Model):
    def __init__(self):
        self.hf_name = "apertium/apy (nob→nno)"
        self.display_name = "Apertium (rule-based)"
        self.param_count = "rule-based"
        self.base_url = os.environ.get("APERTIUM_URL", DEFAULT_URL).rstrip("/")

        # Verify connectivity.
        try:
            req = urllib.request.Request(
                f"{self.base_url}/listPairs",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            pairs = data.get("responseData", [])
            has_pair = any(
                p.get("sourceLanguage") == "nob" and p.get("targetLanguage") == "nno"
                for p in pairs
            )
            if not has_pair:
                available = [(p.get("sourceLanguage"), p.get("targetLanguage")) for p in pairs[:10]]
                raise RuntimeError(
                    f"Apertium APY at {self.base_url} does not have nob→nno. "
                    f"Available pairs (first 10): {available}"
                )
            print(f"  connected to Apertium APY at {self.base_url}", flush=True)
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            raise RuntimeError(
                f"Kan ikkje nå Apertium APY på {self.base_url}. "
                f"Start den med: docker run -d -p 2737:2737 apertium/apy\n"
                f"Feil: {e}"
            ) from e

    def translate(self, text: str, direction: str = "nb-nn") -> str:
        pair = "nob|nno" if direction == "nb-nn" else "nno|nob"
        params = urllib.parse.urlencode({
            "langpair": pair,
            "q": text,
        })
        url = f"{self.base_url}/translate?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        translated = data.get("responseData", {}).get("translatedText", "")
        if not translated:
            raise RuntimeError(f"Apertium returned empty: {data}")
        return translated
