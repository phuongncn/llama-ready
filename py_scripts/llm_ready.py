import argparse, os, signal, threading
import config
from menu import interactive_menu
from manager import start_llama, stop_llama, idle_watcher
from proxy import app
from config import find_free_port


def shutdown_handler(sig, frame):
    print("\n[Proxy] Shutdown signal received, cleaning up...")
    stop_llama()
    print("[Proxy] llama-server stopped. Bye!")
    os._exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="llama-ready — smart lifecycle proxy for llama.cpp")
    parser.add_argument("--models-dir", default=os.path.expanduser("~/models"),
                        help="Directory to scan for .gguf models")
    parser.add_argument("--llama-bin",  default=os.path.expanduser("~/llama.cpp/build/bin/llama-server"),
                        help="Path to llama-server binary")
    parser.add_argument("--proxy-port", type=int, default=9090,
                        help="Starting port for proxy (auto-increments if busy)")
    parser.add_argument("--llm-port",   type=int, default=8080,
                        help="Starting port for llama-server (auto-increments if busy)")
    args = parser.parse_args()

    config.MODELS_DIR         = args.models_dir
    config.LLAMA_BIN          = args.llama_bin
    config.PROXY_PORT_DEFAULT = args.proxy_port
    config.LLM_PORT_DEFAULT   = args.llm_port
    config.PROXY_PORT         = find_free_port(args.proxy_port)

    interactive_menu()

    signal.signal(signal.SIGINT,  shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    threading.Thread(target=start_llama,  daemon=False).start()
    threading.Thread(target=idle_watcher, daemon=True).start()

    print(f"╔══════════════════════════════════════════════╗")
    print(f"║         LLAMA-READY — proxy running          ║")
    print(f"╠══════════════════════════════════════════════╣")
    print(f"║  PROXY  → http://0.0.0.0:{config.PROXY_PORT:<19}║")
    print(f"║  LLM    → {config.LLAMA_SERVER_URL:<34}║")
    print(f"║  Idle shutdown : {config.IDLE_TIMEOUT//60} min{'':<24}║")
    print(f"╚══════════════════════════════════════════════╝")

    from waitress import serve
    serve(app, host='0.0.0.0', port=config.PROXY_PORT, threads=8)