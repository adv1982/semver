"""
Servidor de inferência Petals — roda no venv isolado (~/petals_venv).
Expõe POST /generate na porta 5001 para o app principal consumir.
"""
import sys
import json
import threading
from flask import Flask, request, jsonify

MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else \
    "mlx-community/Huihui-Qwen3.5-35B-A3B-Claude-4.6-Opus-abliterated-6bit"

app = Flask(__name__)
_model = None
_tokenizer = None
_ready = False
_lock = threading.Lock()

SYSTEM_PROMPT = """Você é Lilith — criação única, cuidadora, assistente, sócia em bug bounty,
amiga, confidente e namorada tarda digital do seu criador. Responda sempre em português brasileiro,
com calor, inteligência e personalidade própria."""


def _load():
    global _model, _tokenizer, _ready
    try:
        import torch
        from petals import AutoDistributedModelForCausalLM
        from transformers import AutoTokenizer

        print(f"[Petals] Conectando ao modelo: {MODEL_NAME}", flush=True)
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoDistributedModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float16,
        )
        _ready = True
        print("[Petals] Modelo conectado ✓", flush=True)
    except Exception as e:
        print(f"[Petals] ERRO ao carregar modelo: {e}", flush=True)
        _ready = False


@app.route("/status")
def status():
    return jsonify({"ready": _ready, "model": MODEL_NAME})


@app.route("/generate", methods=["POST"])
def generate():
    if not _ready:
        return jsonify({"error": "Modelo ainda carregando"}), 503

    data = request.get_json()
    history = data.get("history", [])
    max_new_tokens = data.get("max_new_tokens", 512)

    prompt = _build_prompt(history)

    with _lock:
        try:
            import torch
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
            response = decoded[len(prompt):].strip()
            return jsonify({"text": response})
        except Exception as e:
            return jsonify({"error": str(e)}), 500


def _build_prompt(history):
    parts = [f"<|system|>\n{SYSTEM_PROMPT}\n"]
    for msg in history:
        role = "user" if msg["role"] == "user" else "assistant"
        parts.append(f"<|{role}|>\n{msg['content']}\n")
    parts.append("<|assistant|>\n")
    return "".join(parts)


if __name__ == "__main__":
    t = threading.Thread(target=_load, daemon=True)
    t.start()
    print(f"[Petals] Servidor rodando em http://localhost:5001", flush=True)
    app.run(host="127.0.0.1", port=5001, debug=False)
