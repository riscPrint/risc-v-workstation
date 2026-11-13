"""Shared pieces of the `rvw formal` commands: elaborated ports, running yosys/sby, and mapping
SymbiYosys failures back to SpinalChecks check ids."""
from __future__ import annotations

import contextlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from rvw.common.proc import TIMEOUT_EXIT
from rvw.common.sby import TOOL_GRACE_S, execute
from .tools import ACTIVE


@dataclass
class Port:
    name: str
    direction: str  # input | output | inout
    width: int
    signed: bool = False

    def decl(self) -> str:
        rng = f"[{self.width - 1}:0] " if self.width > 1 else ""
        return f"{'signed ' if self.signed else ''}{rng}{vid(self.name)}"


def vid(name: str) -> str:
    """A Verilog identifier, escaped when it is not a simple one (flattened names contain dots)."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", name) else f"\\{name} "


def die(msg: str) -> "NoReturn":
    """An input or usage error: no result is written. Exit code 2 (a written result exits 0 or 1)."""
    print(f"rvw formal: {msg}", file=sys.stderr)
    raise SystemExit(2)


# ---------------------------------------------------------------------------------------------------
# Input validation. Names and paths end up in Yosys and SymbiYosys scripts, where a newline, `;`, `#`
# or a leading `!` would start another command (a shell command for `!`). Every name and path is
# checked against a strict pattern before any script is written; names are also checked against the
# design (ports of the toplevel, signals of the flattened design) where the flow knows them.

IDENT = r"[A-Za-z_][A-Za-z0-9_$]*"
_IDENT_RE = re.compile(IDENT)
_HIER_RE = re.compile(rf"{IDENT}(?:\.{IDENT})*")
_PATH_RE = re.compile(r"[A-Za-z0-9_./+@%,=:~-]+")
_ENGINE_RE = re.compile(r"[a-z][a-z0-9_]*(?::[A-Za-z0-9_.+=-]+)*")


def check_ident(what: str, name: str) -> str:
    if not isinstance(name, str) or not _IDENT_RE.fullmatch(name):
        die(f"{what} {name!r} is not a plain identifier ([A-Za-z_][A-Za-z0-9_$]*)")
    return name


def is_hier(name) -> bool:
    return isinstance(name, str) and bool(_HIER_RE.fullmatch(name))


def check_hier(what: str, name: str) -> str:
    """A flattened hierarchical name: identifiers joined by dots, nothing else."""
    if not isinstance(name, str) or not _HIER_RE.fullmatch(name):
        die(f"{what} {name!r} is not a hierarchical name (identifiers joined by '.')")
    return name


def check_path(what: str, path) -> Path:
    s = str(Path(path).resolve())
    if not _PATH_RE.fullmatch(s):
        die(f"{what} {s!r}: paths may only contain letters, digits and _ . / + @ % , = : ~ - "
            "(they are written into Yosys scripts)")
    return Path(s)


def check_engine(engine: str) -> str:
    parts = [e.strip() for e in str(engine).split(",")]
    if not parts or any(not _ENGINE_RE.fullmatch(e) for e in parts):
        die(f"engine {engine!r} is not an engine or a comma-separated list of engines (e.g. smtbmc:yices, abc:bmc3)")
    return engine


def check_count(what: str, value, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        die(f"{what} must be an integer >= {minimum}, got {value!r}")
    return value


LOCK_NAME = ".rvw-formal.lock"


def _remove_result(out: Path) -> None:
    try:
        (out / "result.json").unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        die(f"cannot remove the old {out / 'result.json'}: {e}")


def lock_out(out: Path) -> int:
    """Take the output directory for this run: an exclusive lock on `<out>/.rvw-formal.lock`, held until
    `release(args)` (or the process exits). Every generated input, solver directory and result is under
    `out`, so a second run on the same directory (another process, or a nested call in this one: flock
    locks belong to the open file) stops here with an input error, before it removes or writes anything."""
    import fcntl
    try:
        out.mkdir(parents=True, exist_ok=True)
        fd = os.open(out / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as e:
        die(f"cannot create the lock {out / LOCK_NAME}: {e}")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        die(f"another rvw formal run is using --out {out}; wait for it or use another --out")
    except OSError as e:
        os.close(fd)
        die(f"cannot lock {out / LOCK_NAME}: {e}")
    return fd


def release(args) -> None:
    """Release the output directory lock taken by `begin`."""
    token = getattr(args, "_formal_tools_token", None)
    if token is not None:
        args._formal_tools_token = None
        ACTIVE.reset(token)
    fd = getattr(args, "_rvw_out_lock", None)
    if fd is not None:
        args._rvw_out_lock = None
        os.close(fd)


def begin(args) -> Path:
    """Start of every flow: validate --out, lock it for the whole run, remove the previous result.json
    (a failed run must never leave an old result in place), then validate the common arguments. Returns
    the resolved output directory. The lock is released by `release(args)`."""
    out = check_path("--out", args.out)
    args._rvw_out_lock = lock_out(out)
    _remove_result(out)
    if not args.verilog or not args.top:
        die("give --verilog and --top, or select a project with formal.verilog and formal.top")
    for f in args.verilog:
        check_path("--verilog", f)
        if not Path(f).is_file():
            die(f"{f} does not exist")
    for opt in ("checks", "trace"):
        f = getattr(args, opt, None)
        if f:
            check_path(f"--{opt}", f)
            if not Path(f).is_file():
                die(f"{f} does not exist")
    check_ident("--top", args.top)
    check_ident("--clock", args.clock)
    if args.reset is not None:
        check_ident("--reset", args.reset)
    check_engine(args.engine)
    mode = getattr(args, 'mode', 'bmc')
    for engine in args.engine.split(','):
        engine = engine.strip()
        if (engine == 'aiger:avy' or engine == 'abc:pdr') and mode != 'prove':
            die(f'{engine} requires formal prove')
        if engine.startswith('btor:') and mode != 'bmc':
            die(f'{engine} requires bounded formal bmc')
    check_count("--depth", args.depth, 1)
    for opt in ("reset_cycles", "settle", "cycle", "time"):
        if getattr(args, opt, None) is not None:
            check_count("--" + opt.replace("_", "-"), getattr(args, opt))
    if getattr(args, "scope", None):
        check_hier("--scope", args.scope)
    for s in getattr(args, "signal", None) or []:
        check_hier("--signal", s)
    if args.timeout is not None and (not args.timeout > 0 or not math.isfinite(args.timeout)):
        die(f"--timeout must be > 0, got {args.timeout}")
    return out


def resolve_reset(args, ports: list[Port]) -> str | None:
    """The reset port: --reset when given (it must be an input of the toplevel), else `reset` if the
    toplevel has such an input, else none."""
    if any(p.direction == "inout" for p in ports):
        die("inout ports are not supported by rvw formal wrappers")
    inputs = {p.name for p in ports if p.direction == "input"}
    for p in ports:
        if p.name in (args.clock, args.reset or "reset") and p.width != 1:
            die(f"clock/reset port {p.name!r} is {p.width} bits wide; one bit is needed")
    if args.clock not in inputs:
        die(f"clock {args.clock!r} is not an input of {args.top} (inputs: {', '.join(sorted(inputs)) or 'none'})")
    if args.reset is not None:
        if args.reset not in inputs:
            die(f"reset {args.reset!r} is not an input of {args.top}")
        if args.reset == args.clock:
            die("--reset and --clock are the same port")
        return args.reset
    return "reset" if "reset" in inputs and args.clock != "reset" else None


# ---------------------------------------------------------------------------------------------------
# Elaborated module ports. Never infer a width or type from Verilog text.


def ports_from_json(path: Path, top: str) -> list[Port]:
    """Read the complete port interface from Yosys JSON, or refuse unreadable metadata.

    Bit offsets and ascending ranges affect HDL indexing, not instance connections. Wrappers use
    normalized descending ranges with the same bit count and signedness.
    """
    try:
        raw = json.loads(path.read_text())["modules"][top]["ports"]
        if not isinstance(raw, dict):
            raise ValueError("ports is not an object")
        ports = []
        for name, port in raw.items():
            direction, bits = port["direction"], port["bits"]
            signed = port.get("signed", 0)
            if (not isinstance(name, str) or not name or any(c.isspace() for c in name)
                    or direction not in ("input", "output", "inout")
                    or not isinstance(bits, list) or not bits
                    or any(not (type(b) is int and b >= 0 or isinstance(b, str) and b in ("0", "1", "x", "z"))
                           for b in bits)
                    or type(signed) is not int or signed not in (0, 1)):
                raise ValueError(f"invalid port metadata for {name!r}")
            ports.append(Port(name, direction, len(bits), bool(signed)))
        return ports
    except (OSError, ValueError, KeyError, TypeError) as e:
        die(f"cannot read the elaborated ports of {top} from {path}: {e}")


def module_ports(verilog_files: list[Path], top: str, out: Path,
                 timeout: float | None = None, defines: list[str] = (), *, snapshot, allow_async_reset=False, allow_latches=False) -> list[Port]:
    """Elaborate using the proof's defines and read all top ports before any optimization.

    `proc` lowers processes because `write_json` cannot serialize them. It preserves the interface.
    Check state controls here, before `prep` can remove unused or tied state in any flow.
    A failed or timed-out probe cannot reuse earlier metadata.
    """
    need("yosys")
    out.mkdir(parents=True, exist_ok=True)
    clear_outputs(out, "module_ports.json", "module_ports.ys", "module_ports.log", "module_ports.il", "module_ports.d", "slang.d")
    d = " ".join(f"-D{x}" for x in defines)
    reads = "\n".join(f"read_verilog -formal -sv {d} {check_path('--verilog', f)}" for f in verilog_files)
    if snapshot.frontend == 'slang':
        plugin = snapshot.tools.slang
        files = ' '.join(str(check_path('--verilog', f)) for f in verilog_files)
        reads = (f'plugin -i {plugin}\nread_slang --top {top} {d} '
                 f'--all-deps {out / "slang.d"} {files}')
    check_ident("--top", top)
    (out / "module_ports.ys").write_text(
        f"{reads}\nhierarchy -check -top {top}\nproc\nwrite_json -noscopeinfo {out / 'module_ports.json'}\n"
        + f"write_rtlil {out / 'module_ports.il'}\n")
    rc, _ = run(["yosys", "-q", "-E", str(out / 'module_ports.d'), "-l", str(out / 'module_ports.log'), "-s", "module_ports.ys"],
                out, out / "module_ports.out", timeout)
    if rc == TIMEOUT_EXIT:
        die(f"the port probe timed out (--timeout {timeout} s)")
    if rc != 0:
        die("the port probe (yosys) failed, see " + str(out / "module_ports.log"))
    snapshot.check_frontend()
    check_state_controls(out / "module_ports.json", allow_async_reset=allow_async_reset, allow_latches=allow_latches)
    return ports_from_json(out / "module_ports.json", top)


_STATE_LIKE = re.compile(r'(?i)^\$(?:_.*(?:FF|SR|LATCH).*|.*(?:ff|latch|mem|fsm).*|sr)$')
_SYNCHRONOUS_STATE = {'$dff', '$dffe', '$sdff', '$sdffe', '$sdffce'}
_STATE_MEMORIES = {'$memrd', '$memwr', '$memwr_v2', '$meminit', '$meminit_v2', '$mem',
                   '$memrd_v2', '$mem_v2'}


def async_state_problems(modules, *, allow_async_reset=False, allow_latches=False) -> list[str]:
    """Refuse state events outside the single-clock model in every elaborated module.

    This includes async reset/load/set/clear cells, latches and fine-grained state cells.
    Memory reads may be asynchronous, but memory async reset ports must be tied inactive.
    Unknown state types are refused instead of assuming they are synchronous.
    """
    if not isinstance(modules, dict) or not modules:
        return ['missing elaborated netlist for the asynchronous state-control check']
    problems = []
    for module, body in sorted(modules.items()):
        if not isinstance(body, dict) or not isinstance(body.get('cells'), dict):
            problems.append(f'{module}: missing cells for the asynchronous state-control check')
            continue
        for name, cell in sorted(body['cells'].items()):
            if (not isinstance(cell, dict) or not isinstance(cell.get('type'), str)
                    or not isinstance(cell.get('connections'), dict)):
                problems.append(f'{module}.{name}: unreadable cell for the asynchronous state-control check')
                continue
            kind = cell['type']
            if kind in modules:
                continue  # module bodies are all checked before pruning unused instances
            where = f'{module}.{name} ({kind})'
            if allow_latches and kind == '$dlatch':
                continue  # Explicit sampled-event equivalence only.
            if allow_async_reset and kind in {'$adff', '$adffe'}:
                continue  # clk2fflogic preserves constant-value asynchronous resets
            if _STATE_LIKE.match(kind) and kind not in _SYNCHRONOUS_STATE | _STATE_MEMORIES:
                problems.append(f'{where}: asynchronous, latched or unsupported state control; '
                                'the single-clock model supports synchronous state only')
                continue
            for port in ('ARST', 'RD_ARST', 'ALOAD', 'SET', 'CLR'):
                bits = cell['connections'].get(port)
                if port in cell['connections'] and (kind not in _STATE_MEMORIES
                        or not isinstance(bits, list) or not bits or any(b != '0' for b in bits)):
                    problems.append(f'{where}: asynchronous control {port} is not supported by the '
                                    'single-clock model')
    return problems


def check_state_controls(probe_json: Path, *, allow_async_reset=False, allow_latches=False) -> None:
    """Refuse unsupported state controls with exit 2, before writing a proof result."""
    try:
        problems = async_state_problems(json.loads(probe_json.read_text())['modules'], allow_async_reset=allow_async_reset, allow_latches=allow_latches)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems = [f'cannot read the asynchronous state-control probe {probe_json} ({exc})']
    if problems:
        shown = '\n  '.join(problems[:10])
        if len(problems) > 10:
            shown += f'\n  ... {len(problems) - 10} more'
        if allow_async_reset:
            die('unsupported asynchronous or latched state in event BMC; only constant-value async reset FFs '
                'are enabled. Refusing:\n  ' + shown)
        die('unsupported asynchronous or latched state: rvw formal uses a single-clock model '
            '(sby multiclock off), which can miss events between clock edges. Refusing:\n  ' + shown)


def need(tool: str) -> str:
    active = ACTIVE.get()
    if active is not None:
        return active.command([tool])[0]
    path = shutil.which(tool)
    if not path:
        die(f"'{tool}' not found on PATH (source spinal-boom/env.sh for oss-cad-suite)")
    return path


class Terminated(BaseException):
    """SIGTERM turned into an exception, so that `run_group` stops the tool's process tree on the way out
    (an MCP cancel signals this process; the tools run in their own process groups)."""


@contextlib.contextmanager
def sigterm_raises():
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def handler(signum, frame):
        raise Terminated()
    old = signal.signal(signal.SIGTERM, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, old)


def run(cmd: list[str], cwd: Path, log: Path, timeout: float | None = None) -> tuple[int, float]:
    """Run `cmd` in its own process group, writing stdout+stderr to `log`. Returns (exit code, seconds);
    124 on timeout. On timeout, error or SIGTERM the whole group is stopped (SIGTERM first: sby then stops
    the solver groups it started; SIGKILL after TOOL_GRACE_S)."""
    active = ACTIVE.get()
    env = None
    if active is not None:
        cmd, env = active.command(cmd), active.env
    return execute(cmd, cwd, log, timeout, env=env)


# ---------------------------------------------------------------------------------------------------
# One clock. Every flow runs sby with `multiclock off`: one solver step is one cycle of every register,
# memory port and clocked assertion, whatever clock drives it. That is the design's behaviour only when
# all of them are on the rising edge of --clock. A second clock, a gated or derived clock, a falling
# edge or a constant clock would be stepped together with --clock and could give a false pass (two
# independent clocks proven as one). The flows check the clocks first and refuse any other design.

# Cell types that can have a clock or trigger input after `prep` (word-level and gate-level flip-flops,
# memories and memory ports, FSMs, clocked assertions and prints).
_CLOCKED_TYPES = ("$*dff*", "$*DFF*", "$mem*", "$fsm", "$check", "$print")
CLOCKS_JSON = "clock_cells.json"


def clock_probe_cmds(top: str, out_json: Path) -> str:
    """Yosys commands (after the design is read and `prep -top top` ran) that write the clocked cells of
    the flattened `top`, its ports and the nets on clock inputs to `out_json`. They change the design:
    run them last."""
    types = " ".join(f"{top}/t:{t}" for t in _CLOCKED_TYPES)
    ports = "CLK,RD_CLK,WR_CLK,TRG"
    return (f"flatten\nopt_clean\n"
            f"select -set rvw_ck {types}\n"
            f"select -set rvw_ckw @rvw_ck %x:+[{ports}] {top}/w:* %i\n"
            f"delete {top}/* @rvw_ck %d @rvw_ckw %d {top}/x:* %d\n"
            f"write_json -noscopeinfo {out_json}\n")


def _param_bits(value, width: int) -> str | None:
    """A yosys JSON parameter as `width` bits, LSB first: a per-bit vector when it has `width` bits,
    else a scalar (any 1 bit: every bit 1). None when it has x/z bits or cannot be read."""
    if isinstance(value, int):
        return ("1" if value else "0") * width
    if not isinstance(value, str) or not value or set(value) - {"0", "1"}:
        return None
    if len(value) == width:
        return value[::-1]
    return ("1" if "1" in value else "0") * width


def clock_problems(probe_json: Path, top: str, clock: str, *, extra_clocks=()) -> list[str]:
    """Every clock or trigger input in `probe_json` (written by `clock_probe_cmds`) that is not the rising
    edge of the toplevel port `clock`, in words. Empty when the design has one clock."""
    try:
        mod = json.loads(probe_json.read_text())["modules"][top]
        clk_bits = mod["ports"][clock]["bits"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        return [f"cannot read the clock probe {probe_json} ({e})"]
    if len(clk_bits) != 1:
        return [f"--clock {clock} is {len(clk_bits)} bits wide; one bit is needed"]
    clk = clk_bits[0]
    allowed = {clk}
    for name in extra_clocks:
        port = mod.get("ports", {}).get(name, {})
        bits = port.get("bits", [])
        if port.get("direction") != "input" or len(bits) != 1 or type(bits[0]) is not int:
            return [f"event clock {name!r} must be a one-bit top input"]
        allowed.add(bits[0])
    names: dict = {}
    for name, n in sorted(mod.get("netnames", {}).items(), key=lambda kv: (kv[0].startswith("$"), kv[0])):
        for i, b in enumerate(n.get("bits", [])):
            if isinstance(b, int) and b not in names:
                names[b] = name if len(n["bits"]) == 1 else f"{name}[{i}]"
    problems = []
    for cname, cell in sorted(mod.get("cells", {}).items()):
        params = cell.get("parameters", {})
        src = cell.get("attributes", {}).get("src", "")
        where = f"{cell.get('type')} {cname}" + (f" ({src})" if src else "")
        for port, bits in sorted(cell.get("connections", {}).items()):
            if port != "TRG" and port != "CLK" and not port.endswith("_CLK"):
                continue
            n = len(bits)
            if n == 0:
                continue  # no trigger: an unclocked assertion
            en = _param_bits(params[f"{port}_ENABLE"], n) if f"{port}_ENABLE" in params else "1" * n
            pol = _param_bits(params.get(f"{port}_POLARITY"), n)
            typ = str(cell.get("type", ""))
            if pol is None and port == "CLK" and typ.startswith("$_") and f"{port}_POLARITY" not in params:
                # gate-level flip-flop: the clock edge is the first letter after the kind ($_DFFE_PN_)
                edge = (typ.split("_") + ["", "", ""])[2][:1]
                pol = {"P": "1" * n, "N": "0" * n}.get(edge)
            if en is None or pol is None:
                problems.append(f"{where}: cannot read {port}_ENABLE/{port}_POLARITY")
                continue
            for i, b in enumerate(bits):
                if en[i] != "1":
                    continue  # an asynchronous memory read port, an unclocked assertion
                if b not in allowed:
                    what = f"constant {b}" if isinstance(b, str) else names.get(b, f"net {b}")
                    problems.append(f"{where}: {port} is {what}, not {clock}")
                elif pol[i] != "1":
                    problems.append(f"{where}: {port} is the falling edge of {clock}")
    return problems


def check_one_clock(problems: list[str], clock: str, *, event_model=False) -> None:
    """Refuse (exit 2, no result) a design whose clocked cells are not all on the rising edge of `clock`."""
    if not problems:
        return
    shown = "\n  ".join(problems[:10]) + (f"\n  ... {len(problems) - 10} more" if len(problems) > 10 else "")
    if event_model:
        die("unsupported event clock; only declared rising-edge top inputs are supported. Refusing:\n  " + shown)
    die(f"the design is not clocked by the rising edge of --clock {clock} alone; rvw formal models one clock "
        "(sby multiclock off) and would step every clock together, which can give a false pass. "
        f"Refusing:\n  {shown}")


def probe_clocks(files: list[Path], top: str, clock: str, out: Path, timeout: float | None, *, extra_clocks=(), event_model=False) -> float:
    """Run the clock probe on the design as the flow reads it; refuse a design with more than one clock
    (see `check_one_clock`). Returns the seconds it took."""
    clear_outputs(out, CLOCKS_JSON, "clock_probe.ys", "clock_probe.log")
    reads = read_rtlil(files)
    probe = clock_probe_cmds(top, out / CLOCKS_JSON)
    if event_model:
        # Preserve dead and tied state before clock validation, just as the state probe does.
        probe = f"flatten\nwrite_json -noscopeinfo {out / CLOCKS_JSON}\n"
    (out / "clock_probe.ys").write_text(f"{reads}\nhierarchy -check -top {top}\n{probe}" if event_model
                                             else f"{reads}\nprep -top {top}\n{probe}")
    rc, secs = run(["yosys", "-q", "-s", "clock_probe.ys"], out, out / "clock_probe.log", timeout)
    if rc == TIMEOUT_EXIT:
        die(f"the clock probe timed out (--timeout {timeout} s)")
    if rc != 0:
        die("the clock probe (yosys) failed, see " + str(out / "clock_probe.log"))
    check_one_clock(clock_problems(out / CLOCKS_JSON, top, clock, extra_clocks=extra_clocks),
                    clock, event_model=event_model)
    return secs


def tool_versions() -> dict:
    """Return start-of-command identities. Never run version commands after a proof."""
    active = ACTIVE.get()
    if active is None:
        raise RuntimeError('formal tool metadata has no command capture')
    return dict(active.identities)


# ---------------------------------------------------------------------------------------------------
# SpinalChecks report and failure mapping


@dataclass
class ChecksIndex:
    """Maps (module, local fail signal) to check entries from a SpinalChecks `*.checks.json`."""
    by_module_signal: dict = field(default_factory=dict)
    checks: list = field(default_factory=list)
    channels: list = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None) -> "ChecksIndex":
        idx = cls()
        if not path:
            return idx
        data = json.loads(Path(path).read_text())
        idx.checks = data.get("checks", [])
        idx.channels = data.get("channels", [])
        for c in idx.checks:
            if c.get("fail_signal"):
                local = c["fail_signal"].rsplit(".", 1)[-1]
                idx.by_module_signal.setdefault((c["module"], local), []).append(c)
        return idx


_FAILED_RE = re.compile(r"failed assertion (\S+) at (\S+?):(\d+)\.\d+-\S+ step (\d+)")
_ASSERT_TEXT_RE = re.compile(r"assert\s*\(\s*\(?\s*!\s*(\w+)\s*\)?\s*\)")


def _verilog_path(files: dict, file: str) -> str | None:
    """Prefer the full snapshot path; a basename is usable only when it is unique."""
    path = Path(file)
    # A bare solver filename must not be resolved against the caller's working directory.
    full = files.get(str(path.resolve())) if path.is_absolute() else None
    return full or files.get(path.name)


def _verilog_line(files: dict, file: str, line: int) -> tuple[str | None, str | None]:
    """(enclosing module, line text) for file:line in one of the design files."""
    path = _verilog_path(files, file)
    if not path:
        return None, None
    lines = files.setdefault(("lines", path), Path(path).read_text(errors="replace").splitlines())
    if line - 1 >= len(lines):
        return None, None
    module = None
    for l in reversed(lines[:line]):
        m = re.match(r"\s*module\s+(\w+)", l)
        if m:
            module = m.group(1)
            break
    return module, lines[line - 1]


_STEP_RE = re.compile(r"\] (engine_\d+): .*Checking assertions in step (\d+)")
_ENGINE_FAIL_RE = re.compile(r"\] (engine_\d+): .*Assert failed in \S+: (\S+?)(?::(\d+)\.\d+-\S+)?(?: \((\S+)\))?(?: \[failed before\])?$")


def engine_failures(text: str) -> list[tuple[str, str | None, int | None, int]]:
    """(property or label, file, line, step) for each assertion an engine reports failing, first time only.
    sby's summary lists only some of them when many fail (--keep-going)."""
    step: dict[str, int] = {}
    out, seen = [], set()
    for line in text.splitlines():
        m = _STEP_RE.search(line)
        if m:
            step[m.group(1)] = int(m.group(2))
            continue
        m = _ENGINE_FAIL_RE.search(line)
        if m and "[failed before]" not in line:
            eng, what, ln, prop = m.groups()
            key = (prop or what, what, ln) if ln else what
            if key in seen:
                continue
            seen.add(key)
            # A failure found while checking step k is reported by smtbmc in the same step numbering.
            out.append((prop or what, what if ln else None, int(ln) if ln else None, step.get(eng, 0)))
    return out


