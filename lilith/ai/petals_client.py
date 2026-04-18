"""
Cliente llama-cpp-python para inferência local de modelos GGUF.
Baixe o modelo antes:
  python download_model.py
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
        print("[Lilith] Execute: python download_model.py")
        return
    try:
        from llama_cpp import Llama
        print(f"[Lilith] Carregando modelo: {MODEL_PATH}")
        _model = Llama(
            model_path=MODEL_PATH,
            n_ctx=1024,
            n_batch=16,
            n_threads=max(1, (os.cpu_count() or 2) // 2),
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


def generate(history: list[dict], max_new_tokens: int = 512) -> str:
    if not _ready or _model is None:
        if not os.path.exists(MODEL_PATH):
            return (
                "⚠️ Modelo não baixado ainda. Execute no terminal:\n"
                "```\npython download_model.py\n```"
            )
        return "⏳ Modelo ainda carregando, aguarde..."

    messages = [{"role": "system", "content": LILITH_SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    with _lock:
        try:
            out = _model.create_chat_completion(
                messages=messages,
                max_tokens=min(max_new_tokens, 256),
                temperature=0.8,
                stop=["<|eot_id|>", "<|end|>"],
            )
            return out["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"⚠️ Erro na geração: {e}"
