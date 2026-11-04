"""Project selection and the small rvw.project/1 configuration contract."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
import tomllib

from .capture import Capture


class ProjectError(ValueError):
    pass


def find_project(project=None, *, start=None):
    """An explicit selection must exist. Discovery stops at the nearest rvw.toml."""
    selected = project if project is not None else os.environ.get("RVW_PROJECT")
    if selected is not None:
        path = Path(selected).expanduser().absolute()
        if path.is_dir():
            path /= "rvw.toml"
        if not path.is_file():
            raise ProjectError(f"no project file {path}")
        return path
    directory = Path(start or Path.cwd()).resolve()
    for parent in (directory, *directory.parents):
        path = parent / "rvw.toml"
        if path.exists() or path.is_symlink():
            if not path.is_file():
                raise ProjectError(f"project file is not a regular file: {path}")
            return path
    return None


def select_core(core=None, project=None):
    """Explicit legacy core selection bypasses discovery, but never an explicit project."""
    if core is not None:
        if project is not None:
            raise ProjectError("give --core or --project, not both")
        return str(core)
    path = find_project(project)
    return str(path) if path else os.environ.get("RVW_CORE")


@dataclass
class Project:
    path: Path
    root: Path
    name: str
    sections: dict
    capture: dict

    def get(self, section, key, default=None):
        return self.sections.get(section, {}).get(key, default)

    @property
    def inputs(self):
        return [value for section, keys in {
            "cosim": ("platform",), "debug": ("config",),
            "checks": ("settings", "waivers"),
        }.items() for key in keys if (value := self.get(section, key)) is not None]


def parse_project(raw, path, environment):
    # Use the existing path and environment rules of regression configs.
    from rvw.regress.config import _path, _cmd, _check_keys
    base = path.parent
    tables = {
        "project": {"schema", "root", "rvw_version"}, "cosim": {"platform"},
        "debug": {"config"}, "checks": {"settings", "waivers"},
        "query": {"build", "db"},
        "lint": {"settings"},
        "arch": {"description", "sources", "benchmarks"},
        "formal": {"verilog", "top", "checks", "clock", "reset", "export_dependencies"},
        "riscv_formal": {"root", "verilog", "wrapper", "isa", "nret", "checks", "depth", "solver", "defines", "ports"},
    }
    _check_keys(raw, {"core", "suites", "tiers", *tables}, str(path))
    sections = {}
    for section, allowed in tables.items():
        table = raw.get(section, {})
        if not isinstance(table, dict):
            raise ProjectError(f"{path}: [{section}] must be a table")
        _check_keys(table, allowed, f"{path} [{section}]")
        sections[section] = dict(table)
    if sections["project"].get("schema", "rvw.project/1") != "rvw.project/1":
        raise ProjectError(f"{path}: unsupported project schema")
    pin = sections["project"].get("rvw_version")
    if pin is not None:
        import rvw
        if not isinstance(pin, str) or pin != rvw.__version__:
            raise ProjectError(f"{path}: needs rvw {pin!r}; running {rvw.__version__}")
    core = raw.get("core", {})
    if not isinstance(core, dict) or not isinstance(core.get("name"), str) or not core["name"].strip():
        raise ProjectError(f"{path}: project needs [core] name")
    for section, table in sections.items():
        for key, value in list(table.items()):
            if section == "riscv_formal":
                if key in {"root", "wrapper"}:
                    if not isinstance(value, str) or not value:
                        raise ProjectError(f"riscv_formal.{key} must be a nonempty path")
                    table[key] = _path(value, base, environment)
                elif key == "verilog":
                    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
                        raise ProjectError("riscv_formal.verilog must be a nonempty path list")
                    table[key] = [_path(v, base, environment) for v in value]
                continue
            if key in {"schema", "rvw_version", "top", "clock", "reset"}:
                if not isinstance(value, str) or not value:
                    raise ProjectError(f"{section}.{key} must be a non-empty string")
            elif key in {"build", "verilog", "export_dependencies"}:
                if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
                    raise ProjectError(f"{section}.{key} must be a non-empty list of strings")
                table[key] = (_cmd(value, base, environment) if key == "build"
                              else [_path(v, base, environment) for v in value])
            else:
                if not isinstance(value, str) or not value:
                    raise ProjectError(f"{section}.{key} must be a non-empty path")
                table[key] = _path(value, base, environment)
    return Project(path, sections["project"].get("root", base), core["name"], sections, {})


def load_project(project=None, *, capture=None, core=None):
    if core is not None:
        if project is not None:
            raise ProjectError("give --core or --project, not both")
        return None
    path = find_project(project)
    if path is None:
        return None
    if capture is None:
        with tempfile.TemporaryDirectory(prefix="rvw-project-") as directory:
            return load_project(path, capture=Capture(Path(directory) / "inputs"))
    from rvw.regress.config import _ENV
    item = capture.file(path)
    text = item.copy.read_text()
    environment = capture.env("HOME", "RVW_PROJECT", *(m.group(1) for m in _ENV.finditer(text)))
    result = parse_project(tomllib.loads(text), Path(item.resolved), environment)
    result.capture = capture.record()
    return result


def database(db=None, project=None):
    if db is not None:
        return db, None
    selected = load_project(project)
    if selected and selected.get("query", "db") is None:
        raise ProjectError(f"{selected.path}: missing query.db")
    return (selected.get("query", "db"), selected.capture) if selected else (None, None)
