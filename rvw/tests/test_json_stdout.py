"""`--json` contract: stdout is exactly one JSON document, or empty on error.

Round 14 found progress lines (`[bundle] ...`, `[reduce] ...`, `[bisect] ...`) on stdout under
`--json`, and CLIs that streamed `json.dump` to stdout, so a value JSON cannot encode left half a
document there. Human messages go to stderr; the document is serialized fully before it is written.
"""
import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from rvw.cli import build_parser, main
from rvw.common.proc import run_group
from test_debug_tools import CFG, FAKE, fake_run, make_core


def strict_json(text: str):
    """Parse one strict JSON document (no NaN/Infinity, nothing after it)."""
    def bad_constant(name):
        raise ValueError(f"not JSON: {name}")
    return json.loads(text, parse_constant=bad_constant)


def assert_one_document_or_empty(stdout: str, what: str):
    if stdout.strip() == "":
        return None
    try:
        return strict_json(stdout)
    except ValueError as e:
        raise AssertionError(f"{what}: stdout is not one JSON document ({e}):\n{stdout[:2000]}") from None


# --- every subcommand that accepts --json ----------------------------------------------------

def json_commands(parser: argparse.ArgumentParser, path=()):
    """(command path, parser) for every leaf of the rvw argparse tree that has a --json option."""
    if hasattr(parser, "load"):
        parser.load()
    seen = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                if id(sub) in seen:        # aliases
                    continue
                seen.add(id(sub))
                yield from json_commands(sub, path + (name,))
    requires_child = any(isinstance(a, argparse._SubParsersAction) and a.required
                         for a in parser._actions)
    if "--json" in parser._option_string_actions and not requires_child:
        yield path, parser


def _value(action, tmp: Path) -> str:
    if action.choices:
        return str(next(iter(action.choices)))
    value = str(tmp / f"missing-{action.dest}")
    if action.type is not None:
        try:
            action.type(value)
        except (ValueError, TypeError, argparse.ArgumentTypeError):
            value = "1"
            action.type(value)
    return value


def probe_argv(path, parser, tmp: Path) -> list[str]:
    """Arguments that get past argparse: required positionals and options get a missing path (or a
    number, or the first choice), so the command runs its error path."""
    argv = list(path)
    def values(action):
        count = action.nargs if isinstance(action.nargs, int) else 1
        return [_value(action, tmp)] * count
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)) \
                or "--json" in action.option_strings:
            continue
        if not action.option_strings:
            if action.nargs in ("?", "*"):
                continue
            argv.extend(values(action))
        elif action.required:
            argv.append(action.option_strings[-1])
            if action.nargs != 0:
                argv.extend(values(action))
    for group in parser._mutually_exclusive_groups:
        if group.required and not any(a.option_strings[-1] in argv for a in group._group_actions):
            a = group._group_actions[0]
            argv += [a.option_strings[-1]] + values(a)
    return argv + ["--json"]


# Extra arguments a command needs so the probe runs it as a one-shot command.
EXTRA = {("mcp",): ["--list"],
         # Exercise input errors, without starting native builds or downloading sources.
         ("agent", "bringup-check"): ["--out", "."],
         ("regress", "uvm"): ["--archive", "missing-archive.tar.gz"]}     # without --list, `rvw mcp` starts the stdio server

COMMANDS = sorted(json_commands(build_parser()), key=lambda c: c[0])


@pytest.mark.fast
def test_probe_arguments_reach_handlers():
    parser = build_parser()
    for path, command in COMMANDS:
        parser.parse_args(probe_argv(path, command, Path("missing-inputs")) + EXTRA.get(path, []))


@pytest.mark.fast
def test_the_probe_sees_the_known_json_commands():
    names = {" ".join(p) for p, _ in COMMANDS}
    for expected in ("bundle", "reduce", "bisect", "wave sample", "cov report", "regress run",
                     "regress known list", "cosim check", "formal bmc", "perf", "mcp"):
        assert expected in names, (expected, sorted(names))


@pytest.mark.parametrize("path,parser", COMMANDS, ids=[" ".join(p) for p, _ in COMMANDS])
def test_every_json_command_writes_one_document_or_nothing(path, parser, tmp_path):
    argv = probe_argv(path, parser, tmp_path) + EXTRA.get(path, [])
    env = {**os.environ, "RVW_NO_LOCK": "1", "RVW_RESULTS": str(tmp_path / "results"),
           "RVW_LOCK_DIR": str(tmp_path / "locks"), "HOME": str(tmp_path / "home")}
    env.pop("RVW_CORE", None)
    p = run_group([sys.executable, "-m", "rvw", *argv], capture=True, env=env,
                  input=b"", timeout=60, cwd=tmp_path)
    assert not p.timed_out, (argv, p.stderr)
    # The probe must reach the command, not stop in argparse.
    assert "usage:" not in p.stderr, (argv, p.stderr)
    assert_one_document_or_empty(p.stdout, " ".join(argv))


# --- bundle / reduce / bisect on a real (fake-adapter) failure --------------------------------

@pytest.fixture
def debug_env(tmp_path):
    cfg = tmp_path / "debug.toml"
    cfg.write_text(CFG)
    return {**os.environ, "RVW_NO_LOCK": "1", "RVW_CORE_CONFIG": str(cfg)}


