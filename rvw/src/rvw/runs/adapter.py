"""Re-running a C1 run through its core adapter with changed options.

The adapter command comes from the run's `replay` string (C1), e.g.
`RiscvSim/boom/run.sh run --elf X --seed 1 --config large --out D`. It is parsed into options,
overridden (seed, max cycles, memory latency, wave window, output dir, ...) and run again while
holding the machine-wide core lock (`rvw.common.lock`, the lock `scripts/with-lock.sh <core>` takes),
so heavy simulations queue. The lock is taken here, before the adapter starts: a `timeout` counts
only the adapter's own run time, never the wait in the lock queue, which `Attempt.lock_wait`
reports. The adapter inherits the lock descriptor, so the lock lives as long as it runs.

Every attempt writes to a directory that it creates itself (`fresh_dir`), so a `result.json` found
afterwards can only come from this attempt; a failed re-run never returns an older result. The
adapter runs in its own process group (`rvw.common.proc.run_group`): a timeout or a cancel stops
the whole tree (lock wrapper, sbt/JVM, simulator), not only the direct child.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..common import lock as corelock
from ..common.proc import run_group
from .result import Run, open_run, tools_root

# C1 options that take no value
FLAGS = {"--rvfi-trace", "--wave", "--konata", "--coverage", "--json", "--rvfi"}


@dataclass
class Command:
    env: dict[str, str] = field(default_factory=dict)   # VAR=value prefixes
    exe: list[str] = field(default_factory=list)        # adapter (maybe with interpreter)
    sub: str = "run"
    opts: dict[str, object] = field(default_factory=dict)  # "--seed": "1", "--wave": True
    notes: list[str] = field(default_factory=list)         # warnings from parse_replay

    environment: dict[str, str] | None = field(default=None, repr=False)
    inputs: object = field(default=None, repr=False)
    unset: list[str] = field(default_factory=list)

    def set(self, **kw) -> "Command":
        """Copy with options changed: set(seed=3, max_cycles=None, wave=True). None removes."""
        c = Command(dict(self.env), list(self.exe), self.sub, dict(self.opts), list(self.notes),
                    self.environment, self.inputs, list(self.unset))
        for k, v in kw.items():
            key = "--" + k.replace("_", "-")
            if v is None or v is False:
                c.opts.pop(key, None)
            elif v is True:
                c.opts[key] = True
            else:
                c.opts[key] = str(v)
        return c

    def get(self, k: str, default=None):
        return self.opts.get("--" + k.replace("_", "-"), default)

    def argv(self) -> list[str]:
        out = list(self.exe) + [self.sub]
        for k, v in self.opts.items():
            if v is True:
                out.append(k)
            else:
                out += [k, str(v)]
        return out

    def shell(self) -> str:
        if self.unset:
            return shlex.join(['env', *[arg for name in self.unset for arg in ('-u', name)],
                               *[f'{k}={v}' for k, v in self.env.items()], *self.argv()])
        env = " ".join(f"{k}={shlex.quote(v)}" for k, v in self.env.items())
        return (env + " " if env else "") + shlex.join(self.argv())

    def child_environment(self) -> dict[str, str]:
        env = dict(self.environment if self.environment is not None else os.environ)
        for name in self.unset:
            env.pop(name, None)
        env.update(self.env)
        return env


def _adapter_path(tok: str, root: Path, notes: list[str]) -> str:
    """Resolve one executable token of a replay against the current tools checkout.

    Repo-relative paths (`RiscvSim/boom/run.sh`, what C1 asks adapters to write) resolve against
    `root`. Absolute paths written by older adapters point into whichever worktree produced the
    run; `.../RiscvSim/<core>/<file>` is mapped to the same file in `root`, with a note, so a re-run
    uses this checkout's adapter. Other absolute paths are kept."""
    if not os.path.isabs(tok):
        cand = root / tok
        return str(cand.absolute()) if cand.exists() else tok
    parts = Path(tok).parts
    if any(re.fullmatch(r'inputs-[0-9a-f]{32}', part) for part in parts):
        return tok  # C8 replay inputs belong to the command, not the current tools checkout.
    if "RiscvSim" in parts:
        k = len(parts) - 1 - parts[::-1].index("RiscvSim")
        if len(parts) - k >= 3:          # RiscvSim/<core>/<file...>
            cand = root.joinpath(*parts[k:])
            if cand.exists() and (not Path(tok).exists() or Path(tok).resolve() != cand.resolve()):
                notes.append(f"replay adapter {tok} is not in this checkout; using {cand}")
                return str(cand.resolve())
    return tok


