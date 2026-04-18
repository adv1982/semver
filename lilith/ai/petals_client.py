"""
Cliente Ollama para inferência local.
Inicie o Ollama antes: ollama serve
"""
import requests as _requests
from ai.persona import LILITH_SYSTEM_PROMPT

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "hf.co/bartowski/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF:Q4_K_M"
_TIMEOUT = 120


def init_model():
    pass  # Ollama gerencia o modelo automaticamente


def is_ready() -> bool:
    try:
        r = _requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return any(MODEL.split(":")[0] in m for m in models)
    except Exception:
        return False


def generate(history: list[dict], max_new_tokens: int = 512) -> str:
    messages = [{"role": "system", "content": LILITH_SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        r = _requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_new_tokens, "temperature": 0.8},
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except _requests.exceptions.ConnectionError:
        return (
            "⚠️ Ollama offline. Inicie com:\n```\nollama serve\n```"
        )
    except Exception as e:
        return f"⚠️ Erro: {e}"
