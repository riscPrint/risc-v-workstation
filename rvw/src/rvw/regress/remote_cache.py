"""Transfer immutable C8 cache generations with native rsync over SSH."""
from pathlib import Path
import json
import re
import os
import shlex
import shutil
import socket
import time

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
        # Ownership is metadata, never evidence for admission.
        (local / '.rvw-owner.json').write_text(json.dumps({
            'schema': 'rvw.cache-owner/1', 'host': socket.gethostname(),
            'user': os.environ.get('USER', 'unknown'), 'key': key,
            'generation': reader.id, 'uploaded_at': time.time()}))
        owners = local / 'owners'
        owners.mkdir(exist_ok=True)
        (owners / (reader.id + '.json')).write_bytes((local / '.rvw-owner.json').read_bytes())
        # Generations first, pointer last. An interrupted transfer cannot publish success.
        mkdir = run_group([*ssh, host, "mkdir", "-p", f"{path}/{key[:2]}/{key}"], timeout=30, capture=True)
        if mkdir.returncode:
            return False
        r = run_group(["rsync", "-r", "--partial", "-e", shlex.join(ssh), "--exclude=current", str(local) + "/", target], timeout=300, capture=True)
        if r.returncode:
            return False
        return run_group(["rsync", "--delay-updates", "-e", shlex.join(ssh), str(local / "current"), target], timeout=30, capture=True).returncode == 0
    # Allow repair of an earlier read-only, corrupt partial generation.
    for directory, dirs, files in os.walk(local):
        Path(directory).chmod(0o700)
        for name in files:
            (Path(directory) / name).chmod(0o600)
    r = run_group(["rsync", "-rp", "--chmod=Du+rwx,Fu+rw", "--partial", "--checksum", "--delete", "-e", shlex.join(ssh), target, str(local) + "/"], timeout=300, capture=True)
    if r.returncode:
        return False
    try:
        reader = open_current(local)
        return reader.read_bytes(".rvw-cache-key").decode() == key
    except (OSError, ValueError):
        return False


def evict(root, *, max_bytes, max_age_s, now=None):
    """Explicit native cache maintenance. Remove oldest managed entries first.

    Run when transfers are idle. Eviction is allowed to cause a miss, never success.
    Unmarked directories are never removed. Invalid managed evidence is evicted.
    """
    import re
    if max_bytes < 0 or max_age_s < 0:
        raise ValueError('retention limits must be non-negative')
    root = Path(root)
    now = time.time() if now is None else now
    entries = []
    removed = []
    for path in sorted(root.glob('*/*')):
        if not re.fullmatch('[0-9a-f]{64}', path.name) or path.parent.name != path.name[:2]:
            continue
        marker = path / '.rvw-cache-entry'
        if not marker.is_file() or marker.read_text() != 'rvw.regress-cache/1\n':
            continue
        valid = True
        try:
            reader = open_current(path)
            valid = reader.read_bytes('.rvw-cache-key').decode() == path.name
        except (OSError, ValueError):
            valid = False
        size = sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
        stamp = (path / 'current').stat().st_mtime if (path / 'current').exists() else 0
        if not valid or now - stamp > max_age_s:
            remove_entry(path)
            removed.append({'key': path.name, 'reason': 'age' if valid else 'invalid'})
        else:
            entries.append((stamp, path, size))
    total = sum(e[2] for e in entries)
    for _, path, size in sorted(entries):
        if total <= max_bytes:
            break
        remove_entry(path)
        total -= size
        removed.append({'key': path.name, 'reason': 'capacity'})
    return {'removed': removed, 'retained_bytes': total, 'policy': 'oldest publication first'}


def remove_entry(path):
    for directory, dirs, files in os.walk(path):
        Path(directory).chmod(0o700)
    shutil.rmtree(path)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Evict managed cache entries on this native host. Stop transfers first.')
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--max-bytes', type=int, required=True)
    parser.add_argument('--max-age-s', type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(evict(args.root, max_bytes=args.max_bytes, max_age_s=args.max_age_s)))
