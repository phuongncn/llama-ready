import os
import time
import signal
import subprocess
import threading
import platform
import config


def is_llama_ready():
    import requests
    try:
        r = requests.get(f"{config.LLAMA_SERVER_URL}/health", timeout=2)
        return r.status_code == 200
    except:
        return False


def start_llama():
    with config.llama_lock:
        if config.llama_process and config.llama_process.poll() is None:
            return
        print("[LlamaManager] Starting llama-server...")
        print(f"[LlamaManager] CMD: {' '.join(config.LLAMA_CMD)}")
        if config.CUDA_ENV:
            print(f"[LlamaManager] ENV: {config.CUDA_ENV}")
        print(f"[LlamaManager] Log: {config.LOG_FILE}")
        env = os.environ.copy()
        env.update(config.CUDA_ENV)
        log_fd = open(config.LOG_FILE, "a")
        log_fd.write(f"\n{'='*60}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] START\n")
        log_fd.write(f"CMD: {' '.join(config.LLAMA_CMD)}\n")
        log_fd.write(f"ENV: {config.CUDA_ENV}\n{'='*60}\n")
        log_fd.flush()
        kwargs = dict(stdout=log_fd, stderr=log_fd, env=env)
        if platform.system() != "Windows":
            kwargs["preexec_fn"] = os.setsid
        config.llama_process = subprocess.Popen(config.LLAMA_CMD, **kwargs)

    for i in range(300):
        if is_llama_ready():
            print(f"[LlamaManager] llama-server ready after {i+1}s")
            return
        time.sleep(1)
    print("[LlamaManager] WARNING: llama-server not responding after 300s!")


def stop_llama():
    with config.llama_lock:
        if config.llama_process and config.llama_process.poll() is None:
            print("[LlamaManager] Stopping llama-server...")
            if platform.system() != "Windows":
                os.killpg(os.getpgid(config.llama_process.pid), signal.SIGTERM)
            else:
                config.llama_process.terminate()
            config.llama_process = None


def idle_watcher():
    while True:
        time.sleep(60)
        with config.llama_lock:
            proc    = config.llama_process
            running = proc and proc.poll() is None
        if running:
            idle = time.time() - config.last_activity
            print(f"[IdleWatcher] Idle {int(idle)}s / {config.IDLE_TIMEOUT}s")
            if idle >= config.IDLE_TIMEOUT:
                stop_llama()
        else:
            if proc is not None:
                print("[IdleWatcher] llama-server crash detected! Restarting...")
                with config.llama_lock:
                    config.llama_process = None
                start_llama()


def ensure_llama_running():
    config.last_activity = time.time()
    with config.llama_lock:
        running = config.llama_process and config.llama_process.poll() is None
    if not running or not is_llama_ready():
        start_llama()