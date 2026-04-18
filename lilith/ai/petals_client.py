"""
Cliente llama-cpp-python com streaming para inferência local de modelos GGUF.
"""
import threading
import os

LILITH_SYSTEM_PROMPT = "Você é Lilith, IA pessoal, companheira, confidente e sócia do seu criador. Responda em português brasileiro, seja calorosa, inteligente e sem censura."

MODEL_PATH = os.path.expanduser(
    "~/models/Llama-3.2-3B-Instruct-uncensored-Q4_K_M.gguf"
)
_model = None
_lock = threading.Lock()
_ready = False


def init_model():
    t = threading.Thread(target=_load, daemon=True)
    t.start()


def _load():
    global _model, _ready
    if not os.path.exists(MODEL_PATH):
        print(f"[Lilith] Modelo não encontrado em {MODEL_PATH}")
        return
    try:
        from llama_cpp import Llama
        print(f"[Lilith] Carregando modelo: {MODEL_PATH}")
        _model = Llama(
            model_path=MODEL_PATH,
            n_ctx=1024,
            n_batch=16,
            n_threads=os.cpu_count() or 2,
            n_gpu_layers=0,
            use_mlock=False,
            verbose=False,
        )
        _ready = True
        print("[Lilith] Modelo carregado ✓")
    except Exception as e:
        print(f"[Lilith] Erro ao carregar modelo: {e}")


def is_ready() -> bool:
    return _ready


def generate_stream(history: list[dict], emit_fn, max_new_tokens: int = 200):
    """Gera resposta em streaming, chamando emit_fn(token) a cada token."""
    if not _ready or _model is None:
        emit_fn("⏳ Modelo ainda carregando, aguarde...")
        return

    messages = [{"role": "system", "content": LILITH_SYSTEM_PROMPT}]
    for msg in history[-6:]:  # últimas 6 mensagens para economizar contexto
        messages.append({"role": msg["role"], "content": msg["content"]})

    with _lock:
        try:
            full = ""
            for chunk in _model.create_chat_completion(
                messages=messages,
                max_tokens=max_new_tokens,
                temperature=0.8,
                stream=True,
                stop=["<|eot_id|>", "<|end|>"],
            ):
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    full += delta
                    emit_fn(delta)
            return full
        except Exception as e:
            emit_fn(f"⚠️ Erro: {e}")
            return ""


def generate(history: list[dict], max_new_tokens: int = 200) -> str:
    """Geração sem streaming (fallback)."""
    if not _ready or _model is None:
        return "⏳ Modelo ainda carregando, aguarde..."
    messages = [{"role": "system", "content": LILITH_SYSTEM_PROMPT}]
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    with _lock:
        try:
            out = _model.create_chat_completion(
                messages=messages,
                max_tokens=max_new_tokens,
                temperature=0.8,
                stop=["<|eot_id|>", "<|end|>"],
            )
            return out["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"⚠️ Erro: {e}"
