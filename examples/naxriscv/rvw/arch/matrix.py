#!/usr/bin/env python3
"""Run the same programs on one-parameter RTL variants. Reuse completed runs."""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
VARIANTS = {"base": ("rv32imasu", {}), "iq16": ("rv32imasu-iq16", {"issue_entries": 16}),
            "rob128": ("rv32imasu-rob128", {"rob_entries": 128}),
            "lq8": ("rv32imasu-lq8", {"load_entries": 8}),
            "sq8": ("rv32imasu-sq8", {"store_entries": 8})}
PROGRAMS = ("median", "qsort", "multiply", "towers", "vvadd", "memcpy")


def main(out, *selected):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rvw = Path(sys.executable).with_name("rvw")
    rows = []
    for variant, (config, changes) in VARIANTS.items():
        if selected and variant not in selected:
            continue
        for name in PROGRAMS:
            dest = out / variant / name
            dest.parent.mkdir(exist_ok=True)
            elf = HERE / "out/bench" / (name + ".riscv")
            def execute(args, filename):
                with (dest.parent / (name + "-" + filename + ".log")).open("w") as stream:
                    subprocess.run([str(a) for a in args], check=True, stdout=stream, stderr=subprocess.STDOUT)
            if not (dest / "result.json").exists():
                execute(["nice", "-n", "10", HERE / "run.sh", "run", "--config", config,
                         "--elf", elf, "--out", dest, "--seed", "1", "--mem-latency", "0",
                         "--max-cycles", "5000000", "--probes", "--rvfi-trace", "--json"], "run")
            result = json.loads((dest / "result.json").read_text())
            if result["status"] != "pass":
                raise RuntimeError(f"{variant}/{name}: RTL did not pass")
            for filename, args in (
                ("spike", ["cosim", "check", "--elf", elf, "--trace", dest / "rvfi.jsonl",
                           "--platform", HERE / "platform.json", "--json"]),
                ("topdown", ["perf", "topdown", dest / "probe-events.jsonl", "--c2",
                             dest / "rvfi.jsonl", "--result", dest / "result.json", "--json"]),
                ("counts", ["probes", "convert", dest / "probe-events.jsonl", "--to", "counts",
                            "--out", dest / "counts.json", "--c1", dest / "result.json",
                            "--c2", dest / "rvfi.jsonl"])):
                target = dest / (filename + ".json")
                if not target.exists():
                    execute([rvw, *args], filename)
                    if filename != "counts":
                        target.write_text((dest.parent / (name + "-" + filename + ".log")).read_text())
            spike = json.loads((dest / "spike.json").read_text())
            if (spike.get("status") != "match" or not spike.get("trace_complete")
                    or spike.get("instructions") != result["instret"]):
                raise RuntimeError(f"{variant}/{name}: Spike did not match")
            row = dict(variant=variant, program=name, config=config, changes=changes,
                       cycles=result["cycles"], instret=result["instret"],
                       ipc=result["instret"]/result["cycles"],
                       elf_sha256=result["elf_sha256"],
                       topdown=json.loads((dest / "topdown.json").read_text()),
                       spike=json.loads((dest / "spike.json").read_text()),
                       counts=json.loads((dest / "counts.json").read_text()))
            rows.append(row)
            (out / "summary.json").write_text(json.dumps(rows, indent=2))
            print(variant, name, row["cycles"], row["ipc"], flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
