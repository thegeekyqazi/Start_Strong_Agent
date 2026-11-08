"""Start the real API process (uvicorn) and check liveness, readiness and capabilities.

Exit 0 only if /health/live is 200 and /health/ready is 200 "ready". Used by `make smoke`.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time

import httpx


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> int:
    port = _free_port()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "--factory",
        "strongstart_api.app:app_factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(cmd)  # noqa: S603 - fixed argv, no shell
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                live = httpx.get(f"{base}/health/live", timeout=1)
                break
            except httpx.TransportError:
                time.sleep(0.1)
        else:
            print("API did not start", file=sys.stderr)
            return 1
        ready = httpx.get(f"{base}/health/ready", timeout=5)
        caps = httpx.get(f"{base}/api/capabilities", timeout=5)
        print(f"live {live.status_code} {live.text}")
        print(f"ready {ready.status_code} {ready.text}")
        print(f"capabilities {caps.status_code} ({len(caps.json()['capabilities'])} entries)")
        ok = live.status_code == 200 and ready.status_code == 200 and caps.status_code == 200
        return 0 if ok and ready.json()["status"] == "ready" else 1
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
