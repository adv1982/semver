#!/usr/bin/env bash
# Instala Petals em venv isolado e inicia servidor de inferência

set -e
PETALS_VENV="$HOME/petals_venv"
MODEL="${1:-mlx-community/Huihui-Qwen3.5-35B-A3B-Claude-4.6-Opus-abliterated-6bit}"

echo "=== Criando venv Petals em $PETALS_VENV ==="
python3 -m venv "$PETALS_VENV"
source "$PETALS_VENV/bin/activate"

echo "=== Instalando setuptools compatível ==="
pip install "setuptools<72" --quiet --force-reinstall

echo "=== Instalando hivemind (sem build isolation) ==="
PIP_NO_BUILD_ISOLATION=1 pip install "hivemind==1.1.10.post2" --quiet

echo "=== Instalando torch CPU ==="
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
  "flask" \
  --quiet

pip install petals --no-deps --quiet

echo ""
echo "=== Petals instalado! ==="
echo "Iniciando servidor de inferência na porta 5001..."
python "$(dirname "$0")/petals_server.py" "$MODEL"
