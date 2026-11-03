"""Transfer immutable C8 cache generations with native rsync over SSH."""
from pathlib import Path
import json
import re
import os
import shlex

from rvw.common.proc import run_group
from rvw.results.generation import open_current


def transfer(remote, key, local, *, upload=False):
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise ValueError("invalid C8 cache key")
    if not remote or remote.startswith("-") or ":" not in remote:
        raise ValueError("remote cache must be HOST:ABSOLUTE_PATH")
    host, path = remote.split(":", 1)
    if not path.startswith("/") or not re.fullmatch(r"[A-Za-z0-9_@.\-]+", host):
        raise ValueError("invalid remote cache location")
    # A remote path must not become shell syntax in rsync's remote command.
    if not re.fullmatch(r"/[A-Za-z0-9_./\-]+", path):
        raise ValueError("remote cache path must use plain path characters")
    ssh = ["ssh", "-oBatchMode=yes", *json.loads(os.environ.get("RVW_CACHE_SSH_OPTIONS", "[]"))]
    target = f"{host}:{path}/{key[:2]}/{key}/"
    if upload:
        reader = open_current(local)
        if reader.read_bytes(".rvw-cache-key").decode() != key:
            return False
        # Generations first, pointer last. An interrupted transfer cannot publish success.
        mkdir = run_group([*ssh, host, "mkdir", "-p", f"{path}/{key[:2]}/{key}"], timeout=30, capture=True)
        if mkdir.returncode:
            return False
        r = run_group(["rsync", "-r", "--partial", "-e", shlex.join(ssh), "--exclude=current", str(local) + "/", target], timeout=300, capture=True)
        if r.returncode:
            return False
        return run_group(["rsync", "--delay-updates", "-e", shlex.join(ssh), str(local / "current"), target], timeout=30, capture=True).returncode == 0
    r = run_group(["rsync", "-r", "--partial", "-e", shlex.join(ssh), target, str(local) + "/"], timeout=300, capture=True)
    if r.returncode:
        return False
    try:
        reader = open_current(local)
        return reader.read_bytes(".rvw-cache-key").decode() == key
    except (OSError, ValueError):
        return False
