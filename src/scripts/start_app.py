#!/usr/bin/env python3
"""
Start React UI and backend processes concurrently.

Requirements:
1. Not reporting ready until BOTH UI and backend processes are ready
2. Exiting as soon as EITHER process fails
3. Printing error logs if either process fails

Usage:
    start-app [OPTIONS]

All options are passed through to the backend server (start-server).
See 'uv run runtime-serve-backend --help' for available options.
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

# Process readiness log patterns.
BACKEND_READY = [r"Uvicorn running on", r"Application startup complete", r"Started server process"]
FRONTEND_READY = [r"Uvicorn running on", r"Application startup complete", r"Started server process"]
SRC_DIR = Path(__file__).parent.parent
FRONTEND_DIST_PATH = SRC_DIR / "reactui" / "dist"


def _env_int(primary: str, fallback: str | None, default: int) -> int:
    """Read an integer environment variable with fallback and default values.

    Args:
        primary: Primary environment variable name.
        fallback: Fallback environment variable name.
        default: Default value when parsing fails.

    Returns:
        Parsed integer value or the default.
    """
    raw = os.environ.get(primary)
    if raw is None and fallback:
        raw = os.environ.get(fallback)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_backend_workers() -> int:
    """Resolve backend worker count from environment.

    Priority:
    1) BACKEND_UVICORN_WORKERS
    2) WEB_CONCURRENCY
    3) default=1
    """
    return max(_env_int("BACKEND_UVICORN_WORKERS", "WEB_CONCURRENCY", 1), 1)


def _resolve_frontend_workers() -> int:
    """Resolve frontend worker count from environment.

    Priority:
    1) FRONTEND_UVICORN_WORKERS
    2) default=1
    """
    return max(_env_int("FRONTEND_UVICORN_WORKERS", None, 1), 1)


def check_port_available(port: int) -> bool:
    """Check whether a TCP port is available on localhost.

    Args:
        port: TCP port number to test.

    Returns:
        True when no process is listening on the port.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(("localhost", port))
        return False
    except (ConnectionRefusedError, OSError):
        return True


