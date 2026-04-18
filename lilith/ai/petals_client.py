import threading
import torch
from config import PETALS_MODEL
from ai.persona import LILITH_SYSTEM_PROMPT

_model = None
_tokenizer = None
_lock = threading.Lock()
_ready = False


def _load():
    global _model, _tokenizer, _ready
    try:
        from petals import AutoDistributedModelForCausalLM
        from transformers import AutoTokenizer

        print(f"[Lilith] Conectando ao Petals: {PETALS_MODEL}")
        _tokenizer = AutoTokenizer.from_pretrained(PETALS_MODEL)
        _model = AutoDistributedModelForCausalLM.from_pretrained(
            PETALS_MODEL,
            torch_dtype=torch.float16,
        )
        _ready = True
        print("[Lilith] Modelo carregado via Petals ✓")
    except Exception as e:
        print(f"[Lilith] Petals indisponível ({e}), usando fallback HTTP.")
        _ready = False


def init_model():
    t = threading.Thread(target=_load, daemon=True)
    t.start()


def is_ready():
    return _ready


def generate(history: list[dict], max_new_tokens: int = 512) -> str:
    if not _ready or _model is None:
        return _generate_fallback(history)

    with _lock:
        prompt = _build_prompt(history)
        inputs = _tokenizer(prompt, return_tensors="pt")
        with torch.inference_mode():
            out = _model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.8,
                do_sample=True,
                pad_token_id=_tokenizer.eos_token_id,
            )
        decoded = _tokenizer.decode(out[0], skip_special_tokens=True)
        return decoded[len(prompt):].strip()


def _build_prompt(history: list[dict]) -> str:
    parts = [f"<|system|>\n{LILITH_SYSTEM_PROMPT}\n"]
    for msg in history:
        role = "user" if msg["role"] == "user" else "assistant"
        parts.append(f"<|{role}|>\n{msg['content']}\n")
    parts.append("<|assistant|>\n")
    return "".join(parts)


def _generate_fallback(history: list[dict]) -> str:
    """Fallback quando Petals não está disponível — retorna aviso claro."""
    return (
        "⚠️ Modelo Petals ainda está carregando ou indisponível. "
        "Aguarde alguns instantes ou verifique sua conexão com a rede Petals."
    )
