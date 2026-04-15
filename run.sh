#!/bin/bash

# Change to script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ ! -d "$DIR/proxy_env" ]; then
    echo "[Error] proxy_env not found. Run ./install.sh first."
    exit 1
fi

# ── Handle CLI arguments ──────────────────────────────────────────────────
case "$1" in
    stop|kill|--stop|--kill|-k)
        echo "Stopping all llama-server processes..."
        if command -v pkill &> /dev/null; then
            pkill -9 llama-server
        elif command -v taskkill &> /dev/null; then
            taskkill /F /IM llama-server.exe
        fi
        echo "Done."
        exit 0
        ;;
    *)
        # Start the proxy
        echo "=== Starting llama-ready ==="
        source "$DIR/proxy_env/bin/activate"
        python "$DIR/py_scripts/llm_ready.py" "$@"
        ;;
esac
