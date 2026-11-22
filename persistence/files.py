"""
Crash-safe file helpers.

Writes go to a temporary file in the same directory and are then moved into
place with os.replace(), which is atomic on POSIX and Windows. A crash mid-write
therefore leaves the previous version intact instead of a half-written file.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


def atomic_write(path: str | Path, writer: Callable[[str], None]) -> None:
    """Call writer(tmp_path) and atomically move the result to `path`."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        writer(tmp)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    def _w(tmp: str) -> None:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

    atomic_write(path, _w)


def atomic_write_json(path: str | Path, data: Any) -> None:
    payload = json.dumps(data, indent=2, default=str, ensure_ascii=False).encode("utf-8")
    atomic_write_bytes(path, payload)


def read_json(path: str | Path, default: Any) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def quarantine(path: str | Path, reason: str = "corrupt") -> Path | None:
    """Rename a bad file aside (never delete it) so it can be inspected later."""
    p = Path(path)
    if not p.exists():
        return None
    dest = p.with_name(f"{p.name}.{reason}-{time.strftime('%Y%m%d-%H%M%S')}")
    os.replace(p, dest)
    return dest
