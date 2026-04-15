import os
import time
import signal
import subprocess
import threading
import platform
import config


def is_llama_ready(port):
    """Check if llama-server on given port is responding."""
    import requests
    try:
        r = requests.get(f"http://localhost:{port}/health", timeout=2)
        return r.status_code == 200
    except:
        return False


def find_free_port(start, max_tries=20):
    """Find a free port starting from start."""
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


def start_instance(port):
    """Start a llama-server instance on the given port."""
    print(f"[InstanceManager] Starting llama-server on port {port}...")
    print(f"[InstanceManager] CMD: {' '.join(config.LLAMA_CMD)}")
    if config.CUDA_ENV:
        print(f"[InstanceManager] ENV: {config.CUDA_ENV}")
    print(f"[InstanceManager] Log: {config.LOG_FILE}")
    
    env = os.environ.copy()
    env.update(config.CUDA_ENV)
    log_fd = open(config.LOG_FILE, "a")
    log_fd.write(f"\n{'='*60}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] START (port={port})\n")
    log_fd.write(f"CMD: {' '.join(config.LLAMA_CMD)}\n")
    log_fd.write(f"ENV: {config.CUDA_ENV}\n{'='*60}\n")
    log_fd.flush()
    
    kwargs = dict(stdout=log_fd, stderr=log_fd, env=env)
    if platform.system() != "Windows":
        kwargs["preexec_fn"] = os.setsid
    
    # FIX: Update --port parameter dynamically for this instance
    cmd = list(config.LLAMA_CMD)  # Create a copy to avoid modifying the original list
    try:
        port_index = cmd.index("--port")
        cmd[port_index + 1] = str(port)
    except ValueError:
        pass  # Fallback if --port not found
    
    proc = subprocess.Popen(cmd, **kwargs)
    
    # Wait for health check
    for i in range(300):
        if is_llama_ready(port):
            print(f"[InstanceManager] llama-server on port {port} ready after {i+1}s")
            return proc
        time.sleep(1)
    print(f"[InstanceManager] WARNING: llama-server on port {port} not responding after 300s!")
    return None


def stop_instance(port):
    """Stop a llama-server instance on the given port."""
    print(f"[InstanceManager] Stopping llama-server on port {port}...")
    with config.pool_lock:
        if port in config.instance_pool:
            proc = config.instance_pool[port]["process"]
            if proc and proc.poll() is None:
                if platform.system() != "Windows":
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                else:
                    proc.terminate()
                del config.instance_pool[port]
                print(f"[InstanceManager] Instance on port {port} stopped.")


def stop_all_instances():
    """Stop all llama-server instances."""
    with config.pool_lock:
        ports = list(config.instance_pool.keys())
    for port in ports:
        stop_instance(port)
    print("[InstanceManager] All instances stopped.")


def get_best_instance(req_id):
    """
    Find the best instance for a new request.
    Returns the port to use.
    """
    with config.pool_lock:
        # Step 1: Find an instance with available capacity
        for port, info in config.instance_pool.items():
            if info["active_requests"] < config.CONCURRENT_PER_INSTANCE:
                print(f"[Proxy] [REQ:{req_id}] Instance {port} is available ({info['active_requests']} active).")
                return port
        
        # Step 2: If all busy and under MAX_INSTANCES, scale up
        if len(config.instance_pool) < config.MAX_INSTANCES:
            # Find a free port
            port = find_free_port(config.LLM_PORT_DEFAULT)
            print(f"[Proxy] [REQ:{req_id}] Scaling: Starting new instance on port {port}...")
            
            proc = start_instance(port)
            if proc:
                config.instance_pool[port] = {
                    "process": proc,
                    "active_requests": 0,
                    "last_used": time.time()
                }
                print(f"[Proxy] [REQ:{req_id}] Instance {port} started successfully.")
                return port
            else:
                print(f"[Proxy] [REQ:{req_id}] Failed to start instance on port {port}.")
        
        # Step 3: At MAX_INSTANCES, return the least busy one
        if config.instance_pool:
            least_busy = min(config.instance_pool.items(), key=lambda x: x[1]["active_requests"])
            port, info = least_busy
            print(f"[Proxy] [REQ:{req_id}] Instance {port} is busy ({info['active_requests']} active).")
            return port
    
    # No instances available - this shouldn't happen if MAX_INSTANCES > 0
    print(f"[Proxy] [REQ:{req_id}] ERROR: No instances available!")
    return None


def increment_active(port):
    """Increment the active request counter for an instance."""
    with config.pool_lock:
        if port in config.instance_pool:
            config.instance_pool[port]["active_requests"] += 1
            config.instance_pool[port]["last_used"] = time.time()
            config.global_last_activity = time.time()


def decrement_active(port):
    """Decrement the active request counter for an instance."""
    with config.pool_lock:
        if port in config.instance_pool:
            config.instance_pool[port]["active_requests"] = max(0, config.instance_pool[port]["active_requests"] - 1)


def idle_watcher():
    """Monitor idle time and stop instances if idle for too long.
    
    Implements aggressive scale-down:
    - Individual instances idle > INSTANCE_IDLE_TIMEOUT (5 min) → stopped (if not the last one)
    - All instances idle > IDLE_TIMEOUT (60 min) → all stopped
    """
    while True:
        time.sleep(60)
        with config.pool_lock:
            running_count = sum(1 for info in config.instance_pool.values()
                               if info["process"] and info["process"].poll() is None)
        
        if running_count > 0:
            idle = time.time() - config.global_last_activity
            print(f"[IdleWatcher] Idle {int(idle)}s / {config.IDLE_TIMEOUT}s ({running_count} instances running)")
            
            if idle >= config.IDLE_TIMEOUT:
                print("[IdleWatcher] Global idle timeout reached. Stopping all instances...")
                stop_all_instances()
            else:
                # Aggressive scale-down: stop individual idle instances (keep at least 1 running)
                now = time.time()
                ports_to_stop = []
                
                for port, info in config.instance_pool.items():
                    if info["process"] and info["process"].poll() is None:
                        # Check if this instance is idle
                        if info["active_requests"] == 0 and (now - info["last_used"]) >= config.INSTANCE_IDLE_TIMEOUT:
                            # Only stop if it's not the last running instance
                            if running_count > 1:
                                ports_to_stop.append(port)
                                running_count -= 1
                                print(f"[IdleWatcher] Instance {port} idle for {int(now - info['last_used'])}s > {config.INSTANCE_IDLE_TIMEOUT}s. Scaling down.")
                
                # Stop idle instances (outside lock to avoid deadlock)
                for port in ports_to_stop:
                    stop_instance(port)
        else:
            # Check if any instance crashed
            with config.pool_lock:
                for port, info in list(config.instance_pool.items()):
                    if info["process"] and info["process"].poll() is not None:
                        print(f"[IdleWatcher] Instance on port {port} crashed! Restarting...")
                        del config.instance_pool[port]
                        proc = start_instance(port)
                        if proc:
                            config.instance_pool[port] = {
                                "process": proc,
                                "active_requests": 0,
                                "last_used": time.time()
                            }

