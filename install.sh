#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=== llama-ready installer ==="

if ! command -v python3 &>/dev/null; then
    echo "[Error] python3 not found. Install Python 3.8+ first."
    exit 1
fi

if [ ! -d "$DIR/proxy_env" ]; then
    echo "[*] Creating virtualenv..."
    python3 -m venv "$DIR/proxy_env"
else
    echo "[✓] proxy_env already exists, updating deps..."
fi

echo "[*] Installing dependencies..."
"$DIR/proxy_env/bin/pip" install --upgrade pip -q
"$DIR/proxy_env/bin/pip" install -r "$DIR/requirements.txt"

echo ""
echo "[✓] Install complete."
echo ""
echo "Prerequisites:"
echo "  - llama.cpp binary : ~/llama.cpp/build/bin/llama-server"
echo "  - Models dir       : ~/models/*.gguf"
echo ""
echo "Run: ./run.sh"