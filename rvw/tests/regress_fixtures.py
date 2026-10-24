"""Shared regress test helpers (a uniquely named module: `conftest` names clash between test folders)."""
from pathlib import Path
import subprocess


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

def legacy_layout(root):
    """Make a mutable pre-C8 fixture. Production readers must still validate its owner."""
    import os
    import shutil
    from rvw.results.generation import open_current, _discard
    root = Path(root)
    if not (root / 'current').exists():
        return
    reader = open_current(root)
    if not (root / 'run.json').exists():  # A cache has no mutable workspace.
        for top, dirs, files in os.walk(reader.path):
            part = Path(top).relative_to(reader.path)
            (root / part).mkdir(parents=True, exist_ok=True)
            for name in files:
                if name != 'generation.json':
                    (root / part / name).write_bytes(reader.read_bytes(part / name))
    (root / 'current').unlink()
    _discard(root / 'generations')
