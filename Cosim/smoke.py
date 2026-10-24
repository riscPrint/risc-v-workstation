#!/usr/bin/env python3
"""Exercise installed ISA ELFs and benchmarks without retaining large traces.
Run with rvw/.venv/bin/python Cosim/smoke.py --isa-dir ... --bench-dir ...
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
from rvw.common.capture import CaptureError
from rvw.cosim.checker import check
from rvw.cosim.generate import generate
from rvw.cosim.inputs import Inputs
from rvw.cosim.spike import Spike, probe


def _publish(out, results):
    """Publish the complete single-file result set by one atomic rename."""
    fd, name = tempfile.mkstemp(prefix=out.name + ".", suffix=".partial", dir=out.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(results, stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(name, out)
    finally:
        Path(name).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isa-dir", type=Path, required=True)
    parser.add_argument("--bench-dir", type=Path)
    parser.add_argument("--platform", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="JSON results, not traces")
    args = parser.parse_args(argv)
    out = args.out.parent.resolve() / args.out.name
    elfs = sorted(p for group in ("ui", "um", "ua", "uf", "ud", "uc")
                  for p in args.isa_dir.glob(f"rv64{group}-p-*") if p.is_file() and "." not in p.name)
    if args.bench_dir:
        elfs += [args.bench_dir / f"{name}.riscv" for name in ("multiply", "towers")]
    results = []
    try:
        if not elfs:
            raise CaptureError("input_not_captured:elfs", "no ELF inputs selected")
        with tempfile.TemporaryDirectory(prefix="rvw-cosim-smoke-") as tmp:
            # This private output is reused only for reference traces from this loop.
            trace = Path(tmp) / "reference.jsonl"
            options = argparse.Namespace(cosim_action="generate", elf=elfs[0], core="boom",
                                         platform=args.platform, out=trace, max_instructions=500000)
            inputs = Inputs(options, tmp)
            images = inputs.capture.files(elfs)
            captured = inputs.capture.record()
            platform = inputs.platform
            for image in images:
                start = time.monotonic()
                identity = next(row for row in captured["files"]
                                if row["copy"] == image.copy.relative_to(inputs.capture.root).as_posix())
                row = {"elf": identity["resolved"], "elf_sha256": identity["sha256"], "capture_row": 0}
                try:
                    probe(platform, image.copy, shim=inputs.shim, executable=inputs.tool.path,
                          env=inputs.child_env, pythonpath=inputs.pythonpath)
                    generated = generate(image.copy, trace, platform, 500000, shim=inputs.shim,
                                         verify=inputs.capture.verify_tools, elf_source=identity["resolved"])
                    model = Spike(platform, image.copy, shim=inputs.shim)
                    try:
                        result = check(trace, model, platform)
                    finally:
                        model.close()
                    row.update(status=result["status"], instructions=result["instructions"],
                               termination=generated["termination"], synchronized=result["synchronized"])
                    if "mismatch" in result:
                        row["mismatch"] = result["mismatch"]
                except CaptureError:
                    raise
                except Exception as exc:
                    row.update(status="error", message=str(exc))
                row["wall_s"] = round(time.monotonic()-start, 3)
                results.append(row)
            inputs.capture.verify_tools()
            # All rows refer to the same capture. Store its potentially large tree only once.
            results[0]["capture"] = captured
            results[0]["options"] = {"max_instructions": 500000, "platform": platform.describe(),
                                      "elfs": [image.source for image in images]}
    except (CaptureError, OSError, ValueError, KeyError, TypeError) as exc:
        results = [{"status": "inconclusive" if isinstance(exc, CaptureError) else "error", "message": str(exc)}]
        if isinstance(exc, CaptureError):
            results[0]["cause"] = exc.cause
    _publish(out, results)
    for row in results:
        print(json.dumps(row), flush=True)
    return 3 if any(r["status"] == "inconclusive" for r in results) else int(any(r["status"] != "match" for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
