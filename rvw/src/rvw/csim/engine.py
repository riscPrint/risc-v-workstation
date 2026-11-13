"""Build and run the native ComponentSims engine. Builds are cached by source hash."""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
FLAGS = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror"]


def source_dir() -> Path:
    env = os.environ.get("RVW_CSIM_SRC")
    path = Path(env) if env else ROOT / "ComponentSims"
    if not (path / "csim.cc").is_file():
        raise FileNotFoundError(f"ComponentSims sources not found at {path} (set RVW_CSIM_SRC)")
    return path


def sources(src: Path) -> list[Path]:
    return sorted([src / "csim.cc", src / "capi.cc", *(src / "include" / "csim").glob("*.h")])


def source_hash(src: Path | None = None) -> str:
    src = src or source_dir()
    h = hashlib.sha256()
    for p in sources(src):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def compiler() -> str:
    cxx = os.environ.get("CXX") or shutil.which("c++") or shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        raise FileNotFoundError("no C++17 compiler found (set CXX)")
    return cxx


def cache_dir() -> Path:
    env = os.environ.get("RVW_CSIM_CACHE")
    return Path(env) if env else Path.home() / ".cache" / "rvw" / "csim"


def build(kind: str = "cli") -> Path:
    """Return the path of the built engine (kind "cli") or shared library (kind "lib")."""
    src = source_dir()
    digest = source_hash(src)[:16]
    name = "csim" if kind == "cli" else ("libcsim.dylib" if platform.system() == "Darwin" else "libcsim.so")
    out = cache_dir() / digest / name
    if out.is_file():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    main = src / ("csim.cc" if kind == "cli" else "capi.cc")
    extra = [] if kind == "cli" else ["-shared", "-fPIC"]
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        tmp_out = Path(tmp) / name
        cmd = [compiler(), *FLAGS, *extra, f"-I{src / 'include'}", str(main), "-o", str(tmp_out)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode:
            raise RuntimeError("ComponentSims build failed:\n" + res.stderr[-4000:])
        os.replace(tmp_out, out)
    return out


def identity() -> dict:
    return {"source_sha256": source_hash(), "compiler": compiler(), "flags": FLAGS}