class ProcessManager:
    def __init__(self, port=8000, no_ui=False):
        """Initialize process state, readiness flags, and runtime options.

        Args:
            port: Backend port to use unless overridden.
            no_ui: Whether to run backend only.
        """
        self.backend_process = None
        self.frontend_process = None
        self.backend_ready = False
        self.frontend_ready = False
        self.failed = threading.Event()
        self.backend_log = None
        self.frontend_log = None
        self.port = port
        self.frontend_port = None
        self.no_ui = no_ui

    def check_ports(self):
        """Validate that required ports are available before process startup."""
        backend_port = self.port

        errors = []
        if not check_port_available(backend_port):
            errors.append(
                f"Port {backend_port} (backend) is already in use.\n"
                f"  To free it: lsof -ti :{backend_port} | xargs kill -9"
            )

        if not self.no_ui:
            frontend_port = _env_int("CHAT_APP_PORT", "PORT", 3000)

            if backend_port == frontend_port:
                print(
                    f"ERROR: Backend and frontend are both configured to use port {backend_port}."
                )
                print("  Set CHAT_APP_PORT in .env to a different port (e.g., CHAT_APP_PORT=3000).")
                sys.exit(1)

            if not check_port_available(frontend_port):
                port_source = (
                    "CHAT_APP_PORT"
                    if os.environ.get("CHAT_APP_PORT")
                    else "PORT"
                    if os.environ.get("PORT")
                    else "default"
                )
                errors.append(
                    f"Port {frontend_port} (frontend, source: {port_source}) is already in use.\n"
                    f"  To free it: lsof -ti :{frontend_port} | xargs kill -9\n"
                    f"  Or set a different port: CHAT_APP_PORT=<port> in .env"
                )

        if errors:
            print("ERROR: Port(s) already in use:\n")
            for error in errors:
                print(f"  {error}\n")
            sys.exit(1)

    def monitor_process(self, process, name, log_file, patterns):
        """Stream process logs, detect readiness, and flag failures.

        Args:
            process: Subprocess handle to monitor.
            name: Logical process name used in output.
            log_file: Open file handle receiving mirrored process logs.
            patterns: Regex patterns indicating process readiness.
        """
        is_ready = False
        try:
            for line in iter(process.stdout.readline, ""):
                if not line:
                    break

                line = line.rstrip()
                log_file.write(line + "\n")
                print(f"[{name}] {line}")

                # Mark process readiness when any configured pattern is detected.
                if not is_ready and any(re.search(p, line, re.IGNORECASE) for p in patterns):
                    is_ready = True
                    if name == "backend":
                        self.backend_ready = True
                    else:
                        self.frontend_ready = True
                    print(f"✓ {name.capitalize()} is ready!")

                    if self.no_ui and self.backend_ready:
                        print("\n" + "=" * 50)
                        print("✓ Backend is ready! (running without UI)")
                        print(f"✓ API available at http://localhost:{self.port}")
                        print("=" * 50 + "\n")
                    elif self.backend_ready and self.frontend_ready:
                        print("\n" + "=" * 50)
                        print("✓ Both frontend and backend are ready!")
                        print(
                            f"✓ Open the chat UI at http://localhost:{self.frontend_port or 3000}"
                        )
                        print("=" * 50 + "\n")

            process.wait()
            if process.returncode != 0:
                self.failed.set()

        except Exception as e:
            print(f"Error monitoring {name}: {e}")
            self.failed.set()

    def start_process(self, cmd, name, log_file, patterns, cwd=None):
        """Start a process and attach a monitor thread.

        Args:
            cmd: Command list to execute.
            name: Logical process name used in output.
            log_file: Open file handle receiving mirrored process logs.
            patterns: Regex patterns indicating process readiness.
            cwd: Optional working directory override.

        Returns:
            Started subprocess handle.
        """
        print(f"Starting {name}...")
        process_env = os.environ.copy()
        existing_pythonpath = process_env.get("PYTHONPATH", "")
        src_path = str(SRC_DIR)
        process_env["PYTHONPATH"] = (
            f"{src_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else src_path
        )
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=process_env,
        )

        thread = threading.Thread(
            target=self.monitor_process, args=(process, name, log_file, patterns), daemon=True
        )
        thread.start()
        return process

    def print_logs(self, log_path):
        """Print the tail of a process log file for troubleshooting.

        Args:
            log_path: Path to the log file.
        """
        print(f"\nLast 50 lines of {log_path}:")
        print("-" * 40)
        try:
            lines = Path(log_path).read_text().splitlines()
            print("\n".join(lines[-50:]))
        except FileNotFoundError:
            print(f"(no {log_path} found)")
        print("-" * 40)

    def cleanup(self):
        """Terminate managed processes and close log file handles."""
        print("\n" + "=" * 42)
        print("Shutting down..." if self.no_ui else "Shutting down both processes...")
        print("=" * 42)

        for proc in [self.backend_process, self.frontend_process]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except (subprocess.TimeoutExpired, Exception):
                    proc.kill()

        if self.backend_log:
            self.backend_log.close()
        if self.frontend_log:
            self.frontend_log.close()

    def run(self, backend_args=None):
        """Run process orchestration until failure or interruption.

        Args:
            backend_args: Additional arguments passed to start-server.

        Returns:
            Process exit code.
        """
        load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env", override=True)
        in_databricks_app = bool(os.environ.get("DATABRICKS_APP_NAME"))
        if not in_databricks_app:
            self.check_ports()

        backend_port = self.port
        if in_databricks_app and not self.no_ui:
            # Databricks routes public traffic to the app port. Keep the UI on
            # that port and shift the backend to an internal port.
            public_port = _env_int("DATABRICKS_APP_PORT", "PORT", 8000)
            self.frontend_port = public_port
            if backend_port == public_port:
                backend_port = public_port + 1
            self.port = backend_port

        react_dist_path = Path(
            os.environ.get("REACT_UI_DIST_DIR", str(FRONTEND_DIST_PATH))
        ).resolve()
        if not self.no_ui:
            if not react_dist_path.exists():
                print(
                    "ERROR: React UI dist not found. "
                    f"Expected at: {react_dist_path}\n"
                    "Build UI assets first with: uv run runtime-build-source"
                )
                self.no_ui = True
            else:
                # Route browser-origin invocations through the React UI proxy server.
                os.environ["FRONTEND_BACKEND_PROXY"] = f"http://localhost:{self.port}/invocations"
                os.environ["REACT_UI_DIST_DIR"] = str(react_dist_path)

        # Open process log files with line-buffered writes.
        self.backend_log = open("backend.log", "w", buffering=1)
        if not self.no_ui:
            self.frontend_log = open("frontend.log", "w", buffering=1)

        try:
            # Build backend command while preserving passthrough arguments.
            backend_cmd = [
                "uv",
                "run",
                "python",
                "-c",
                (
                    "import sys; "
                    "from backend.api.server import main; "
                    "sys.argv = ['start-server'] + sys.argv[1:]; "
                    "main()"
                ),
            ]
            backend_cmd_args = list(backend_args or [])
            if "--port" not in backend_cmd_args:
                backend_cmd_args.extend(["--port", str(self.port)])
            if "--workers" not in backend_cmd_args:
                backend_cmd_args.extend(["--workers", str(_resolve_backend_workers())])
            backend_cmd.extend(backend_cmd_args)

            # Start backend process first.
            self.backend_process = self.start_process(
                backend_cmd, "backend", self.backend_log, BACKEND_READY
            )

            if not self.no_ui:
                # Start React UI proxy server process.
                if self.frontend_port is None:
                    self.frontend_port = _env_int("CHAT_APP_PORT", "PORT", 3000)
                frontend_workers = _resolve_frontend_workers()
                frontend_cmd = [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "scripts.react_ui_server",
                    "--port",
                    str(self.frontend_port),
                ]
                if frontend_workers > 1:
                    frontend_cmd.extend(["--workers", str(frontend_workers)])
                self.frontend_process = self.start_process(
                    frontend_cmd,
                    "frontend",
                    self.frontend_log,
                    FRONTEND_READY,
                )

                print(
                    f"\nMonitoring processes (Backend PID: {self.backend_process.pid}, Frontend PID: {self.frontend_process.pid})\n"
                )
            else:
                print(f"\nMonitoring backend process (PID: {self.backend_process.pid})\n")

            # Stop when either managed process exits unexpectedly.
            while not self.failed.is_set():
                time.sleep(0.1)
                if self.backend_process.poll() is not None:
                    self.failed.set()
                    break
                if (
                    not self.no_ui
                    and self.frontend_process
                    and self.frontend_process.poll() is not None
                ):
                    self.failed.set()
                    break

            # Determine which process exited first and return its exit code.
            if self.no_ui or self.backend_process.poll() is not None:
                failed_name = "backend"
                failed_proc = self.backend_process
            else:
                failed_name = "frontend"
                failed_proc = self.frontend_process
            exit_code = failed_proc.returncode if failed_proc else 1

            print(
                f"\n{'=' * 42}\nERROR: {failed_name} process exited with code {exit_code}\n{'=' * 42}"
            )
            self.print_logs("backend.log")
            if not self.no_ui:
                self.print_logs("frontend.log")
            return exit_code

        except KeyboardInterrupt:
            print("\nInterrupted")
            return 0

        finally:
            self.cleanup()


def main():
    """Parse CLI arguments and run the process manager."""
    parser = argparse.ArgumentParser(
        description="Start agent frontend and backend",
        usage="%(prog)s [OPTIONS]\n\nAll options are passed through to start-server. "
        "Use 'uv run runtime-serve-backend --help' for available options.",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Run backend only, skip frontend UI",
    )
    args, backend_args = parser.parse_known_args()

    # Read explicit backend port from passthrough arguments when provided.
    port = 8000
    for i, arg in enumerate(backend_args):
        if arg == "--port" and i + 1 < len(backend_args):
            try:
                port = int(backend_args[i + 1])
            except ValueError:
                pass
            break

    sys.exit(ProcessManager(port=port, no_ui=args.no_ui).run(backend_args))


if __name__ == "__main__":
    main()
