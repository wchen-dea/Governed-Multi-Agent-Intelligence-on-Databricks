#!/usr/bin/env python3
"""Run a pre-flight check for the local agent.

Run this before deploying to catch configuration and code errors early.

Usage:
    uv run runtime-preflight
"""

import contextlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

_IS_WINDOWS = sys.platform == "win32"

# Maximum wait time for server startup, in seconds.
SERVER_START_TIMEOUT = 60
# Maximum wait time for a response request, in seconds.
REQUEST_TIMEOUT = 60


def find_free_port() -> int:
    """Return an available ephemeral localhost port.

    Returns:
        Available TCP port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def start_server(port: int) -> subprocess.Popen:
    """Start the local server and wait until readiness logs are observed.

    Args:
        port: Local port used for server startup.

    Returns:
        Running server subprocess handle.
    """
    popen_kwargs = {}
    if _IS_WINDOWS:
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["preexec_fn"] = os.setsid

    proc = subprocess.Popen(
        ["uv", "run", "runtime-serve-backend", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        **popen_kwargs,
    )

    lines_queue: list[str] = []

    def _reader():
        # Streams lines as they arrive; not a list-copy, so list(iter(...)) would
        # block until EOF instead of letting the polling loop below react live.
        for line in iter(proc.stderr.readline, ""):
            lines_queue.append(line)  # noqa: PERF402

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    deadline = time.time() + SERVER_START_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            t.join(timeout=2)
            stderr = "".join(lines_queue)
            print(f"  Server exited early (code {proc.returncode})")
            if stderr:
                for line in stderr.strip().splitlines()[-20:]:
                    print(f"    {line}")
            sys.exit(1)

        while lines_queue:
            line = lines_queue.pop(0)
            if "Uvicorn running on" in line or "Application startup complete" in line:
                return proc

        time.sleep(0.5)

    stop_server(proc)
    print(f"  Server did not start within {SERVER_START_TIMEOUT}s")
    sys.exit(1)


def stop_server(proc: subprocess.Popen):
    """Terminate the server process gracefully, then force-kill if needed.

    Args:
        proc: Server subprocess handle.
    """
    if _IS_WINDOWS:
        proc.terminate()
    else:
        import signal

        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def check_health(base_url: str) -> bool:
    """Validate that the health endpoint reports a healthy status.

    Args:
        base_url: Base URL for local server endpoints.

    Returns:
        True when the health endpoint responds with healthy status.
    """
    try:
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("status") in {"healthy", "ok"}
    except Exception as e:
        print(f"  Health check failed: {e}")
        return False


def check_invocations(base_url: str, retries: int = 2) -> bool:
    """Send a minimal invocation request and validate response shape.

    Args:
        base_url: Base URL for local server endpoints.
        retries: Number of retry attempts after initial failure.

    Returns:
        True when invocation succeeds with expected output shape.
    """
    payload = json.dumps(
        {"input": [{"role": "user", "content": "Say hello in one word."}]}
    ).encode()

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                f"{base_url}/invocations",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read())
                # Confirm that the invocation response includes at least one output item.
                if "output" in data and len(data["output"]) > 0:
                    return True
                print(f"  Unexpected response shape: {json.dumps(data)[:200]}")
                return False
        except Exception as e:
            if attempt < retries:
                print(f"   Attempt {attempt + 1} failed ({e}), retrying...")
                time.sleep(3)
            else:
                print(f"  Invocations request failed: {e}")
                return False
    return False


def main():
    """Execute the end-to-end local pre-flight workflow."""
    print("Pre-flight check")
    print("=" * 40)

    port = find_free_port()
    base_url = f"http://localhost:{port}"

    # Step 1: Start server.
    print(f"1. Starting server on port {port}...")
    proc = start_server(port)
    print("   OK")

    try:
        # Step 2: Health check.
        print("2. Health check...")
        if not check_health(base_url):
            print("   FAILED")
            sys.exit(1)
        print("   OK")

        # Step 3: Send a test request.
        print("3. Sending test request to /invocations...")
        if not check_invocations(base_url):
            print("   FAILED")
            sys.exit(1)
        print("   OK")

        print("=" * 40)
        print("Pre-flight check passed!")

    finally:
        stop_server(proc)


if __name__ == "__main__":
    main()