def parse_replay(replay: str, root: Path | None = None) -> Command:
    toks = shlex.split(replay)
    c = Command()
    i = 0
    while i < len(toks) and "=" in toks[i] and not toks[i].startswith("-") and "/" not in toks[i].split("=")[0]:
        k, v = toks[i].split("=", 1)
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k):
            raise ValueError(f'unsupported replay environment name: {k}')
        c.env[k] = v
        i += 1
    if i < len(toks) and Path(toks[i]).name == 'env':
        i += 1
        while i < len(toks) and toks[i].startswith('-'):
            option = toks[i]
            i += 1
            if option == '--':
                break
            if option in ('-u', '--unset') and i < len(toks):
                name = toks[i]
                i += 1
            elif option.startswith('--unset='):
                name = option.split('=', 1)[1]
            else:
                raise ValueError(f'unsupported replay environment option: {option}')
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
                raise ValueError(f'unsupported replay environment name: {name}')
            c.unset.append(name)
            c.env.pop(name, None)
        while i < len(toks) and '=' in toks[i] and not toks[i].startswith('-'):
            name, value = toks[i].split('=', 1)
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
                raise ValueError(f'unsupported replay environment name: {name}')
            c.env[name] = value
            i += 1
    # executable: everything up to the subcommand (run)
    j = i
    while j < len(toks) and toks[j] not in ("run", "run-many", "build"):
        j += 1
    if j >= len(toks):
        raise ValueError(f"cannot find the adapter subcommand in replay: {replay}")
    if i == j:
        raise ValueError('replay environment prefix has no adapter')
    root = Path(root or tools_root())
    c.exe = [_adapter_path(e, root, c.notes) for e in toks[i:j]]
    for n in c.notes:
        print(f"[rvw] warning: {n}", file=sys.stderr, flush=True)
    c.sub = toks[j]
    k = j + 1
    while k < len(toks):
        t = toks[k]
        if t.startswith("--"):
            if "=" in t:
                a, b = t.split("=", 1)
                c.opts[a] = b
            elif t in FLAGS or k + 1 >= len(toks) or toks[k + 1].startswith("--"):
                c.opts[t] = True
            else:
                c.opts[t] = toks[k + 1]
                k += 1
        k += 1
    return c


def command_for(run: Run, *, root: Path | None = None) -> Command:
    """The adapter command that reproduces `run` exactly (seed, config, max cycles, latency)."""
    root = root or tools_root()
    replay = run.get("replay")
    if replay:
        c = parse_replay(replay, root=root)
    else:
        core = run.get("core") or "core"
        c = Command(exe=[str(root / "RiscvSim" / core / "run.sh")], sub="run")
    # Pin everything the result recorded, so the replay is exact even if `replay` omitted it.
    pins = {"elf": run.get("elf"), "config": run.get("config"), "seed": run.get("seed"),
            "max_cycles": run.get("max_cycles"), "mem_latency": run.get("mem_latency")}
    for k, v in pins.items():
        if v is not None:
            c = c.set(**{k: v})
        elif k == "mem_latency":
            c = c.set(mem_latency=None)    # absent = randomized timing
    return c


