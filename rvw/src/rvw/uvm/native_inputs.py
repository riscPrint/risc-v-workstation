"""Explicit project native inputs for a compiled bench and its C4 identity."""
from pathlib import Path
from rvw.sim.uvm import sha


def capture(paths):
    hashes = {}
    for value in paths:
        path = Path(value).resolve(strict=True)
        files = sorted(p for p in path.rglob('*') if p.is_file()) if path.is_dir() else [path]
        if not files:
            raise ValueError('empty native dependency: '+str(path))
        hashes.update((str(p), sha(p)) for p in files)
    return hashes


def verify(hashes):
    if any(not Path(p).is_file() or sha(p) != digest for p, digest in hashes.items()):
        raise ValueError('native dependency changed; rebuild the bench')
