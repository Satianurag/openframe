#!/usr/bin/env python3
"""Run the API and Vite together; stop both when this launcher exits."""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def available_port(start: int, end: int) -> int:
    for candidate in range(start, end + 1):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    raise RuntimeError(f"No free local port in {start}–{end}.")


def main() -> int:
    if not shutil.which("uv") or not shutil.which("npm"):
        print("Install uv and Node.js/npm first. See README.md.", file=sys.stderr)
        return 1
    if not (ROOT / "frontend/node_modules").exists():
        subprocess.run(["npm", "install"], cwd=ROOT / "frontend", check=True)
    try:
        api_port = available_port(8000, 8020)
        frontend_port = available_port(5173, 5193)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    child_env = {**os.environ, "OPENFRAME_API_URL": f"http://127.0.0.1:{api_port}"}
    origins = [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (api_port, frontend_port)]
    origins.extend(filter(None, os.environ.get("OPENFRAME_ALLOWED_ORIGINS", "").split(",")))
    child_env["OPENFRAME_ALLOWED_ORIGINS"] = ",".join(dict.fromkeys(origins))
    children: list[subprocess.Popen] = []
    stopping = False

    def stop(*_args):
        nonlocal stopping
        if stopping:
            return
        stopping = True
        for process in children:
            if process.poll() is None:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
        for process in children:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        extras = ["--extra", "cloud"]
        children.append(subprocess.Popen(
            ["uv", "run", "--python", "3.12", *extras, "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", str(api_port)],
            cwd=ROOT, env=child_env, start_new_session=os.name == "posix",
        ))
        children.append(subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
            cwd=ROOT / "frontend", env=child_env, start_new_session=os.name == "posix",
        ))
        print(f"OpenFrame: open the local URL printed by Vite. API: http://127.0.0.1:{api_port}")
        while not stopping:
            for process in children:
                try:
                    code = process.wait(timeout=0.5)
                    if not stopping:
                        stop()
                        return code or 1
                except subprocess.TimeoutExpired:
                    pass
        return 0
    finally:
        stop()


if __name__ == "__main__":
    raise SystemExit(main())
