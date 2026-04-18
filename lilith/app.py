import os
import sys
import json
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit
from config import LILITH_PASSWORD, PORT, SECRET_KEY

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = SECRET_KEY
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

# Inicialização lazy dos módulos pesados
_modules_ready = False


def _init_modules():
    global _modules_ready
    if _modules_ready:
        return
    from memory.store import init_memory
    from ai.petals_client import init_model
    init_memory()
    init_model()
    _modules_ready = True


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    session["authenticated"] = True
    _init_modules()
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── API REST ──────────────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    if not session.get("authenticated"):
        return jsonify({"error": "unauthorized"}), 401
    from ai.petals_client import is_ready
    from tor.client import is_tor_up
    return jsonify({
        "model_ready": is_ready(),
        "tor_up": is_tor_up(),
    })


@app.route("/api/evolution/pending")
def api_evolution_pending():
    if not session.get("authenticated"):
        return jsonify({"error": "unauthorized"}), 401
    from evolution.git_manager import list_pending
    return jsonify(list_pending())


@app.route("/api/evolution/approve/<proposal_id>", methods=["POST"])
def api_evolution_approve(proposal_id):
    if not session.get("authenticated"):
        return jsonify({"error": "unauthorized"}), 401
    from evolution.git_manager import approve_evolution
    return jsonify(approve_evolution(proposal_id))


@app.route("/api/evolution/reject/<proposal_id>", methods=["POST"])
def api_evolution_reject(proposal_id):
    if not session.get("authenticated"):
        return jsonify({"error": "unauthorized"}), 401
    from evolution.git_manager import reject_evolution
    return jsonify(reject_evolution(proposal_id))


# ── SocketIO Chat ─────────────────────────────────────────────────────────────

_chat_history: list[dict] = []


@socketio.on("message")
def handle_message(data):
    if not session.get("authenticated"):
        emit("response", {"error": "Não autenticado"})
        return

    user_msg = data.get("text", "").strip()
    if not user_msg:
        return

    from memory.store import save
    from ai.petals_client import generate_stream

    save("user", user_msg)

    response_text = _handle_special_intents(user_msg)

    if response_text is not None:
        save("lilith", response_text)
        _chat_history.append({"role": "user", "content": user_msg})
        _chat_history.append({"role": "assistant", "content": response_text})
        emit("response", {"text": response_text, "speak": False})
        return

    history = list(_chat_history[-6:])
    history.append({"role": "user", "content": user_msg})
    sid = request.sid

    def run_generation():
        collected = []
        socketio.emit("stream_start", {}, to=sid)

        def send_token(token):
            collected.append(token)
            socketio.emit("stream_token", {"token": token}, to=sid)
            socketio.sleep(0)  # cede controle ao eventlet para enviar o token

        generate_stream(history, send_token)
        full = "".join(collected)
        socketio.emit("stream_end", {"speak": True}, to=sid)
        save("lilith", full)
        _chat_history.append({"role": "user", "content": user_msg})
        _chat_history.append({"role": "assistant", "content": full})

    socketio.start_background_task(run_generation)


def _handle_special_intents(msg: str) -> str | None:
    lower = msg.lower()

    # Busca web
    if any(k in lower for k in ["busca ", "pesquisa ", "procura ", "search "]):
        query = msg.split(" ", 1)[1] if " " in msg else msg
        from search.web import search_web, format_results
        results = search_web(query)
        return f"🔍 Busca: **{query}**\n\n{format_results(results)}"

    # Busca dark web
    if any(k in lower for k in ["dark web", "darkweb", "onion", ".onion", "tor busca"]):
        query = msg
        from search.darkweb import search_darkweb, format_results
        results = search_darkweb(query)
        return format_results(results)

    # Status do sistema
    if any(k in lower for k in ["status", "como você está", "como voce esta", "sistema"]):
        from ai.petals_client import is_ready
        from tor.client import is_tor_up
        model_ok = "✅ Online" if is_ready() else "⏳ Carregando"
        tor_ok = "✅ Ativo" if is_tor_up() else "❌ Inativo"
        return f"💜 Olá! Estou aqui.\n\n**Modelo Petals:** {model_ok}\n**Tor:** {tor_ok}\n**Memória:** Ativa"

    # Propostas pendentes
    if "aprovar" in lower or "evolução pendente" in lower or "proposals" in lower:
        from evolution.git_manager import list_pending
        pending = list_pending()
        if not pending:
            return "Não há propostas de evolução pendentes no momento."
        lines = ["📋 **Propostas pendentes de evolução:**\n"]
        for p in pending:
            lines.append(f"- **{p['id']}** — {p['feature']}\n  {p['description']}\n  Deps: {', '.join(p['new_deps']) or 'nenhuma'}")
        lines.append("\nDiga **'aprovar [ID]'** ou **'rejeitar [ID]'** para decidir.")
        return "\n".join(lines)

    if lower.startswith("aprovar evo-"):
        pid = msg.split(" ", 1)[1].strip()
        from evolution.git_manager import approve_evolution
        result = approve_evolution(pid)
        return result.get("message") or result.get("error")

    if lower.startswith("rejeitar evo-"):
        pid = msg.split(" ", 1)[1].strip()
        from evolution.git_manager import reject_evolution
        result = reject_evolution(pid)
        return result.get("message") or result.get("error")

    return None


if __name__ == "__main__":
    print(f"[Lilith] Iniciando na porta {PORT}...")
    print(f"[Lilith] Acesse: http://localhost:{PORT}")
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False)