def lock_prefix(core: str | None) -> list[str]:
    """`with-lock.sh <core>` for commands written out for a human (replay.sh)."""
    if os.environ.get("RVW_NO_LOCK") or not core:
        return []
    script = tools_root() / "scripts" / "with-lock.sh"
    return [str(script), core] if script.exists() else []


def lock_name(core: str | None) -> str | None:
    """The machine-wide lock a re-run of `core` takes (None with RVW_NO_LOCK or no core)."""
    return None if os.environ.get("RVW_NO_LOCK") or not core else core


class _Locked:
    """Hold lock `name` (None: no lock) for a block and measure the wait; progress goes to `log`."""
    def __init__(self, name: str | None, log):
        self.name, self.log, self.wait = name, log, 0.0
        self._cm = None

    def __enter__(self):
        t = time.monotonic()
        if self.name:
            self._cm = corelock.held(self.name, log=self.log)
            self._cm.__enter__()
        self.wait = time.monotonic() - t
        if self.name and self.wait >= 1:
            self.log.write(f"[rvw] waited {self.wait:.0f}s for the {self.name} lock\n")
            self.log.flush()
        return self

    def __exit__(self, *exc):
        if self._cm is not None:
            return self._cm.__exit__(*exc)
        return False


@dataclass
class Attempt:
    """One adapter invocation. `run` is set only when this invocation wrote a valid result.json
    into its own fresh directory and was not stopped by the wall-clock timeout."""
    run: Run | None
    dir: Path
    wall: float
    returncode: int | None = None
    timed_out: bool = False
    log: Path | None = None
    error: str | None = None
    lock_wait: float = 0.0      # seconds spent waiting for the core lock (not part of `wall` or the timeout)


def fresh_dir(out: str | os.PathLike) -> Path:
    """Create a new, empty directory for one attempt: `out` if it does not exist yet, else
    `out-2`, `out-3`, ... (mkdir is atomic, so concurrent attempts never share a directory, and an
    existing directory or link is never written into)."""
    out = Path(out).absolute()
    out.parent.mkdir(parents=True, exist_ok=True)
    for n in range(1, 100000):
        d = out if n == 1 else out.with_name(f"{out.name}-{n}")
        try:
            d.mkdir()
        except FileExistsError:
            continue
        return d.resolve()
    raise RuntimeError(f"no free attempt directory next to {out}")


def _collect(d: Path, started: float, cmd: Command | None = None) -> tuple[Run | None, str | None]:
    f = d / "result.json"
    if not f.exists():
        return None, f"no result.json in {d}"
    # The directory was created by this attempt; the mtime check guards against an adapter that
    # copies an old result in.
    if f.stat().st_mtime < started - 2:
        return None, f"{f} predates this attempt"
    try:
        from .inputs import new_capture
        run = open_run(d, capture=new_capture())
        if cmd is not None:
            elf = cmd.get("elf")
            if elf is not None:
                import hashlib
                expected = hashlib.sha256(Path(elf).read_bytes()).hexdigest()
                if run.get("elf_sha256") != expected:
                    why = "C1 ELF hash is missing or differs from requested ELF"
                    run.result.extra["inconclusive"] = why
                    run.data["inconclusive"] = why
                    return run, why
            for name in ("seed", "config", "max_cycles", "mem_latency"):
                wanted = cmd.get(name)
                if wanted is None:
                    continue
                if name != "config":
                    wanted = int(wanted)
                actual = run.get(name)
                if type(actual) is not type(wanted) or actual != wanted:
                    why = f"C1 {name} {actual!r} differs from requested {wanted!r}"
                    run.result.extra["inconclusive"] = why
                    run.data["inconclusive"] = why
                    return run, why
        return run, None
    except (OSError, ValueError) as e:
        return None, str(e)


