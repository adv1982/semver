"""
Cliente do servidor Petals local (http://localhost:5001).
Inicie o servidor separado com: bash install_petals.sh
"""
import requests as _requests
from ai.persona import LILITH_SYSTEM_PROMPT

PETALS_SERVER = "http://127.0.0.1:5001"
_TIMEOUT = 120


def init_model():
    pass  # servidor Petals é iniciado separadamente


def is_ready() -> bool:
    try:
        r = _requests.get(f"{PETALS_SERVER}/status", timeout=3)
        return r.json().get("ready", False)
    except Exception:
        return False


def generate(history: list[dict], max_new_tokens: int = 512) -> str:
    try:
        r = _requests.post(
            f"{PETALS_SERVER}/generate",
            json={"history": history, "max_new_tokens": max_new_tokens},
            timeout=_TIMEOUT,
        )
        if r.status_code == 503:
            return "⏳ Lilith ainda está acordando... o modelo está carregando na rede Petals. Aguarde um momento."
        data = r.json()
        if "error" in data:
            return f"⚠️ Erro do modelo: {data['error']}"
        return data.get("text", "")
    except _requests.exceptions.ConnectionError:
        return (
            "⚠️ Servidor Petals offline. Inicie em outro terminal:\n"
            "```\nbash install_petals.sh\n```"
        )
    except _requests.exceptions.Timeout:
        return "⏳ O modelo demorou muito para responder. Tente novamente."
    except Exception as e:
        return f"⚠️ Erro inesperado: {e}"
