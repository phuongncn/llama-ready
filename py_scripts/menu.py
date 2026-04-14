import os, glob
import config
from config import find_free_port, save_config, load_config
from models import find_models, check_turbo_support, build_llama_cmd


def interactive_menu():
    saved = load_config()
    if saved:
        print("\n=== Found saved config ===")
        print(f"  Model       : {os.path.basename(saved.get('model_file',''))}")
        print(f"  Idle timeout: {saved.get('idle_minutes', 60)} minutes")
        print(f"  CTX         : {saved.get('ctx')} | ctk={saved.get('ctk','q8_0')} ctv={saved.get('ctv','q8_0')} | GPU layers: {saved.get('gpu_layers')}")
        reuse = input("\nUse this config? (Y/n): ").strip().lower()
        if reuse in ("", "y"):
            config.IDLE_TIMEOUT = saved["idle_minutes"] * 60
            llm_port = find_free_port(saved["port"])
            if llm_port != saved["port"]:
                print(f"[Config] Port {saved['port']} in use, switching to {llm_port}.")
            config.LLAMA_SERVER_URL = f"http://localhost:{llm_port}"
            ctk = saved.get("ctk") or saved.get("kv_type", "q8_0")
            ctv = saved.get("ctv") or saved.get("kv_type", "q8_0")
            config.LLAMA_CMD = build_llama_cmd(
                saved["model_file"], saved.get("mmproj_file"),
                llm_port, saved["ctx"], saved["gpu_layers"],
                saved["parallel"], saved["batch"], saved["ubatch"],
                ctk, ctv, saved["threads"], saved["threads_batch"],
                saved["reasoning"], saved["nommap"], saved.get("nocache", True)
            )
            config.CUDA_ENV = {}
            if saved.get("cuda_graph"):   config.CUDA_ENV["GGML_CUDA_GRAPH_OPT"] = "1"
            if saved.get("cuda_cublas"):  config.CUDA_ENV["GGML_CUDA_FORCE_CUBLAS"] = "1"
            print(f"[Config] Loaded saved config. LLM port: {llm_port}\n")
            return

    print("\n" + "═"*55)
    print("   LLAMA-READY — Startup Configuration")
    print("═"*55)

    if not os.path.isfile(config.LLAMA_BIN):
        print(f"[Error] Binary not found: {config.LLAMA_BIN}")
        exit(1)

    turbo_supported = check_turbo_support()
    if turbo_supported:
        print("[✓] llama-server supports TurboQuant")

    models = find_models()
    if not models:
        print(f"[Error] No models found in {config.MODELS_DIR}")
        exit(1)

    print("\n=== Available models ===")
    for i, m in enumerate(models):
        print(f"  {i+1}. {os.path.basename(m)}")
        print(f"      {os.path.dirname(m)}")

    while True:
        try:
            idx = int(input(f"\nSelect model (1-{len(models)}): ")) - 1
            if 0 <= idx < len(models):
                model_file = models[idx]
                break
        except ValueError:
            pass
        print("Invalid selection, try again.")

    model_dir    = os.path.dirname(model_file)
    mmproj_files = glob.glob(os.path.join(model_dir, "mmproj*.gguf"))
    mmproj_file  = None
    if mmproj_files:
        print(f"\nFound mmproj: {os.path.basename(mmproj_files[0])}")
        if input("Use this mmproj? (Y/n): ").strip().lower() in ("", "y"):
            mmproj_file = mmproj_files[0]

    print("\n=== Proxy settings ===")
    idle_input = input("Auto-stop llama after how many idle minutes? [60]: ").strip()
    config.IDLE_TIMEOUT = int(idle_input) * 60 if idle_input.isdigit() else 3600

    print("\n=== llama-server settings (Enter = default) ===")
    def ask(prompt, default):
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else str(default)

    llm_free_port = find_free_port(config.LLM_PORT_DEFAULT)
    port          = int(ask("port", llm_free_port))
    ctx           = int(ask("ctx-size", 256000))
    gpu_layers    = int(ask("n-gpu-layers", 99))
    parallel      = int(ask("parallel", 1))
    batch         = int(ask("batch -b", 4096))
    ubatch        = int(ask("ubatch -ub", 4096))

    print("\n─── KV Cache ───")
    if turbo_supported:
        print("  Standard   : q4_0 / q8_0 / f16")
        print("  TurboQuant : turbo2 (6.4x) / turbo3 (4.6x) / turbo4 (3.8x)")
        print("  Suggested  : -ctk q8_0  -ctv turbo3")
    ctk = ask("KV key cache -ctk", "q8_0")
    ctv = ask("KV val cache -ctv", "q8_0")

    threads       = int(ask("decode threads", 4))
    threads_batch = int(ask("prefill threads", 20))

    print("\n=== Options ===")
    reasoning  = input("reasoning-budget -1 (Y/n) [Y]: ").strip().lower() in ("", "y")
    nommap     = input("no-mmap (Y/n) [Y]: ").strip().lower() in ("", "y")
    nocache    = input("no-cache-prompt (Y/n) [Y]: ").strip().lower() in ("", "y")
    cuda_graph = input("CUDA graph optimization (Y/n) [Y]: ").strip().lower() in ("", "y")
    cuda_cublas= input("CUDA force cuBLAS (Y/n) [Y]: ").strip().lower() in ("", "y")


    config.LLAMA_SERVER_URL = f"http://localhost:{port}"
    config.CUDA_ENV = {}
    if cuda_graph:  config.CUDA_ENV["GGML_CUDA_GRAPH_OPT"] = "1"
    if cuda_cublas: config.CUDA_ENV["GGML_CUDA_FORCE_CUBLAS"] = "1"

    config.LLAMA_CMD = build_llama_cmd(
        model_file, mmproj_file, port, ctx, gpu_layers,
        parallel, batch, ubatch, ctk, ctv, threads, threads_batch,
        reasoning, nommap, nocache
    )

    save_config({
        "model_file": model_file, "mmproj_file": mmproj_file,
        "idle_minutes": config.IDLE_TIMEOUT // 60,
        "port": port, "ctx": ctx, "gpu_layers": gpu_layers,
        "parallel": parallel, "batch": batch, "ubatch": ubatch,
        "ctk": ctk, "ctv": ctv,
        "threads": threads, "threads_batch": threads_batch,
        "reasoning": reasoning, "nommap": nommap, "nocache": nocache,
        "cuda_graph": cuda_graph, "cuda_cublas": cuda_cublas,
    })

    print("\n=== Summary ===")
    print(f"  Model       : {os.path.basename(model_file)}")
    print(f"  Mmproj      : {os.path.basename(mmproj_file) if mmproj_file else 'None'}")
    print(f"  Idle timeout: {config.IDLE_TIMEOUT//60} minutes")
    print(f"  LLM port    : {port}")
    print(f"  CTX         : {ctx} | ctk={ctk} ctv={ctv} | GPU layers: {gpu_layers}")
    if config.CUDA_ENV:
        print(f"  CUDA env    : {config.CUDA_ENV}")
    print()