"""Owned real API processes, no dependency overrides or shared Python state."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx


@contextmanager
def api_process(url: str, directory: Path) -> Iterator[httpx.Client]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    directory.mkdir(exist_ok=True, parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("STRONGSTART_")}
    env.update(
        STRONGSTART_DATABASE_URL=url,
        STRONGSTART_ANSWER_STORE_BACKEND="postgres",
        STRONGSTART_AUTH_MODE="fixture",
        STRONGSTART_DEV_B_STORE_DIR=str(directory / "b"),
    )
    proc = subprocess.Popen(  # noqa: S603 - fixed owned local API command
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "strongstart_api.app:app_factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=directory,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30) as client:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise AssertionError("owned API process exited during startup")
                try:
                    if client.get("/health/live").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                threading.Event().wait(0.05)  # readiness polling, never contention proof
            else:
                raise AssertionError("owned API startup timeout")
            yield client
    finally:
        proc.terminate()
        proc.wait(timeout=10)