def rvw_json(args, env):
    p = subprocess.run([sys.executable, "-m", "rvw", *map(str, args), "--json"], capture_output=True,
                       text=True, env=env, stdin=subprocess.DEVNULL, timeout=600)
    data = assert_one_document_or_empty(p.stdout, " ".join(map(str, args)))
    return p, data


def test_bundle_json_stdout_is_one_document(tmp_path, monkeypatch, debug_env):
    monkeypatch.setenv("RVW_CORE_CONFIG", debug_env["RVW_CORE_CONFIG"])
    run = fake_run(tmp_path / "r", "--seed", "9")
    p, S = rvw_json(["bundle", run, "--out", tmp_path / "b", "--rerun-window", "300", "--cut-cycles", "50"],
                    debug_env)
    assert p.returncode == 0, p.stderr
    assert S["signature"] == "assert:lsu.scala:1241"
    assert "[bundle]" in p.stderr          # progress still shown, on stderr


def test_reduce_json_stdout_is_one_document(tmp_path, debug_env):
    run = fake_run(tmp_path / "r", "--seed", "9")
    p, r = rvw_json(["reduce", run, "--out", tmp_path / "red", "--seeds", "2", "--latencies", "1"], debug_env)
    assert p.returncode == 0, p.stderr
    assert r["reproduced"] and "[reduce]" in p.stderr


def _noisy_git(tmp_path: Path) -> dict:
    """A `git` on PATH that writes to stdout on `git clone` (as hooks or some versions can)."""
    real = subprocess.run(["which", "git"], capture_output=True, text=True, check=True).stdout.strip()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    g = bin_dir / "git"
    g.write_text(f'#!/bin/sh\nif [ "$1" = clone ]; then echo "Cloning into somewhere..."; fi\nexec {real} "$@"\n')
    g.chmod(g.stat().st_mode | stat.S_IEXEC)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def test_bisect_json_stdout_is_one_document(tmp_path, debug_env):
    repo, _ = make_core(tmp_path)
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    env = {**debug_env, **_noisy_git(tmp_path)}
    p, r = rvw_json(["bisect", run, "--good", "HEAD~7", "--core-repo", repo, "--workdir", tmp_path / "bis"], env)
    assert p.returncode == 0, p.stderr
    assert r["result"]["commit"].endswith("change 5") and "[bisect]" in p.stderr


# --- values JSON cannot encode: nothing partial on stdout --------------------------------------

def _main(capsys, argv):
    capsys.readouterr()
    try:
        code = main(argv)
    except Exception as e:      # before the fix some of these escaped as tracebacks
        code = e
    return code, capsys.readouterr()


@pytest.mark.parametrize("cmd", ["bundle", "reduce", "bisect"])
def test_debug_commands_never_write_a_partial_or_invalid_document(cmd, capsys, monkeypatch):
    bad = {"signature": "s", "suspect": {"unit": "u"}, "out": "o", "reproduced": True,
           "best": {"cycles": 1, "seed": 1, "mem_latency": 1, "replay": "r"}, "workdir": "w",
           "result": {"first_bad": "x", "commit": "c"}, "value": float("nan"), "obj": object()}
    monkeypatch.setattr(f"rvw.{cmd}.cli.execute_json", lambda *a, **k: bad)
    argv = [cmd, "run"] + (["--good", "g"] if cmd == "bisect" else []) + ["--json"]
    code, out = _main(capsys, argv)
    assert out.out == "" and code == 2, (code, out.out[:300])
    assert "JSON" in out.err


def test_wave_never_writes_a_partial_document(capsys, monkeypatch):
    monkeypatch.setattr("rvw.wave.ops.sample", lambda *a, **k: {"TOP.x": object()})
    code, out = _main(capsys, ["wave", "sample", "w.vcd", "x", "--at", "5", "--json"])
    assert out.out == "" and code == 2, (code, out.out[:300])


def test_regress_never_writes_a_partial_document(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr("rvw.regress.cli.read_index",
                        lambda: [{"run_id": "r1", "path": str(tmp_path), "bad": object()}])
    code, out = _main(capsys, ["regress", "history", "--json"])
    assert out.out == "" and code == 2, (code, out.out[:300])


def test_cov_writes_one_error_document_when_the_result_cannot_be_encoded(capsys, monkeypatch):
    monkeypatch.setattr("rvw.cov.cli.calculate",
                        lambda args: {"schema": "rvw.coverage-x/1", "points": [], "bad": float("inf")})
    code, out = _main(capsys, ["cov", "report", "db.json", "--json"])
    assert code == 2
    assert strict_json(out.out)["schema"] == "rvw.coverage-error/1"


def test_json_fallback_keeps_a_finding_status_on_exit_1(capsys):
    from types import SimpleNamespace
    from rvw.common.cli_json import execute
    def finding(_):
        print(json.dumps({"status": "violation", "findings": [{"sink": "dbus_addr"}]}))
        return 1
    def failed_text(_):
        print("something broke")
        return 1
    assert execute(finding, SimpleNamespace(command="sec")) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "violation" and out["verdict"] == "fail" and "code" not in out
    assert execute(failed_text, SimpleNamespace(command="x")) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error" and out["code"] == "command_failed"
