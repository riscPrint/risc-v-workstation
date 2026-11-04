"""Command-owned C8 inputs. Execution and claims use this one capture."""
from argparse import Namespace
import json
import os
from pathlib import Path
import shlex
import sys

from rvw.common.capture import Capture, CaptureError
from .platform import Platform
from .spike import capture_shim

ROOT = Path(__file__).resolve().parents[4]


def _public_record(value):
    """Keep captured provenance, without locations of temporary execution copies."""
    if isinstance(value, dict):
        return {key: _public_record(item) for key, item in value.items() if key != "copy"}
    if isinstance(value, list):
        return [_public_record(item) for item in value]
    return value


class Inputs:
    def __init__(self, args, directory):
        self.child_env = os.environ.copy()
        self.capture = c = Capture(Path(directory) / "inputs")
        from rvw.common.project import load_project
        args = Namespace(**vars(args))
        project = load_project(getattr(args, "project", None), capture=c, core=args.core)
        if project:
            args.core = project.name
            args.platform = args.platform or project.get("cosim", "platform")
            if args.platform is None:
                raise ValueError(f"{project.path}: missing cosim.platform")
        if not args.core:
            raise ValueError("give --core or select a project with cosim.platform")
        self.options = dict(vars(args))
        self.files = {}
        self.env = c.env("RVW_SPIKE_SHIM", "RVW_SAIL", "PATH", "PYTHONPATH",
                         "DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "LD_LIBRARY_PATH", "LD_PRELOAD")
        for name, value in self.env.items():
            if value is None:
                self.child_env.pop(name, None)
            else:
                self.child_env[name] = value
        # Loader injection would bypass the captured native dependency.
        for name in ("DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "LD_LIBRARY_PATH", "LD_PRELOAD"):
            if self.env[name]:
                raise CaptureError(f"input_not_captured:{name}", "loader overrides are unsupported")
        self.args = Namespace(**vars(args))
        if args.cosim_action == "generate":
            output = Path(args.out)
            self.args.out = output.parent.resolve() / output.name
            self.options["out"] = self.args.out
        for name in ("elf", "trace", "sail_config"):
            path = getattr(args, name, None)
            if path is not None:
                self.files[name] = item = c.file(path)
                setattr(self.args, name, item.copy)
        platform_path = args.platform or Path(__file__).parent / "configs" / f"{args.core}.json"
        self.files["platform"] = c.file(platform_path)
        self.platform = Platform.load(args.core, self.files["platform"].copy)
        self.core_run = None
        if args.cosim_action == "check":
            adjacent = Path(args.trace).parent / "result.json"
            if adjacent.exists():
                self.files["core_run"] = c.file(adjacent)
                self.core_run = json.loads(self.files["core_run"].copy.read_text())
        if args.cosim_action == "generate" and Path(args.out).exists():
            if Path(args.out).is_dir():
                raise ValueError(f"--out {args.out} is a directory")
            if Path(args.out).samefile(args.elf):
                raise ValueError("--out is the ELF itself")
            self.files["overwrite_guard"] = existing = c.file(args.out)
            with open(existing.copy, "rb") as stream:
                first = stream.readline(65536)
            try:
                header = json.loads(first)
            except ValueError:
                header = None
            if not isinstance(header, dict) or header.get("schema") not in ("rvw.rvfi/1", "rvw.rvfi/2"):
                raise ValueError(f"refusing to overwrite {args.out}: it exists and is not a C2 trace")
            if header.get("config") != "reference":
                raise ValueError(f"refusing to overwrite {args.out}: it is a recorded core trace "
                                 f"(core {header.get('core')!r}, config {header.get('config')!r}), not a reference trace")
        self.revision = c.git_ref(ROOT, "HEAD")
        self.shim = None
        self.pythonpath = None
        self.default_sail_config = None
        model = getattr(args, "model", "spike") if args.cosim_action == "check" else "spike"
        if model == "sail":
            self.tool = c.tool(args.sail)
            self.args.sail = str(self.tool.path)
            if not args.sail_config:
                from .sail_config import query
                self.default_sail_config = query(self.tool.path, ["--print-default-config",
                    *(["--rv32"] if self.platform.xlen == 32 else [])], args.timeout, env=self.child_env)
        else:
            self.shim = capture_shim(c, self.env["RVW_SPIKE_SHIM"] or ROOT / "Cosim/build/librvw_spike.so")
            # The MCP worker starts at the resolved interpreter. Select that same
            # executable for the CLI probe before Capture pins and verifies it.
            self.tool = c.tool(os.path.realpath(sys.executable))
            self.pythonpath = c.tree(ROOT / "rvw/src").copy
        self.record = c.record()

    def identity(self, name):
        item = self.files[name]
        return next(row for row in self.record["files"] if row["copy"] == item.copy.relative_to(self.capture.root).as_posix())

    def metadata(self):
        option_names = ("cosim_action", "core") + (
            ("model", "history", "strict", "strict_sync", "timeout")
            if self.options["cosim_action"] == "check" else ("max_instructions",))
        info = {"platform": self.platform.describe(), "tools_rev": self.revision,
                "capture": _public_record(self.record), "cache_key": None,
                "options": {name: self.options[name] for name in option_names}}
        for name in ("elf", "trace", "sail_config", "platform"):
            if name not in self.files:
                continue
            row = self.identity(name)
            info["platform_file" if name == "platform" else name] = row["resolved"]
            info[name + "_sha256"] = row["sha256"]
        if "trace" in self.files:
            with self.files["trace"].copy.open() as stream:
                info["trace_header"] = json.loads(next(stream))
        if self.default_sail_config is not None:
            info["sail_default_config"] = self.default_sail_config
        if self.core_run is not None:
            info["core_run"] = {k: self.core_run.get(k) for k in ("source", "config", "seed", "tools", "replay")}
        if self.shim:
            info["tools"] = {"shim_sha256": self.shim["library"]["sha256"], "spike_build": self.shim["manifest_data"]}
        else:
            tool = next(row for row in self.record["tools"] if row["source"] == self.tool.source)
            info["tools"] = {"sail": tool["version"]}
        a = self.options
        command = ["rvw", "cosim", a["cosim_action"], "--elf", info["elf"], "--core", a["core"],
                   "--platform", info["platform_file"]]
        if a["cosim_action"] == "check":
            command += ["--trace", info["trace"], "--model", a["model"], "--history", str(a["history"]), "--timeout", str(a["timeout"])]
            if a["strict"]:
                command += ["--strict"]
            if a["strict_sync"]:
                command += ["--strict-sync", ",".join(a["strict_sync"])]
            if a["model"] == "sail":
                command += ["--sail", str(self.tool.path)]
                if "sail_config" in info:
                    command += ["--sail-config", info["sail_config"]]
        else:
            command += ["--out", os.path.abspath(a["out"]), "--max-instructions", str(a["max_instructions"])]
        info["replay"] = shlex.join(command + ["--json"])
        return info
