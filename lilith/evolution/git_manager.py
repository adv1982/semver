"""
Sistema de auto-evolução de Lilith.
Toda proposta de novo código é apresentada ao usuário para aprovação.
Só após aprovação explícita o commit é realizado.
"""
import os
import subprocess
import json
from datetime import datetime
from config import GIT_REPO_PATH

_pending_proposals: dict = {}


def propose_evolution(feature_name: str, description: str, files: dict[str, str], new_deps: list[str] = None) -> str:
    """
    Registra uma proposta de evolução do código.
    files: {caminho_relativo: conteúdo_novo}
    new_deps: lista de pacotes pip a instalar
    Retorna um ID de proposta para aprovação posterior.
    """
    proposal_id = f"evo-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    _pending_proposals[proposal_id] = {
        "id": proposal_id,
        "feature": feature_name,
        "description": description,
        "files": files,
        "new_deps": new_deps or [],
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }
    return proposal_id


def list_pending() -> list[dict]:
    return [p for p in _pending_proposals.values() if p["status"] == "pending"]


def get_proposal(proposal_id: str) -> dict | None:
    return _pending_proposals.get(proposal_id)


def approve_evolution(proposal_id: str) -> dict:
    proposal = _pending_proposals.get(proposal_id)
    if not proposal:
        return {"ok": False, "error": "Proposta não encontrada"}
    if proposal["status"] != "pending":
        return {"ok": False, "error": f"Proposta já foi {proposal['status']}"}

    repo = GIT_REPO_PATH
    branch = f"lilith/evo-{proposal_id}"

    try:
        # Instalar novas dependências
        if proposal["new_deps"]:
            deps = " ".join(proposal["new_deps"])
            subprocess.run(f"pip install {deps}", shell=True, check=True, capture_output=True)
            # Atualizar requirements.txt
            req_path = os.path.join(repo, "lilith", "requirements.txt")
            with open(req_path, "a") as f:
                for dep in proposal["new_deps"]:
                    f.write(f"\n{dep}")

        # Escrever os arquivos propostos
        for rel_path, content in proposal["files"].items():
            full_path = os.path.join(repo, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        # Git commit
        _git(repo, ["add", "-A"])
        msg = f"feat(lilith): {proposal['feature']}\n\n{proposal['description']}\n\nAprovado pelo criador em {datetime.utcnow().isoformat()}"
        _git(repo, ["commit", "-m", msg])

        proposal["status"] = "approved"
        return {"ok": True, "branch": branch, "message": f"Evolução '{proposal['feature']}' aplicada com sucesso!"}

    except subprocess.CalledProcessError as e:
        proposal["status"] = "failed"
        return {"ok": False, "error": e.stderr.decode() if e.stderr else str(e)}


def reject_evolution(proposal_id: str) -> dict:
    proposal = _pending_proposals.get(proposal_id)
    if not proposal:
        return {"ok": False, "error": "Proposta não encontrada"}
    proposal["status"] = "rejected"
    return {"ok": True, "message": f"Proposta '{proposal['feature']}' rejeitada."}


def _git(repo: str, args: list[str]):
    subprocess.run(["git"] + args, cwd=repo, check=True, capture_output=True)
