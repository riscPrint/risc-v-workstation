"""Core config files: which adapter to call, which configs exist, the suites and the tiers.

A core config is TOML. `--core NAME` looks for `NAME.toml` in `$RVW_CORES` (a `:`-separated list of
directories), then in `rvw/configs/`; `--core PATH.toml` loads a file directly. Strings may use
`${VAR}` and `${VAR:-default}`. Relative paths are resolved against the config file's directory.
Nothing here knows about a particular core; see `rvw/configs/boom.toml` for BOOM.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import tomllib
import tempfile
from rvw.common.capture import Capture
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs"  # rvw/configs in the source tree

KINDS = ("elf-dir", "build")
RESERVED_JOB_OPTIONS = frozenset({"config", "elf", "out", "seed", "max_cycles", "mem_latency",
                                  "rvfi_trace", "wall_timeout"})
RESERVED_BUILD_OPTIONS = frozenset({"--config", "--json", "--rvfi"})


class ConfigError(ValueError):
    pass


_METRIC_NAME = r"[A-Za-z_][A-Za-z0-9_.-]*"
_DOTTED_KEY = r"[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)*"


def metric_specs(specs) -> dict[str, str]:
    """Validate declarations once for config loading and stored-result comparison."""
    if not isinstance(specs, list):
        raise ConfigError("performance metrics must be a list of name[:direction] strings")
    parsed = {}
    directions = {"": "min", "min": "min", "lower": "min", "max": "max", "higher": "max"}
    for spec in specs:
        if not isinstance(spec, str) or re.fullmatch(
                _METRIC_NAME + r"(?::(?:min|lower|max|higher))?", spec) is None:
            raise ConfigError(f"invalid performance metric {spec!r}; use name[:min|lower|max|higher]")
        name, _, direction = spec.partition(":")
        if name in parsed:
            raise ConfigError(f"duplicate performance metric {name!r}")
        parsed[name] = directions[direction]
    return parsed


def positive_int(v, what: str, *, optional: bool = False) -> int | None:
    """`v` as a count of at least 1 (an int, not a bool, float or string), else ConfigError.
    Review 11: a negative seed count expanded to zero jobs and the run "succeeded" with no tests."""
    if v is None and optional:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        raise ConfigError(f"{what} must be a whole number of at least 1, not {v!r}")
    return v


def finite_number(v, what: str, *, positive: bool = False, optional: bool = False) -> float | None:
    """A finite numeric limit, without bool/string coercion or floating-point overflow."""
    if v is None and optional:
        return None
    try:
        ok = (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
              and (v > 0 if positive else v >= 0))
    except OverflowError:
        ok = False
    if not ok:
        bound = "positive" if positive else "non-negative"
        raise ConfigError(f"{what} must be a finite {bound} number, not {v!r}")
    return float(v)


def nonnegative_int(v, what: str, *, optional: bool = False) -> int | None:
    if v is None and optional:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ConfigError(f"{what} must be a non-negative whole number, not {v!r}")
    return v


_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand(s: str, environment=None) -> str:
    """Expand `${VAR}` / `${VAR:-default}` and a leading `~`."""
    def sub(m):
        v = (os.environ if environment is None else environment).get(m.group(1))
        if v:
            return v
        if m.group(2) is not None:
            return m.group(2)
        raise ConfigError(f"environment variable {m.group(1)} is not set (in {s!r})")
    expanded = _ENV.sub(sub, s)
    if environment is not None and expanded.startswith("~/"):
        home = environment.get("HOME")
        if not home:
            raise ConfigError("HOME is not captured for a ~ path")
        return home + expanded[1:]
    return os.path.expanduser(expanded)


def _path(s: str, base: Path, environment=None) -> Path:
    path = Path(expand(s, environment))
    if path.is_absolute():
        return path
    # Reduce leading parents against the pinned config directory. Preserve later symlinks.
    parts = list(path.parts)
    while parts and parts[0] == "..":
        base, parts = base.parent, parts[1:]
    if ".." in parts:
        raise ConfigError("non-leading .. in an input path cannot be captured safely")
    return base.joinpath(*parts)


def _cmd(v, base: Path, environment=None) -> list[str]:
    """A command: a string or a list. Elements starting with ./ or ../ are paths."""
    items = v if isinstance(v, list) else [v]
    out = []
    for i, x in enumerate(items):
        x = expand(str(x), environment)
        if x.startswith(("./", "../")) or (i == 0 and not x.startswith("/") and "/" in x):
            x = str(_path(x, base, environment))
        out.append(x)
    return out


@dataclass
class Suite:
    name: str
    kind: str = "elf-dir"
    description: str = ""
    dir: Path | None = None
    glob: str = "*"
    strip_suffix: str = ""
    include: list[str] = field(default_factory=list)  # regexes on the test id; any must match
    exclude: list[str] = field(default_factory=list)  # regexes on the test id; none may match
    configs: list[str] = field(default_factory=list)  # default configs; empty = the core default
    seeds: int = 1
    max_cycles: int | None = None
    mem_latency: int | None = None
    timeout_s: float = 600.0  # wall clock per test
    options: dict = field(default_factory=dict)  # extra run-many manifest keys
    build_options: list[str] = field(default_factory=list)  # extra `build` flags (kind = "build")
    cycles_key: str = "cycles"  # dotted path in result.json for the test's cycles
    instret_key: str = "instret"
    perf_metrics: list[str] = field(default_factory=list)  # compared by `rvw regress compare`

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        metric_specs(self.perf_metrics)
        for key in ("cycles_key", "instret_key"):
            selector = getattr(self, key)
            if (not isinstance(selector, str) or not selector
                    or any(re.fullmatch(_DOTTED_KEY, alt.strip()) is None for alt in selector.split("|"))):
                raise ConfigError(f"suite {self.name} {key} must contain dotted keys separated by |")
        positive_int(self.seeds, f"suite {self.name} seeds")
        positive_int(self.max_cycles, f"suite {self.name} max_cycles", optional=True)
        nonnegative_int(self.mem_latency, f"suite {self.name} mem_latency", optional=True)
        finite_number(self.timeout_s, f"suite {self.name} timeout_s", positive=True)
        if not isinstance(self.build_options, list) or not all(isinstance(arg, str) for arg in self.build_options):
            raise ConfigError(f"suite {self.name} build_options must be a list of strings")
        for arg in self.build_options:
            if arg.partition("=")[0] in RESERVED_BUILD_OPTIONS:
                raise ConfigError(f"suite {self.name} build_options argument {arg!r} is reserved by the runner; "
                                  "use the selected config or runner option")
        normalized = {}
        for key, value in self.options.items():
            if not isinstance(key, str):
                raise ConfigError(f"suite {self.name} options keys must be strings")
            name = key.removeprefix("--").replace("-", "_")
            if name in RESERVED_JOB_OPTIONS:
                raise ConfigError(f"suite {self.name} options.{key} is reserved by the runner; "
                                  "use the suite field or runner option")
            if name in normalized:
                raise ConfigError(f"suite {self.name} options.{key} repeats a normalized key")
            normalized[name] = value
        self.options = normalized
        try:
            json.dumps(self.options, allow_nan=False)
        except (TypeError, ValueError) as e:
            raise ConfigError(f"suite {self.name} options must be strict JSON: {e}") from e


@dataclass
class TierRun:
    suite: str
    configs: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)
    seeds: int | None = None


@dataclass
class Tier:
    name: str
    description: str = ""
    runs: list[TierRun] = field(default_factory=list)


@dataclass
class CoreConfig:
    name: str
    path: Path
    adapter: list[str]
    configs: list[str]
    default_config: str
    lock: str | None = None
    lock_dir: Path | None = None
    source_repo: Path | None = None
    source_env: str | None = None
    cache_paths: list[Path] = field(default_factory=list)
    input_complete: bool = False  # explicit user claim: all adapter dependencies are declared
    input_env: list[str] = field(default_factory=list)
    input_tools: list[str] = field(default_factory=list)
    input_verilator_toolchain: bool = False  # select compiler/linker from the installed verilated.mk
    input_commands: list[str] = field(default_factory=list)  # pinned commands without a --version interface
    identity_capture: bool = False  # `identity --config C --options JSON` prints rvw.adapter-capture/2
    capture: dict = field(default_factory=dict, repr=False)
    identity: bool = False  # the adapter has `identity` (C1): text that changes with its toolchain/sources
    identity_timeout_s: float = 120.0
    wall_timeout: bool = False  # the adapter honours a per-job `wall_timeout` manifest key (C1)
    known_failures: Path | None = None
    jobs: int = 4
    persistent: bool = False  # serial fresh-instance server in run-many
    build_first: bool = True
    build_timeout_s: float = 3600.0
    startup_s: float = 120.0
    perf_tolerance: float = 0.01
    suites: dict[str, Suite] = field(default_factory=dict)
    tiers: dict[str, Tier] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.input_complete, bool):
            raise ConfigError("core.input_complete must be a boolean")
        if not isinstance(self.input_verilator_toolchain, bool):
            raise ConfigError("core.input_verilator_toolchain must be a boolean")
        if not isinstance(self.identity_capture, bool) or (self.identity_capture and not self.identity):
            raise ConfigError("core.identity_capture requires identity=true and a boolean value")
        for key in ("input_env", "input_tools", "input_commands"):
            if not isinstance(getattr(self, key), list) or not all(isinstance(v, str) and v for v in getattr(self, key)):
                raise ConfigError(f"core.{key} must be a list of non-empty strings")
        if not isinstance(self.persistent, bool):
            raise ConfigError("core.persistent must be a boolean")
        positive_int(self.jobs, "core.jobs")
        for key in ("identity_timeout_s", "build_timeout_s", "startup_s"):
            finite_number(getattr(self, key), f"core.{key}", positive=True)
        finite_number(self.perf_tolerance, "core.perf_tolerance")

    def require_source_selection(self) -> None:
        if not isinstance(self.source_env, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.source_env):
            raise ConfigError(f"core {self.name}: a selected source tree needs a valid [core] source_env "
                              f"in {self.path}; the adapter must read that environment variable")

    def suite(self, name: str) -> Suite:
        try:
            return self.suites[name]
        except KeyError:
            raise ConfigError(f"core {self.name}: no suite {name!r} (have: {', '.join(self.suites)})") from None

    def tier(self, name: str) -> Tier:
        try:
            return self.tiers[name]
        except KeyError:
            raise ConfigError(f"core {self.name}: no tier {name!r} (have: {', '.join(self.tiers)})") from None

    def suite_configs(self, suite: Suite) -> list[str]:
        return suite.configs or [self.default_config]


def find_config(core: str) -> Path:
    p = Path(core).expanduser()
    if p.suffix == ".toml" or p.is_file():
        if not p.is_file():
            raise ConfigError(f"no core config file {p}")
        return p.absolute()
    dirs = [Path(d) for d in os.environ.get("RVW_CORES", "").split(":") if d] + [CONFIG_DIR]
    for d in dirs:
        if (d / f"{core}.toml").is_file():
            return (d / f"{core}.toml").absolute()
    raise ConfigError(f"no core config {core}.toml in {', '.join(map(str, dirs))}")


def _strs(v, what) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ConfigError(f"{what} must be a string or a list of strings")
    return list(v)


def _check_keys(d: dict, allowed: set[str], what: str) -> None:
    bad = set(d) - allowed
    if bad:
        raise ConfigError(f"{what}: unknown keys {', '.join(sorted(bad))}")


def _platform_commands(value) -> list[str]:
    if not isinstance(value, dict):
        raise ConfigError("core.input_commands_by_platform must be a table")
    commands = {}
    for platform, names in value.items():
        if not isinstance(platform, str) or not platform:
            raise ConfigError("core.input_commands_by_platform needs non-empty platform names")
        commands[platform] = _strs(names, f"core.input_commands_by_platform.{platform}")
        if any(not name for name in commands[platform]):
            raise ConfigError(f"core.input_commands_by_platform.{platform} needs non-empty commands")
    return commands.get(sys.platform, [])


def load_config(core: str | None = None, *, project=None, capture=None) -> CoreConfig:
    from rvw.common.project import select_core, parse_project, find_project
    if core is None and project is None:
        project = find_project()
    selected = select_core(core, project)
    if selected is None:
        raise ConfigError("give --project, create rvw.toml, or give --core")
    path = find_config(selected)
    with tempfile.TemporaryDirectory(prefix="rvw-config-") as directory:
        capture = capture or Capture(Path(directory) / "capture")
        item = capture.file(path)
        text = item.copy.read_text()
        raw = tomllib.loads(text)
        environment = capture.env("HOME", "RVW_CORES", "RVW_CORE", *(match.group(1) for match in _ENV.finditer(text)))
        is_project = project is not None or path.name == "rvw.toml" or "project" in raw
        project_config = parse_project(raw, Path(item.resolved), environment) if is_project else None
        config_record = capture.record()
    base = Path(item.resolved).parent
    c = raw.get("core")
    if not isinstance(c, dict):
        raise ConfigError(f"{path}: missing [core] table")
    _check_keys(c, {"name", "adapter", "configs", "default_config", "lock", "lock_dir", "source_repo",
                    "source_env", "cache_paths", "input_complete", "input_env", "input_tools", "input_verilator_toolchain", "input_commands", "input_commands_by_platform", "identity_capture", "identity", "identity_timeout_s", "wall_timeout", "known_failures", "jobs", "persistent", "build_first", "build_timeout_s",
                    "startup_s", "perf_tolerance"}, f"{path} [core]")
    if "adapter" not in c:
        raise ConfigError(f"{path}: [core] needs adapter")
    configs = _strs(c.get("configs"), "core.configs")
    cfg = CoreConfig(
        name=c.get("name", path.stem),
        path=path,
        adapter=_cmd(c["adapter"], base, environment),
        configs=configs,
        default_config=c.get("default_config", configs[0] if configs else "default"),
        lock=c.get("lock"),
        lock_dir=_path(c["lock_dir"], base, environment) if c.get("lock_dir") else None,
        source_repo=(_path(c["source_repo"], base, environment) if c.get("source_repo")
                     else project_config.root if project_config else None),
        source_env=c.get("source_env"),
        cache_paths=[_path(p, base, environment) for p in _strs(c.get("cache_paths"), "core.cache_paths")],
        input_complete=c.get("input_complete", False),
        input_env=_strs(c.get("input_env"), "core.input_env"),
        input_tools=_strs(c.get("input_tools"), "core.input_tools"),
        input_verilator_toolchain=c.get("input_verilator_toolchain", False),
        input_commands=(_strs(c.get("input_commands"), "core.input_commands")
                        + _platform_commands(c.get("input_commands_by_platform", {}))),
        identity_capture=c.get("identity_capture", False),
        identity=bool(c.get("identity", False)),
        identity_timeout_s=c.get("identity_timeout_s", 120),
        wall_timeout=bool(c.get("wall_timeout", False)),
        known_failures=_path(c["known_failures"], base, environment) if c.get("known_failures") else None,
        jobs=c.get("jobs", 4),
        persistent=c.get("persistent", False),
        build_first=bool(c.get("build_first", True)),
        build_timeout_s=c.get("build_timeout_s", 3600),
        startup_s=c.get("startup_s", 120),
        perf_tolerance=c.get("perf_tolerance", 0.01),
    )
    cfg.capture = config_record
    if project_config:
        cfg.cache_paths.extend(p for p in project_config.inputs if p not in cfg.cache_paths)
    suite_keys = {f for f in Suite.__dataclass_fields__ if f != "name"}
    for name, s in (raw.get("suites") or {}).items():
        _check_keys(s, suite_keys, f"{path} [suites.{name}]")
        kind = s.get("kind", "elf-dir")
        if kind not in KINDS:
            raise ConfigError(f"{path} [suites.{name}]: kind must be one of {', '.join(KINDS)}")
        if kind == "elf-dir" and "dir" not in s:
            raise ConfigError(f"{path} [suites.{name}]: elf-dir suites need dir")
        for k in ("include", "exclude"):
            for rx in _strs(s.get(k), k):
                try:
                    re.compile(rx)
                except re.error as e:
                    raise ConfigError(f"{path} [suites.{name}] {k}: bad regex {rx!r}: {e}") from None
        suite = Suite(
            name=name, kind=kind, description=s.get("description", ""),
            dir=_path(s["dir"], base, environment) if s.get("dir") else None,
            glob=s.get("glob", "*"), strip_suffix=s.get("strip_suffix", ""),
            include=_strs(s.get("include"), "include"), exclude=_strs(s.get("exclude"), "exclude"),
            configs=_strs(s.get("configs"), "configs"),
            seeds=positive_int(s.get("seeds", 1), f"{path} [suites.{name}] seeds"),
            max_cycles=s.get("max_cycles"), mem_latency=s.get("mem_latency"),
            timeout_s=s.get("timeout_s", 600), options=dict(s.get("options", {})),
            build_options=_strs(s.get("build_options"), "build_options"),
            cycles_key=s.get("cycles_key", "cycles"), instret_key=s.get("instret_key", "instret"),
            perf_metrics=_strs(s.get("perf_metrics"), "perf_metrics"),
        )
        unknown = [x for x in suite.configs if configs and x not in configs]
        if unknown:
            raise ConfigError(f"{path} [suites.{name}]: unknown configs {', '.join(unknown)}")
        cfg.suites[name] = suite
    for name, t in (raw.get("tiers") or {}).items():
        _check_keys(t, {"description", "runs"}, f"{path} [tiers.{name}]")
        runs = []
        for r in t.get("runs", []):
            _check_keys(r, {"suite", "configs", "include", "seeds"}, f"{path} [tiers.{name}] run")
            if r.get("suite") not in cfg.suites:
                raise ConfigError(f"{path} [tiers.{name}]: unknown suite {r.get('suite')!r}")
            runs.append(TierRun(suite=r["suite"], configs=_strs(r.get("configs"), "configs"),
                                include=_strs(r.get("include"), "include"),
                                seeds=positive_int(r.get("seeds"), f"{path} [tiers.{name}] run seeds",
                                                   optional=True)))
        cfg.tiers[name] = Tier(name=name, description=t.get("description", ""), runs=runs)
    return cfg
