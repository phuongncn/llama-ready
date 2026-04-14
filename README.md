# llama-ready — Smart Lifecycle Proxy for llama.cpp

> Never waste GPU power on idle models again.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![llama.cpp](https://img.shields.io/badge/llama.cpp-compatible-green.svg)](https://github.com/ggerganov/llama.cpp)

## The Problem

`llama-server` loads your model into VRAM and keeps it there forever — even at 3am when nobody is using it. That's wasted power, locked VRAM, and a hotter GPU for nothing.

## The Solution

`llama-ready` sits between your AI clients and `llama-server`. It **starts the model on the first request** and **automatically shuts it down** after N minutes of idle. Your clients never know the difference.

## How It Works

```
Your AI client (OpenWebUI, Continue.dev, curl...)
        │
        ▼
┌─────────────────────────┐
│   llama-ready proxy     │  ← always running, zero overhead
│   localhost:9090        │
└────────────┬────────────┘
             │  starts on first request
             │  stops after idle timeout
             ▼
┌─────────────────────────┐
│   llama-server          │  ← only runs when needed
│   localhost:8080        │
└─────────────────────────┘
```

## Features

- **Auto start/stop** — llama-server starts on first request, shuts down after idle timeout (default: 60 min)
- **Zero client changes** — drop-in replacement: just point OpenWebUI / Continue.dev / any OpenAI-compatible client to the proxy URL
- **Config persistence** — answer the setup wizard once, reuse on next launch
- **Model auto-detection** — scans your models directory for `.gguf` files automatically
- **Vision model support** — auto-detects `mmproj` files; converts WebP → JPEG transparently
- **Crash recovery** — idle watcher auto-restarts llama-server if it crashes
- **Full parameter control** — ctx-size, gpu-layers, KV cache types (including TurboQuant), parallel, batch, CUDA flags, MoE options
- **Multi-instance** — run `run.sh` multiple times for different models in separate tmux sessions

## Quick Start

### Requirements

- Python 3.8+
- [llama.cpp](https://github.com/ggerganov/llama.cpp) built with `llama-server`
- tmux (for `run.sh` — optional, you can run `llm_ready.py` directly)

### Install

```bash
git clone https://github.com/phuongncn/llama-ready
cd llama-ready
python -m venv proxy_env
source proxy_env/bin/activate   # Windows: proxy_env\Scripts\activate
pip install -r requirements.txt
```

### Run

```bash
# Default paths (~/models and ~/llama.cpp/build/bin/llama-server)
python llm_ready.py

# Custom paths
python llm_ready.py --models-dir /data/models --llama-bin /opt/llama/build/bin/llama-server

# With tmux session manager (Linux/macOS)
./run.sh
```

### Point your client to the proxy

Replace your `llama-server` URL with:
```
http://localhost:9090
```
That's it. The proxy is fully OpenAI API compatible.

## CLI Options

| Flag | Default | Description |
|---|---|---|
| `--models-dir` | `~/models` | Directory to scan for `.gguf` models |
| `--llama-bin` | `~/llama.cpp/build/bin/llama-server` | Path to `llama-server` binary |
| `--proxy-port` | `9090` | Proxy listen port (auto-increments if busy) |
| `--llm-port` | `8080` | llama-server port (auto-increments if busy) |

## Configuration Wizard

On first run, an interactive wizard walks you through:

- Model selection (auto-detected from `--models-dir`)
- Idle timeout
- Context size, GPU layers, KV cache type (`q4_0` / `q8_0` / `f16` / TurboQuant)
- Parallel slots, batch sizes, thread counts
- CUDA graph optimization, cuBLAS, MoE flags

Settings are saved to `llm_proxy_config.json` and reused on next launch.

## Platform Support

| Platform | Status | Notes |
|---|---|---|
| Linux | ✅ Full support | Recommended |
| macOS | ✅ Full support | |
| Windows | ⚠️ Partial | Run `llm_ready.py` directly; `run.sh` requires WSL |

## Project Structure

```
llama-ready/
├── llm_ready.py     # Entrypoint — argparse, startup, signal handling
├── config.py        # Globals, config load/save, port finder
├── models.py        # Model discovery, llama-server command builder
├── menu.py          # Interactive setup wizard
├── manager.py       # llama-server lifecycle (start/stop/watch)
├── proxy.py         # Flask proxy, WebP→JPEG conversion
├── run.sh           # tmux session manager (Linux/macOS)
└── requirements.txt
```

## License

MIT — see [LICENSE](LICENSE)