def _assertion_delays(model_json: Path | None) -> dict[tuple[str, int], int]:
    """Known clocked-assertion delays by elaborated source location. Ambiguity leaves no mapping."""
    if model_json is None:
        return {}
    try:
        modules = json.loads(model_json.read_text())["modules"]
        delays: dict[tuple[str, int], set[int | None]] = {}
        for module in modules.values():
            for cell in module.get("cells", {}).values():
                params = cell.get("parameters", {})
                if not (cell["type"] == "$assert" or
                        cell["type"] == "$check" and params.get("FLAVOR") == "assert"):
                    continue
                triggers = cell.get("connections", {}).get("TRG", [])
                delay = 1 if (cell["type"] == "$check" and len(triggers) == 1 and
                              _param_bits(params.get("TRG_ENABLE"), 1) == "1" and
                              _param_bits(params.get("TRG_POLARITY"), 1) == "1") else None
                for src in cell.get("attributes", {}).get("src", "").split("|"):
                    match = re.fullmatch(r"(.+):(\d+)\.\d+-.*", src)
                    if match:
                        file, line = match.groups()
                        key = (str(Path(file).resolve()), int(line))
                        delays.setdefault(key, set()).add(delay)
        return {key: 1 for key, values in delays.items() if values == {1}}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}  # Reporting cannot infer a cycle from missing or unreadable metadata.


