"""Pinned Accellera UVM component conformance runs on native Verilator."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tarfile
import time
import urllib.request

from rvw.common.proc import run_group
from rvw.results import write_json

COMMIT = "78c06547a2a0a29b3dc9dcafae62b75b2ff61544"
URL = f"https://api.github.com/repos/accellera-official/uvm-core/tarball/{COMMIT}"
ARCHIVE_SHA256 = "9ee918499a92518f8f7c202c5f8a38b8a0c83d4eba3bedd7890bfa3ed023d1e4"
LICENSES = {
    "LICENSE.txt": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
    "NOTICE.txt": "b89f85d3f14ae457890c932bd543124e6521f74b3b01ab208932ef72488748c2",
}
FEATURES = ("constrained_random", "functional_coverage", "tlul", "rvfi",
            "phases_config_factory_tlm", "ral_frontdoor", "interrupt_debug_pins")
DEFAULT_SUITE = Path(__file__).resolve().parents[4] / "Uvm" / "tests"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unpack(archive: Path, destination: Path) -> Path:
    """Check the archive before extraction. Keep the upstream licence and notice."""
    if sha(archive) != ARCHIVE_SHA256:
        raise ValueError("Accellera UVM archive checksum mismatch")
    destination.mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            path = destination / member.name
            if not path.resolve().is_relative_to(destination.resolve()):
                raise ValueError("invalid archive path")
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            else:
                raise ValueError("unsupported archive entry")
    roots = list(destination.iterdir())
    if len(roots) != 1:
        raise ValueError("invalid UVM archive root")
    root = roots[0]
    for name, digest in LICENSES.items():
        if sha(root / name) != digest:
            raise ValueError(f"UVM licence or notice checksum mismatch: {name}")
    return root


def evidence(log: str, returncode: int, timed_out: bool, *, negative=False) -> bool:
    if timed_out:
        return False
    if negative:
        diagnostic = {True: "[RVFI] load observation mismatch",
                      "ral": "[RAL] read or prediction mismatch",
                      "pins": "[PINS] interrupt/debug pin mismatch"}[negative]
        return (returncode != 0 and diagnostic in log
                and "RVW_UVM_DONE" not in log)
    markers = re.findall(r"^RVW_UVM_PASS (\w+)$", log, re.M)
    return (returncode == 0 and log.count("RVW_UVM_DONE") == 1
            and sorted(markers) == sorted(FEATURES)
            and not re.search(r"^UVM_(?:ERROR|FATAL)\b(?!\s*:\s*0\s*$)", log, re.M))


def run(out: Path, *, archive=None, suite=DEFAULT_SUITE, verilator="verilator",
        seed=1, seeds=1, timeout=600, required_features=()) -> dict:
    from .uvm_features import require
    require(required_features)
    if (type(seed) is not int or not 1 <= seed <= 2**31-1 or
            type(seeds) is not int or not 1 <= seeds <= 100 or seed+seeds > 2**31 or
            not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("invalid UVM seed, seed count or timeout")
    executable = shutil.which(verilator)
    if executable is None:
        raise ValueError("Verilator is not installed")
    suite = Path(suite).resolve(strict=True)
    sources = [suite / name for name in ("tlul.sv", "env.sv", "controls.sv", "registers.json")]
    inputs = {str(p): sha(p) for p in sources}
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    rows = []
    commands = []
    version = run_group([executable, "--version"], capture=True, timeout=10)
    if version.returncode:
        raise ValueError("cannot get Verilator version")
    try:
        if archive is None:
            archive = out / "uvm.tar.gz"
            with urllib.request.urlopen(URL, timeout=30) as response, archive.open("wb") as dst:
                shutil.copyfileobj(response, dst)
        library = unpack(Path(archive), out / "library")
        from rvw.sim.ral import generate
        (out / "ral.sv").write_text(generate(suite / "registers.json"))
        command = [executable, "--binary", "--timing", "--assert", "--coverage",
                   "-Wno-fatal", "-j", "2", "--top-module", "top",
                   "+define+UVM_NO_DPI", f"+incdir+{library / 'src'}",
                   str(library / "src/uvm_pkg.sv"), str(out / "ral.sv"),
                   str(suite / "tlul.sv"), str(suite / "controls.sv"), str(suite / "env.sv"),
                   "--Mdir", str(out / "build")]
        commands.append(command)
        with (out / "build.log").open("w") as log:
            built = run_group(command, timeout=timeout, stdout=log, stderr=log)
        if built.returncode or built.timed_out:
            raise ValueError("UVM compile failed or timed out; see build.log")
        for current in range(seed, seed+seeds):
            for negative in (False, True, "ral", "pins"):
                name = f"{current}-{str(negative) if negative else 'normal'}"
                command = [str(out / "build/Vtop"), f"+verilator+seed+{current}"]
                if negative:
                    command.append({True: "+corrupt", "ral": "+ral_corrupt", "pins": "+pins_corrupt"}[negative])
                commands.append(command)
                with (out / f"{name}.log").open("w") as log:
                    result = run_group(command, cwd=out, timeout=timeout, stdout=log, stderr=log)
                good = evidence((out / f"{name}.log").read_text(), result.returncode,
                                result.timed_out, negative=negative)
                fault_id = {True: "rvfi_fault_detection", "ral": "ral_fault_detection", "pins": "pins_fault_detection"}
                for feature in ((fault_id[negative],) if negative else FEATURES):
                    rows.append({"id": feature, "seed": current, "kind": "uvm",
                                 "status": "pass" if good else "error",
                                 "simulator_exit": result.returncode,
                                 "wall_clock_timeout": result.timed_out,
                                 "signature": None if good else "uvm:incomplete",
                                 **({} if good else {"inconclusive": "missing conformance evidence"}),
                                 "artifacts": {"log": f"{name}.log"}})
    except (OSError, ValueError, tarfile.TarError) as exc:
        rows.append({"id": "build", "seed": seed, "kind": "uvm", "status": "error",
                     "signature": "uvm:build", "inconclusive": str(exc)})
    changed = any(not Path(p).is_file() or sha(p) != digest for p, digest in inputs.items())
    if changed:
        for row in rows:
            row.update(status="error", signature="uvm:source-changed",
                       inconclusive="suite sources changed during run")
    report = {"schema": "rvw.results/1", "suite": "uvm-subset", "core": "tiny-ram",
              "config": "verilator-timing-no-dpi", "run_id": out.name,
              "created": dt.datetime.now(dt.timezone.utc).isoformat(),
              "source": {"input_sha256": inputs, "uvm_commit": COMMIT,
                         "uvm_archive_sha256": ARCHIVE_SHA256,
                         "identity_complete": False},
              "uvm_release": "2020.3.1", "licence": "Apache-2.0",
              "licence_sha256": LICENSES, "verilator": version.stdout.strip(),
              "tests": rows, "commands": commands, "timeout_s": timeout,
              "wall_s": time.monotonic()-start}
    write_json(out / "results.json", report)
    return report


def register(sub):
    parser = sub.add_parser("uvm", help="run the pinned Accellera UVM subset on Verilator")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--archive", type=Path, help="offline pinned UVM source archive")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--require-feature", action="append", default=[],
                        help="refuse features outside the qualified runner profile")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=command)


def command(args):
    import sys
    try:
        report = run(args.out, archive=args.archive, suite=args.suite,
                     verilator=args.verilator, seed=args.seed, seeds=args.seeds,
                     timeout=args.timeout, required_features=args.require_feature)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report) if args.json else str(args.out / "results.json"))
    return 0 if all(row["status"] == "pass" for row in report["tests"]) else 2
