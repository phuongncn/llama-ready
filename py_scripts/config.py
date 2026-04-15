import os
import threading
import time

PROXY_PORT_DEFAULT = 9090
LLM_PORT_DEFAULT   = 8080
MODELS_DIR         = os.path.expanduser("~/models")
LLAMA_BIN          = os.path.expanduser("~/llama.cpp/build/bin/llama-server")

PROXY_PORT       = None
LLAMA_SERVER_URL = None
IDLE_TIMEOUT     = 3600
LLAMA_CMD        = []
CUDA_ENV         = {}
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE      = os.path.join(_ROOT, "llm_proxy_config.json")
LOG_FILE         = os.path.join(_ROOT, "llama_server.log")

# Instance pool for multi-backend load balancing
instance_pool = {}
# Format: { port: {"process": Popen, "active_requests": int, "last_used": timestamp} }
MAX_INSTANCES = 3
IDLE_TIMEOUT = 3600  # 60 minutes - Global idle timeout for stopping ALL instances
INSTANCE_IDLE_TIMEOUT = 300  # 5 minutes - Per-instance idle timeout for aggressive scale-down
CONCURRENT_PER_INSTANCE = 1  # Threshold to trigger scaling

# Thread-safe locks
llama_lock = threading.Lock()
pool_lock = threading.Lock()
global_last_activity = time.time()


def find_free_port(start, max_tries=20):
    import socket
    for port in range(start, start + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}–{start + max_tries - 1}")


def save_config(cfg: dict):
    import json
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print(f"[Config] Saved → {CONFIG_FILE}")


def load_config():
    import json
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return None