def parse_failures(sby_log: Path, verilog_files: list[Path], checks: ChecksIndex, cycle_offset: int = 0,
                   property_model: Path | None = None) -> list[dict]:
    """Failed assertions reported by sby, with the check they belong to when SpinalChecks generated them."""
    files: dict = {}
    for f in verilog_files:
        path = str(f.resolve())
        files[path] = path
        files[f.name] = path if f.name not in files or files[f.name] == path else None

    def location(file: str, line: int) -> tuple[str, int]:
        return (_verilog_path(files, file) or file, line)

    delays = _assertion_delays(property_model)
    out, seen = [], set()
    text = sby_log.read_text(errors="replace") if sby_log.exists() else ""
    found = [(m.group(1), m.group(2), int(m.group(3)), int(m.group(4))) for m in _FAILED_RE.finditer(text)]
    summarized = {location(f[1], f[2]) for f in found}
    for prop, file, line, step in engine_failures(text):
        if file and line and location(file, line) not in summarized:
            found.append((prop, file, line, step))
    for prop, file, line, step in found:
        key = (prop, location(file, line), step)
        if key in seen:
            continue
        seen.add(key)
        module, src = _verilog_line(files, file, line)
        # Only an unambiguous, elaborated clocked property earns the one-step correction.
        delay = delays.get(location(file, line))
        cycle = cycle_offset + step - delay if delay is not None and step >= delay else None
        entry = {"property": prop, "location": f"{os.path.basename(file)}:{line}", "step": step,
                 "cycle": cycle, "module": module, "check": None, "kind": None, "source": None}
        if src:
            a = _ASSERT_TEXT_RE.search(src)
            if a:
                hits = checks.by_module_signal.get((module, a.group(1)), [])
                if hits:
                    entry["check"] = hits[0]["id"] if len(hits) == 1 else [h["id"] for h in hits]
                    entry["kind"] = hits[0]["kind"]
                    s = hits[0].get("source")
                    entry["source"] = f"{s['file']}:{s['line']}" if s else None
                entry["fail_signal"] = a.group(1)
        out.append(entry)
    return out


