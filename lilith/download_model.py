"""
Baixa o modelo GGUF do HuggingFace para ~/models/
"""
import os
from huggingface_hub import hf_hub_download

REPO = "bartowski/Llama-3.2-3B-Instruct-abliterated-GGUF"
FILE = "Llama-3.2-3B-Instruct-abliterated-Q4_K_M.gguf"
DEST = os.path.expanduser("~/models")

os.makedirs(DEST, exist_ok=True)
print(f"Baixando {FILE} (~2GB)...")
path = hf_hub_download(repo_id=REPO, filename=FILE, local_dir=DEST)
print(f"Modelo salvo em: {path}")