def execute(cmd: Command, out: Path, core: str | None = None, log: Path | None = None,
            timeout: float | None = None, lock: bool = True) -> Attempt:
    """Run `cmd` with `--out` set to a fresh directory derived from `out` (see `fresh_dir`).
    `timeout` starts once the core lock is held."""
    d = fresh_dir(out)
    c = cmd.set(out=str(d))
    argv = c.argv()
    log = Path(log) if log else (d / "rerun.log")
    with open(log, "w") as lf:
        lf.write("$ " + c.shell() + "\n")
        lf.flush()
        with _Locked(lock_name(core) if lock else None, lf) as held:
            env = c.child_environment()
            started = time.time()
            t = time.monotonic()
            r = run_group(argv, stdout=lf, stderr=subprocess.STDOUT, env=env, timeout=timeout,
                          cwd=str(tools_root()))
            wall = time.monotonic() - t
        if r.timed_out:
            lf.write(f"\n[rvw] stopped the adapter's process group after {timeout}s of run time\n")
    if r.timed_out:
        return Attempt(None, d, wall, r.returncode, True, log, f"timed out after {timeout}s", held.wait)
    if c.inputs is not None:
        c.inputs.verify()
    run, err = _collect(d, started, c)
    return Attempt(run, d, wall, r.returncode, False, log, err, held.wait)


def _manifest_entry(cmd: Command) -> dict:
    j = {}
    for k, v in cmd.opts.items():
        j[k[2:].replace("-", "_")] = v if v is True else (int(v) if str(v).lstrip("-").isdigit() else v)
    return j


def execute_many(cmds: list[Command], outs: list[Path], core: str | None = None, jobs: int = 1,
                 timeout: float | None = None, log: Path | None = None) -> list[Attempt]:
    """Run several variants of one adapter command, each into its own fresh directory. Uses the
    adapter's `run-many` (one JVM, one compiled model) and falls back to one `run` per command if
    that yields no results (and did not time out)."""
    if not cmds:
        return []
    environment = cmds[0].environment if cmds[0].environment is not None else os.environ
    if len(cmds) > 1 and not environment.get("RVW_NO_RUN_MANY"):
        dirs = [fresh_dir(o) for o in outs]
        base = cmds[0]
        fd, manifest = tempfile.mkstemp(prefix="manifest-", suffix=".jsonl", dir=dirs[0].parent)
        with os.fdopen(fd, "w") as f:
            for c, o in zip(cmds, dirs):
                f.write(json.dumps(_manifest_entry(c.set(out=str(o)))) + "\n")
        from .inputs import new_capture
        capture = base.inputs.capture if base.inputs is not None else new_capture()
        manifest = str(capture.file(Path(manifest)).copy)
        many = Command(dict(base.env), list(base.exe), "run-many", {"--manifest": manifest,
                                                                     "--jobs": str(jobs)}, environment=base.environment,
                       inputs=base.inputs, unset=list(base.unset))
        argv = many.argv()
        log = Path(log) if log else (dirs[0].parent / "run-many.log")
        budget = timeout * len(cmds) if timeout else None
        with open(log, "a") as lf:
            lf.write("$ " + many.shell() + "\n")
            lf.flush()
            with _Locked(lock_name(core), lf) as held:
                env = many.child_environment()
                started = time.time()
                t = time.monotonic()
                r = run_group(argv, stdout=lf, stderr=subprocess.STDOUT, env=env, cwd=str(tools_root()),
                              timeout=budget)
                wall = time.monotonic() - t
            if r.timed_out:
                lf.write(f"\n[rvw] run-many stopped after {budget}s of run time\n")
        if many.inputs is not None:
            many.inputs.verify()
        res = []
        for d, cmd in zip(dirs, cmds):
            run, err = _collect(d, started, cmd)
            res.append(Attempt(run, d, wall, r.returncode, r.timed_out and run is None, log,
                               err if run is None and not r.timed_out else
                               (f"run-many timed out after {budget}s" if run is None else None), held.wait))
        if any(a.run is not None for a in res) or r.timed_out:
            return res
    return [execute(c, o, core=core, timeout=timeout) for c, o in zip(cmds, outs)]