def sby_result(log_text: str) -> tuple[str, int | None]:
    """Status and exit code from the last SBY `DONE (STATUS, rc=N)` line."""
    matches = re.findall(r"DONE \((\w+), rc=(\d+)\)", log_text)
    return (matches[-1][0].lower(), int(matches[-1][1])) if matches else ("error", None)


def clear_outputs(out: Path, *names: str) -> None:
    """Remove the earlier run's `names` (files or directories) under `out`; stop if one cannot go."""
    for name in names:
        p = out / name
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
        except FileNotFoundError:
            pass
        except OSError as e:
            die(f"cannot remove the earlier run's {p}: {e}")
        if p.exists() or p.is_symlink():
            die(f"cannot remove the earlier run's {p}")


def read_rtlil(files: list[Path]) -> str:
    """Read the already elaborated model without repeating Verilog preprocessing."""
    return "\n".join(f"read_rtlil {f.resolve()}" for f in files)


def engine_line(engine: str, keep_going: bool) -> str:
    """`smtbmc:bitwuzla` -> `smtbmc --keep-going bitwuzla`; `abc:bmc3` -> `abc bmc3`."""
    parts = engine.split(":")
    name, rest = parts[0], parts[1:]
    if name == "smtbmc" and keep_going:
        return " ".join(["smtbmc", "--keep-going", *rest])
    return " ".join([name, *rest])


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n")


