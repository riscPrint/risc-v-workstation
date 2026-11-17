"""Resolve workstation-owned verification inputs without sibling checkouts."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import shutil

from rvw.regress.source import ensure_pinned_source, describe, _dest_lock

OVERRIDES = {"act4": "ACT4_SOURCE", "riscv-tests": "RISCV_TESTS_SRC",
             "riscv-formal": "RISCV_FORMAL", "sail": "RVW_SAIL"}


def resolve(name, *, acquire=False, revision=None):
    if name not in OVERRIDES:
        raise ValueError(f"unknown dependency: {name}")
    override = os.environ.get(OVERRIDES[name])
    if name == "riscv-tests" and not override:
        override = os.environ.get("RISCV_TESTS_SOURCE")
    if override:
        path = Path(override).expanduser().resolve()
        if name == "sail":
            if not path.is_file() or not os.access(path, os.X_OK):
                raise ValueError(f"invalid {OVERRIDES[name]} executable: {path}")
            return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), override=True)
        source = describe(path)
        if not path.is_dir() or not source.rev or (revision and source.rev != revision):
            raise ValueError(f"invalid {OVERRIDES[name]} source or revision: {path}")
        return dict(path=str(path), revision=source.rev, dirty=source.dirty, override=True)
    if name != "sail":
        source = ensure_pinned_source(name, revision, offline=not acquire)
        return dict(path=str(source.path), revision=source.rev, override=False)
    # The existing manifest is the sole archive pin authority.
    root = Path(__file__).resolve().parents[4]
    records = json.loads((root / "scripts/native-manifest.json").read_text())["archives"]
    host = platform.system() + "-" + platform.machine()
    matches = [r for r in records if r["tool"] == "Sail" and r["host"] == host]
    if len(matches) != 1:
        raise ValueError(f"no pinned Sail archive for {host}")
    record = matches[0]
    prefix = Path(os.environ.get("RVW_NATIVE_CACHE", Path.home() / ".cache/rvw/native"))
    target = prefix / record["tool"] / record["version"]
    spec = importlib.util.spec_from_file_location("rvw_fetch_native", root / "scripts/fetch-native.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with (_dest_lock(target) if acquire else contextlib.nullcontext()), contextlib.redirect_stdout(io.StringIO()):
        module.install(record, prefix, check=target.exists() or not acquire)
    executables = [p for p in target.rglob("sail_riscv_sim") if p.is_file() and os.access(p, os.X_OK)]
    if len(executables) != 1:
        raise ValueError(f"expected one Sail executable in {target}")
    path = executables[0].resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                version=record["version"], archive_sha256=record["sha256"], override=False)
