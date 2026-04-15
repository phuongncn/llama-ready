# llama-ready — Smart Load Balancer & Auto-Scaler for llama.cpp

> Zero idle waste. Zero blocking. Seamless scaling.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![llama.cpp](https://img.shields.io/badge/llama.cpp-compatible-green.svg)](https://github.com/ggerganov/llama.cpp)

## What is it?

`llama-ready` acts as a highly intelligent Layer-7 Reverse Proxy between your AI clients and `llama-server`.

**The old way:** Running `llama-server` 24/7 wastes VRAM and power. On the other hand, running just one instance during heavy concurrent workloads (like an AI Agent chewing through code while you ask a quick question) blocks your requests and often leads to Out-Of-Memory (OOM) crashes due to Context Window limits.

**The `llama-ready` way:**
- It **sleeps at 0 VRAM** when idle.
- It **spawns the first instance instantly** on your first request.
- It **auto-scales (spawns more instances)** on different ports if the current instances are busy.
- It **aggressively scales down** idle backend instances to free up VRAM, while keeping one alive until a global idle timeout is reached.

Your clients (OpenWebUI, Continue.dev, AI Agents) simply connect to a single endpoint (`localhost:9090`), and `llama-ready` handles all the complex routing and lifecycle management behind the scenes.

## Architecture: How It Works

    Your AI clients (OpenWebUI, AI Agents, IDEs, curl...)
            │
            ▼ (Single Endpoint)
    ┌─────────────────────────┐
    │   llama-ready Proxy     │  ← Always running, zero GPU overhead
    │   localhost:9090        │
    └────────────┬────────────┘
                 │  Routes request based on active load
                 │  Auto-starts new instances if busy
                 │  Auto-stops instances if idle
                 ▼
          ┌─────────────┐
          │ llama Pool  │
          ├─────────────┤
          │ Port: 8080  │ ← Instance 1 (Primary)
          │ Port: 8082  │ ← Instance 2 (Scaled up for heavy load)
          │ Port: 8083  │ ← Instance 3 (Auto-killed after 5 min idle)
          └─────────────┘

## Key Features

- 🚀 **Smart Auto-Scaling:** Define a `MAX_INSTANCES` pool. The proxy monitors active requests and seamlessly spins up new `llama-server` instances to handle concurrent traffic without blocking your workflow.
- 🔋 **Aggressive Scale-Down (Eco-mode):** Individual scaled instances are automatically killed after a short period of inactivity (e.g., 5-15 mins) to immediately release VRAM.
- 💤 **Global Idle Shutdown:** If the entire system is idle for N minutes (default: 60), it shuts down completely (Zero VRAM footprint).
- 🔌 **Drop-in Replacement:** Zero client configuration changes needed. Just point your OpenAI-compatible client to the proxy URL.
- 🧠 **Perfect for AI Agents & Coding:** By offloading concurrent requests to separate instances, you prevent massive Context Window conflicts (e.g., OpenClaw eating 128k-256k tokens won't freeze your IDE's auto-complete request).
- 💾 **Config Persistence:** Setup your optimal `ctx-size`, `gpu-layers`, and `KV cache` once via an interactive CLI, and it remembers everything for the next run.
- 🖼️ **Vision Model Support:** Transparently converts WebP to JPEG on the fly and auto-detects `mmproj` files.

## Quick Start

### Requirements

- Python 3.8+
- [llama.cpp](https://github.com/ggerganov/llama.cpp) built with `llama-server`
- tmux (optional, but recommended for background running)

### Install

    git clone https://github.com/phuongncn/llama-ready
    cd llama-ready
    chmod +x install.sh run.sh
    ./install.sh

### Run

Simply execute the run script. On the first launch, an interactive wizard will guide you to select your `.gguf` model and configure the Load Balancer settings.

    ./run.sh

- **Stop all processes gracefully:**

    ./run.sh stop

### Point your client to the proxy

Replace your current `llama-server` endpoint with the proxy's address:

    http://localhost:9090

That's it. Send a request and watch the magic happen in the console logs.

## Configuration Wizard Overview

On the first run, the interactive wizard configures:
- **Model selection:** Auto-detected from your `--models-dir`.
- **Global Idle timeout:** Shut down the entire system after X minutes of zero traffic.
- **Max Instances:** How many `llama-server` processes the Load Balancer is allowed to spawn (e.g., Set to 2 or 3 based on your total VRAM).
- **Instance Idle Timeout:** How fast to kill a secondary instance to save VRAM.
- **llama.cpp specifics:** Context size, KV cache type (`q4_0` / `q8_0` / `f16` / TurboQuant), parallel slots, and CUDA optimizations.

Settings are saved to `llm_proxy_config.json`.

## CLI Options (Advanced)

| Flag | Default | Description |
|---|---|---|
| `--models-dir` | `~/models` | Directory to scan for `.gguf` models |
| `--llama-bin` | `~/llama.cpp/build/bin/llama-server` | Path to `llama-server` binary |
| `--proxy-port` | `9090` | The single entry point for clients |
| `--llm-port` | `8080` | Starting port for the llama-server pool |

## Platform Support

| Platform | Status |
|---|---|
| Linux | ✅ Recommended |
| macOS | ✅ Supported |
| Windows | ✅ Supported (via WSL or Native Python) |

## License

MIT — see [LICENSE](LICENSE)