def count_asserts(rtlil: Path, top: str) -> int | None:
    """Assertions in the design SymbiYosys proved (`sby/model/design_prep.il`, after prep): `$assert`
    cells of `top`, counted once per instance through the hierarchy. None if the model is missing."""
    if not rtlil.is_file():
        return None
    own: dict[str, int] = {}
    inst: dict[str, list[str]] = {}
    module = None
    for line in rtlil.read_text(errors="replace").splitlines():
        s = line.strip()
        if s.startswith("module "):
            module = s.split()[1].lstrip("\\")
            own[module], inst[module] = 0, []
        elif s.startswith("cell ") and module is not None:
            typ = s.split()[1]
            if typ == "$assert":
                own[module] += 1
            elif typ.startswith("\\"):
                inst[module].append(typ[1:])
        elif s == "end" and module is not None and not line.startswith(" "):
            module = None
    memo: dict[str, int] = {}

    def total(m: str, depth: int = 0) -> int:
        if m not in own or depth > 1000:
            return 0
        if m not in memo:
            memo[m] = own[m] + sum(total(c, depth + 1) for c in inst[m])
        return memo[m]
    return total(top) if top in own else None


def final_status(rc: int, sby_text: str, asserts: int | None) -> str:
    """A pass needs matching process/log exit codes and assertions in the prepared model."""
    answers = set(re.findall(r"Status returned by engine: (PASS|FAIL)\b", sby_text))
    if answers == {"PASS", "FAIL"}:
        return "error"
    if rc == TIMEOUT_EXIT:
        return "timeout"
    status, log_rc = sby_result(sby_text)
    if log_rc != rc:
        return "error"
    if (status == "error" and re.search(r"engine_\d+: abc bmc3(?:\s|$)", sby_text)
            and "Error: Does not work for combinational networks." in sby_text):
        die("abc:bmc3 cannot check a model reduced to a combinational network. "
            "Use --engine smtbmc:yices and run the proof again. "
            "The solver log is in sby/logfile.txt under --out.")
    if status == "pass":
        if rc != 0:
            return "error"
        if asserts is None:
            return "error"
        if asserts == 0:
            return "no_checks"
    return status
