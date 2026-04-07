#!/usr/bin/env bash
# Dental Insights — Environment Setup
# Run this before using the download script.

set -euo pipefail

echo "=== Dental Insights — Dataset Environment Setup ==="

# 1. Install Python dependencies
echo "[1/4] Installing Python dependencies..."
pip install -r "$(dirname "$0")/requirements.txt"

# 2. Check Kaggle credentials
echo "[2/4] Checking Kaggle credentials..."
if [ -f "$HOME/.kaggle/kaggle.json" ]; then
    echo "  Kaggle credentials found."
else
    echo "  WARNING: Kaggle credentials not found."
    echo "  To download Kaggle datasets:"
    echo "    1. Go to https://www.kaggle.com/settings"
    echo "    2. Click 'Create New Token'"
    echo "    3. Save kaggle.json to ~/.kaggle/kaggle.json"
    echo "    4. chmod 600 ~/.kaggle/kaggle.json"
fi

# 3. Check Roboflow API key
echo "[3/4] Checking Roboflow API key..."
if [ -n "${ROBOFLOW_API_KEY:-}" ]; then
    echo "  Roboflow API key found."
else
    echo "  WARNING: ROBOFLOW_API_KEY not set."
    echo "  To download Roboflow datasets:"
    echo "    export ROBOFLOW_API_KEY='your_key_here'"
    echo "    Get your key from: https://app.roboflow.com/settings/api"
fi

# 4. Create folder structure
echo "[4/4] Creating folder structure..."
python "$(dirname "$0")/download_datasets.py" --setup-folders --output-dir "${1:-./dental_data}"

echo ""
echo "=== Setup complete ==="
echo "Run the download script:"
echo "  python dental-datasets/download_datasets.py --output-dir ./dental_data"
echo ""
echo "For a dry run first:"
echo "  python dental-datasets/download_datasets.py --output-dir ./dental_data --dry-run"
echo ""
echo "To list datasets needing manual access:"
echo "  python dental-datasets/download_datasets.py --output-dir ./dental_data --list-manual"
