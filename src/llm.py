"""
Minimal client for a local language model served by Ollama.

Free and offline: the model runs on the local GPU. Every caller
must cope with the model being unavailable (returns None), so
the analysis never depends on it.
"""

import json
import os

import requests


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.environ.get("STOCK_ENGINE_LLM", "qwen2.5:7b-instruct")

# A 2k context is enough for a batch of headlines and frees VRAM:
# on a 6 GB GPU this puts ~84% of the 7B model on the GPU (vs 82%)
# and is ~24% faster than the 4k default.
NUM_CTX = int(os.environ.get("STOCK_ENGINE_LLM_CTX", "2048"))


def llm_available(timeout=2):

    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        response.raise_for_status()
    except Exception:
        return False

    names = {m.get("name") for m in response.json().get("models", [])}

    return LLM_MODEL in names


def chat_json(system, user, schema, timeout=180):
    """
    Ask the model for JSON that matches `schema` (Ollama enforces
    the schema during decoding). Temperature 0 for repeatability.
    Returns the parsed object, or None on any failure.
    """

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": schema,
                "stream": False,
                "options": {"temperature": 0, "seed": 0, "num_ctx": NUM_CTX},
            },
            timeout=timeout,
        )
        response.raise_for_status()

        return json.loads(response.json()["message"]["content"])

    except Exception:
        return None


def chat_text(system, user, timeout=180):
    """Plain-text completion; None on failure."""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": 0, "seed": 0, "num_ctx": NUM_CTX},
            },
            timeout=timeout,
        )
        response.raise_for_status()

        return response.json()["message"]["content"]

    except Exception:
        return None
