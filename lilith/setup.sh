#!/usr/bin/env bash
set -e

echo "=== Lilith Setup ==="

# Verificar Python
python3 --version || { echo "Python 3 necessário"; exit 1; }

# Verificar Tor
if ! command -v tor &>/dev/null; then
  echo "[!] Tor não encontrado. Instalando..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y tor
  elif command -v brew &>/dev/null; then
    brew install tor
  else
    echo "Instale o Tor manualmente: https://www.torproject.org/"
  fi
fi

# Criar .env se não existir
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Configure o arquivo .env antes de continuar!"
  echo "   - Defina LILITH_PASSWORD (senha de acesso)"
  echo "   - Defina ONION_SEARCH_KEY (busca dark web)"
  echo ""
  read -p "Pressione Enter para abrir o .env no editor (ou Ctrl+C para cancelar)..."
  ${EDITOR:-nano} .env
fi

# Instalar dependências Python
echo "[*] Instalando dependências Python..."
pip install -r requirements.txt

echo ""
echo "=== Setup completo ==="
echo ""
echo "Para iniciar o Tor:"
echo "  tor &"
echo ""
echo "Para iniciar Lilith:"
echo "  python app.py"
echo ""
echo "Acesse: http://localhost:5000"
