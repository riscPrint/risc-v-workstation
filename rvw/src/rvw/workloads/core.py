"""Build captured sources and check complete reference exits and exact output bytes.

This is a reference-output check. It does not grant a C4 acceptance verdict.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile

from rvw.common.proc import run_group

ASSETS = Path(__file__).with_name("assets")
EMPTY = hashlib.sha256(b"").hexdigest()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hash(path):
    """Hash relative names and bytes. Permit only internal symlinks."""
    h = hashlib.sha256()
    for p in sorted(Path(path).rglob("*")):
        if p.is_symlink():
            if not p.resolve().is_relative_to(Path(path).resolve()) or not p.exists():
                raise ValueError(f"external or broken source symlink: {p}")
            name = p.relative_to(path).as_posix().encode()
            target = p.readlink().as_posix().encode()
            h.update(b"link" + len(name).to_bytes(8, "big") + name)
            h.update(len(target).to_bytes(8, "big") + target)
            continue
        if p.is_dir():
            continue
        if not p.is_file():
            raise ValueError(f"special source file: {p}")
        name = p.relative_to(path).as_posix().encode()
        h.update(len(name).to_bytes(8, "big") + name)
        h.update(bytes.fromhex(digest(p)))
        h.update((p.stat().st_mode & 0o111).to_bytes(2, "big"))
    return h.hexdigest()


def command(argv, **kw):
    r = run_group(argv, capture=True, timeout=kw.pop("timeout", 120), **kw)
    if r.timed_out or r.returncode:
        raise ValueError(f"command failed ({r.returncode}): {argv[0]}: {str(r.stderr)[-1000:]}")
    return r.stdout


def load(path=None):
    data = json.loads(Path(path).read_bytes() if path else (ASSETS / "default.json").read_bytes())
    if data.get("schema") != "rvw.workloads/1" or not data.get("workloads"):
        raise ValueError("expected nonempty rvw.workloads/1 manifest")
    ids = set()
    if not isinstance(data.get("compiler_version"), str) or not data["compiler_version"]:
        raise ValueError("compiler_version must pin the full first version line")
    for w in data["workloads"]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", w["id"]) or w["id"] in ids:
            raise ValueError("invalid or duplicate workload ID")
        ids.add(w["id"])
        if w["mode"] not in ("bare", "linux"):
            raise ValueError("mode must be bare or linux")
        if not re.fullmatch(r"[0-9a-f]{64}", w["stdout_sha256"]):
            raise ValueError("expected output hash is required")
        if not isinstance(w["build"], list) or not w["build"]:
            raise ValueError("build must be a nonempty argument list")
        if not isinstance(w.get("args", []), list):
            raise ValueError("args must be an argument list")
    return data


def identity(name):
    found = shutil.which(name)
    if not found:
        raise ValueError(f"tool not found: {name}")
    path = str(Path(found).absolute())
    return {"path": path, "sha256": digest(path),
            "version": version(path)}


def version(path):
    option = "--help" if Path(path).name == "spike" else "--version"
    r = run_group([path, option], capture=True, timeout=15)
    text = (r.stdout or "") + (r.stderr or "")
    if r.timed_out or not text.strip() or (r.returncode and option != "--help"):
        raise ValueError("cannot identify tool version")
    return text.splitlines()[0]


def archive_source(source, revision, destination):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("source revision must be a full Git commit")
    raw = command(["git", "-C", str(source), "archive", revision], text=False)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        tar.extractall(destination, filter="data")


def recipe(name):
    names = {"embench": "default.json", "riscv-tests": "riscv-tests.json", "coremark": "coremark.json", "zstd": "zstd.json"}
    if name not in names:
        raise ValueError("unknown workload recipe")
    return ASSETS / names[name]


def build(manifest, source, out, cc, bench=None):
    data = load(manifest)
    source, out = Path(source).resolve(), Path(out).resolve()
    if source == out or source in out.parents:
        raise ValueError("output must be outside the source tree")
    selected = bench.split(",") if bench else [w["id"] for w in data["workloads"]]
    rows = [w for w in data["workloads"] if w["id"] in selected]
    if not rows or set(selected) != {w["id"] for w in rows}:
        raise ValueError("unknown or empty workload selection")
    compiler = identity(cc)
    if compiler["version"] != data["compiler_version"]:
        raise ValueError(f"compiler pin mismatch: {compiler['version']}")
    out.mkdir(parents=True, exist_ok=False)
    captured = out / "source"
    if "revision" in data:
        archive_source(source, data["revision"], captured)
    else:
        # Licensed sources need no Git repository. The caller pins their tree.
        expected = data["source_sha256"]
        if tree_hash(source) != expected:
            raise ValueError("source tree pin mismatch")
        shutil.copytree(source, captured, symlinks=True)
    for relative, revision in data.get("dependencies", {}).items():
        dependency = Path(relative)
        if dependency.is_absolute() or ".." in dependency.parts:
            raise ValueError("dependency paths must stay within the source tree")
        archive_source(source / dependency, revision, captured / dependency)
    source_hash = tree_hash(captured)
    shutil.copytree(ASSETS, out / "assets")
    root = Path(__file__).resolve().parents[4]
    for relative in data.get("runtime_files", []):
        runtime = Path(relative)
        if runtime.is_absolute() or ".." in runtime.parts:
            raise ValueError("runtime paths must stay within the workstation")
        target = out / "assets/workstation" / runtime
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / runtime, target)
    records = []
    for w in rows:
        dest = out / w["id"]
        dest.mkdir()
        mapping = {"source": str(captured), "out": str(dest), "cc": compiler["path"],
                   "assets": str(out / "assets")}
        argv = [a.format_map(mapping) for a in w["build"]]
        command(argv, cwd=captured)
        elf = dest / "workload.elf"
        # Refuse a successful command that produced no target or the wrong target.
        header = elf.read_bytes()[:64]
        if len(header) < 64 or header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\xf3\x00":
            raise ValueError("build output must be a little-endian RV64 ELF")
        records.append({**w, "argv": argv, "elf": str(elf), "elf_sha256": digest(elf),
                        "elf_bytes": elf.stat().st_size})
    if tree_hash(captured) != source_hash:
        raise ValueError("build modified captured sources; put generated files under {out}")
    if digest(compiler["path"]) != compiler["sha256"]:
        raise ValueError("compiler changed during build")
    report = {"schema": "rvw.workload-build/1", "status": "built", "manifest": data,
              "source_sha256": source_hash, "assets_sha256": tree_hash(out / "assets"),
              "compiler": compiler, "workloads": records}
    (out / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def verify(build_path, out, oracle, timeout=120, trace=False):
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    raw = Path(build_path).read_bytes()
    data = json.loads(raw)
    if data.get("schema") != "rvw.workload-build/1" or not data.get("workloads"):
        raise ValueError("expected nonempty workload build report")
    tool = identity(oracle)
    name = Path(tool["path"]).name
    if name not in ("spike", "qemu-riscv64", "qemu-riscv64-static"):
        raise ValueError("oracle must be Spike or QEMU RISC-V Linux user mode")
    if trace and name != "spike":
        raise ValueError("instruction logs require Spike")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for w in data["workloads"]:
        elf = Path(w["elf"])
        if digest(elf) != w["elf_sha256"]:
            raise ValueError("ELF changed since build")
        if (name == "spike") != (w["mode"] == "bare"):
            raise ValueError("Spike requires bare mode; QEMU user mode requires linux mode")
        argv = [tool["path"]] + (["--isa=rv64gc"] if name == "spike" else [])
        if trace:
            argv.append("-l")
        argv += [str(elf), *w.get("args", [])]
        # File inputs are part of the captured source tree. Recheck their bytes.
        source = Path(build_path).resolve().parent / "source"
        if tree_hash(source) != data["source_sha256"]:
            raise ValueError("captured source or inputs changed")
        workdir = out / f"{w['id']}.inputs"
        shutil.copytree(source, workdir, symlinks=True)
        stdout, stderr = out / f"{w['id']}.stdout", out / f"{w['id']}.stderr"
        with stdout.open("wb") as so, stderr.open("wb") as se:
            result = run_group(argv, cwd=workdir, stdout=so, stderr=se, timeout=timeout)
        ok = not result.timed_out and result.returncode == 0 and digest(stdout) == w["stdout_sha256"]
        rows.append({"id": w["id"], "status": "pass" if ok else "fail", "argv": argv,
                     "elf_sha256": w["elf_sha256"], "exit_code": result.returncode,
                     "timed_out": result.timed_out, "stdout_sha256": digest(stdout),
                     "stderr_sha256": digest(stderr)})
        if trace and ok:
            from .profile import summarize
            rows[-1]["profile"] = summarize(stderr)
    if digest(tool["path"]) != tool["sha256"]:
        raise ValueError("oracle changed during verification")
    report = {"schema": "rvw.workload-verify/1", "status": "pass" if all(
        r["status"] == "pass" for r in rows) else "fail", "oracle": tool,
        "build_sha256": hashlib.sha256(raw).hexdigest(), "workloads": rows}
    (out / "verify.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
