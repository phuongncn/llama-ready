import os
import glob
import subprocess
import config


def find_models():
    pattern = os.path.join(config.MODELS_DIR, "**", "*.gguf")
    all_files = glob.glob(pattern, recursive=True)
    return [
        f for f in sorted(all_files)
        if "mmproj" not in os.path.basename(f).lower()
        and not any(f.endswith(f"-000{i}.gguf") for i in range(2, 10))
        and not any(f.endswith(f"-00{i:02d}.gguf") for i in range(10, 100))
    ]


def check_turbo_support():
    try:
        out = subprocess.run([config.LLAMA_BIN, "--help"], capture_output=True, text=True, timeout=5)
        return "turbo" in out.stdout.lower() or "turbo" in out.stderr.lower()
    except Exception:
        return False




def build_llama_cmd(model_file, mmproj_file, port, ctx, gpu_layers,
                    parallel, batch, ubatch, ctk, ctv, threads, threads_batch,
                    reasoning, nommap, nocache):
    cmd = [
        config.LLAMA_BIN,
        "-m", model_file,
        "--host", "0.0.0.0",
        "--port", str(port),
        "--n-gpu-layers", str(gpu_layers),
        "--ctx-size", str(ctx),
        "-ctk", ctk, "-ctv", ctv,
        "-b", str(batch), "-ub", str(ubatch),
        "--parallel", str(parallel),
        "--threads", str(threads),
        "--threads-batch", str(threads_batch),
        "-fa", "1",
        "--jinja",
        "--reasoning-budget", "-1" if reasoning else "0",
    ]
    if nocache:  cmd.append("--no-cache-prompt")
    if nommap:   cmd.append("--no-mmap")
    if mmproj_file: cmd += ["--mmproj", mmproj_file]
    return cmd