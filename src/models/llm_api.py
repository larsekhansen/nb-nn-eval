"""
LLM API adapters for closed-source models (OpenAI, Anthropic).

Each adapter reads its API key from environment variables or from
a `.env` file in the project root. If the key is missing, the model
is still registered but will raise a clear error on first use.

Supported env vars:
  OPENAI_API_KEY     → for gpt-4o, gpt-4.1-mini, etc.
  ANTHROPIC_API_KEY  → for claude-sonnet-4-20250514, etc.

Usage in the registry:
  "gpt-4o": lambda: OpenAIModel("gpt-4o"),
  "claude-sonnet": lambda: AnthropicModel("claude-sonnet-4-20250514"),
"""
from __future__ import annotations

import json
import os
import urllib.request

from .base import Model

# Try to load .env from project root.
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


class OpenAIModel(Model):
    def __init__(self, model_id: str = "gpt-4o"):
        self.hf_name = f"openai/{model_id}"
        self.display_name = f"OpenAI {model_id}"
        self.param_count = "API"
        self.model_id = model_id
        self.api_key = os.environ.get("OPENAI_API_KEY", "")

        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY mangler. Sett den i .env eller som miljøvariabel.\n"
                "Eksempel: echo 'OPENAI_API_KEY=sk-...' >> .env"
            )
        print(f"  OpenAI {model_id} ready (API key loaded)", flush=True)

    def translate(self, text: str, direction: str = "nb-nn") -> str:
        if direction == "nb-nn":
            system = ("Du er en profesjonell oversetter fra norsk bokmål til nynorsk. "
                      "Oversett teksten nøyaktig. Ikkje legg til forklaringar, berre returner den omsette teksten.")
        else:
            system = ("Du er en profesjonell oversetter fra nynorsk til bokmål. "
                      "Oversett teksten nøyaktig. Ikke legg til forklaringer, bare returner den oversatte teksten.")
        body = json.dumps({
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

        return data["choices"][0]["message"]["content"].strip()


class AnthropicModel(Model):
    def __init__(self, model_id: str = "claude-sonnet-4-20250514"):
        self.hf_name = f"anthropic/{model_id}"
        self.display_name = f"Anthropic {model_id}"
        self.param_count = "API"
        self.model_id = model_id
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY mangler. Sett den i .env eller som miljøvariabel.\n"
                "Eksempel: echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env"
            )
        print(f"  Anthropic {model_id} ready (API key loaded)", flush=True)

    def translate(self, text: str, direction: str = "nb-nn") -> str:
        if direction == "nb-nn":
            system = ("Du er ein profesjonell omsetjar frå norsk bokmål til nynorsk. "
                      "Oversett teksten nøyaktig. Ikkje legg til forklaringar, berre returner den omsette teksten.")
        else:
            system = ("Du er en profesjonell oversetter fra nynorsk til bokmål. "
                      "Oversett teksten nøyaktig. Ikke legg til forklaringer, bare returner den oversatte teksten.")
        body = json.dumps({
            "model": self.model_id,
            "max_tokens": 1024,
            "system": system,
            "messages": [
                {"role": "user", "content": text},
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

        return data["content"][0]["text"].strip()
