"""Background commands the API starts and the UI watches: model checks and tournament runs.

The process outlives the request that started it (and, for tournaments, the browser tab). Output goes to a
log file; the registry only remembers handles so a status request can say whether it is still running.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

LOG_TAIL_BYTES = 16_000


class TrackedProcess(Protocol):
    """What the registry needs from a process: ``ManagedProcess`` here, ``BattleRun`` for tournaments."""

    name: str

    @property
    def running(self) -> bool: ...
    @property
    def exit_code(self) -> int | None: ...
    def log_tail(self) -> str: ...


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen
    log_path: Path

    @property
    def exit_code(self) -> int | None:
        return self.process.poll()

    @property
    def running(self) -> bool:
        return self.exit_code is None

    def log_tail(self) -> str:
        try:
            size = self.log_path.stat().st_size
            with self.log_path.open("rb") as log:
                log.seek(max(0, size - LOG_TAIL_BYTES))
                return log.read().decode("utf-8", errors="replace")
        except OSError:
            return ""


def spawn(name: str, args: list[str], *, cwd: Path, log_path: Path) -> ManagedProcess:
    """Start ``python -u <args>`` detached from the request, writing UTF-8 output to ``log_path``."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-u", *args], cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return ManagedProcess(name, process, log_path)


class ProcessRegistry:
    """Named processes, newest last. Finished ones are kept (their log is the result) up to ``keep``."""

    def __init__(self, keep: int = 50):
        self._items: dict[str, TrackedProcess] = {}
        self._lock = threading.Lock()
        self.keep = keep

    def add(self, proc: TrackedProcess) -> TrackedProcess:
        with self._lock:
            self._items[proc.name] = proc
            finished = [n for n, p in self._items.items() if not p.running]
            for name in finished[: max(0, len(self._items) - self.keep)]:
                del self._items[name]
        return proc

    def get(self, name: str) -> TrackedProcess | None:
        with self._lock:
            return self._items.get(name)

    def running(self, prefix: str = "") -> list[TrackedProcess]:
        """Processes whose name starts with ``prefix`` that have not exited."""
        with self._lock:
            return [p for n, p in self._items.items() if n.startswith(prefix) and p.running]
