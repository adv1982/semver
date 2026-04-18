#!/usr/bin/env bash
# Instala Petals em venv isolado, contornando bug pkg_resources/setuptools>=72

set -e
PETALS_VENV="$HOME/petals_venv"
MODEL="${1:-mlx-community/Huihui-Qwen3.5-35B-A3B-Claude-4.6-Opus-abliterated-6bit}"
CONSTRAINTS="/tmp/lilith_pip_constraints.txt"

# Forçar setuptools<72 em TODOS os ambientes de build do pip
echo "setuptools<72" > "$CONSTRAINTS"
export PIP_CONSTRAINT="$CONSTRAINTS"
export PIP_NO_BUILD_ISOLATION=1

echo "=== Criando venv Petals em $PETALS_VENV ==="
python3 -m venv "$PETALS_VENV"
source "$PETALS_VENV/bin/activate"

echo "=== Fixando setuptools ==="
pip install "setuptools<72" wheel pip --upgrade --quiet

echo "=== Instalando hivemind 1.1.10 ==="
pip install "hivemind==1.1.10.post2"

echo "=== Instalando torch (CPU) ==="
pip install torch --index-url https://download.pytorch.org/whl/cpu --quiet

echo "=== Instalando dependências Petals ==="
pip install \
  "transformers>=4.32.0,<4.35.0" \
  "peft==0.5.0" \
  "pydantic<2.0,>=1.10" \
  "async-timeout>=4.0.2" \
  "Dijkstar>=2.6.0" \
  "humanfriendly" \
  "sentencepiece>=0.1.99" \
  "speedtest-cli==2.1.3" \
  "tensor-parallel==1.0.23" \
  "cpufeature>=0.2.0" \
  "flask"

echo "=== Instalando petals (sem deps) ==="
pip install petals --no-deps

echo ""
echo "=== Petals pronto! Iniciando servidor na porta 5001... ==="
python "$(dirname "$(realpath "$0")")/petals_server.py" "$MODEL"
