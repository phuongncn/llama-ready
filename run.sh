#!/bin/bash

# Change to script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ ! -d "$DIR/proxy_env" ]; then
    echo "[Error] proxy_env not found. Run ./install.sh first."
    exit 1
fi

SESSION_PREFIX="proxy_llm"

# Use switch-client if inside tmux, attach-session if outside
tmux_goto() {
    local target="$1"
    if [ -n "$TMUX" ]; then
        tmux switch-client -t "$target"
    else
        tmux attach-session -t "$target"
    fi
}

# List running sessions with this prefix (auto-clean dead sessions)
list_sessions() {
    tmux list-sessions -F "#{session_name}" 2>/dev/null | grep "^${SESSION_PREFIX}[0-9]*$" | while read -r s; do
        # Get process running in pane
        cmd=$(tmux list-panes -t "$s" -F "#{pane_current_command}" 2>/dev/null | head -1)
        if [[ "$cmd" != *python* ]]; then
            tmux kill-session -t "$s" 2>/dev/null  # proxy exited, clean up session
        else
            echo "$s"
        fi
    done | sort -t_ -k3 -V
}

kill_all_sessions() {
    local sessions=( $(list_sessions) )
    if [ ${#sessions[@]} -eq 0 ]; then
        echo "No instances running."
        exit 0
    fi
    echo "=== Stopping all ${#sessions[@]} instances ==="
    for s in "${sessions[@]}"; do
        echo "  Stopping $s..."
        tmux send-keys -t "$s" C-c 2>/dev/null
        sleep 1
        tmux kill-session -t "$s" 2>/dev/null
    done
    echo "All instances stopped."
}

# ── Handle CLI arguments ──────────────────────────────────────────────────
case "$1" in
    stop|kill|--stop|--kill|-k)
        kill_all_sessions
        exit 0
        ;;
esac

RUNNING=( $(list_sessions) )

if [ ${#RUNNING[@]} -gt 0 ]; then
    echo "=== Running proxy instances ==="
    for i in "${!RUNNING[@]}"; do
        echo "  $((i+1)). ${RUNNING[$i]}"
    done
    echo "  $((${#RUNNING[@]}+1)). Start new instance"
    echo "  0. Stop all"
    echo ""
    read -rp "Select (Enter = attach to first): " CHOICE

    if [[ -z "$CHOICE" ]]; then
        CHOICE=1
    fi

    if [[ "$CHOICE" == "0" ]]; then
        kill_all_sessions
        exit 0
    fi

    if [[ "$CHOICE" =~ ^[0-9]+$ ]] && [ "$CHOICE" -le "${#RUNNING[@]}" ]; then
        SESSION="${RUNNING[$((CHOICE-1))]}"
        echo "Attaching to tmux session '$SESSION'..."
        sleep 1
        tmux_goto "$SESSION"
        exit 0
    fi
    # If new or out-of-range → fall through to create new
fi

# Find unused session name: proxy_llm1, proxy_llm2, ...
IDX=1
while tmux has-session -t "${SESSION_PREFIX}${IDX}" 2>/dev/null; do
    IDX=$((IDX + 1))
done
SESSION="${SESSION_PREFIX}${IDX}"

echo "=== Starting llama-ready (session: $SESSION) ==="

# Create new tmux session and run Python inside
tmux new-session -d -s "$SESSION" -x 220 -y 50 \
    "bash -c \"source '$DIR/proxy_env/bin/activate' && exec python '$DIR/py_scripts/llm_ready.py'\""

echo "Started in tmux session '$SESSION'. Attaching to configure..."
echo "(Ctrl+B D to detach — process keeps running)"
sleep 1
tmux_goto "$SESSION"
