"""Native negative binding test. Set VEXRISCV to a private checkout."""
import json
import os
from pathlib import Path
import shutil
import sys

import pytest
from rvw.common.proc import run_group
from rvw.cli import main


def test_native_decode_branch_probe_is_named(tmp_path, capsys):
    core = os.environ.get("VEXRISCV")
    if not core:
        pytest.skip("needs private VEXRISCV and native tools")
    repo = Path(os.environ["RVW_HOME"]) if os.environ.get("RVW_HOME") else Path(__file__).resolve().parents[4]
    source = repo / "examples/vexriscv/rvw"
    project = tmp_path / "project/rvw"
    shutil.copytree(source, project, ignore=shutil.ignore_patterns("out", "target", ".bsp"))
    plugin = project / "src/main/scala/rvwvex/ProbePlugin.scala"
    old = "Probe.branch(\"vex_static\", retire && isBranch, wb.input(PC), taken,"
    new = "Probe.branch(\"misplaced_decode_branch\", decode.arbitration.isFiring && decode.input(BRANCH_CTRL) =/= BranchCtrlEnum.INC, decode.input(PC), taken,"
    text = plugin.read_text()
    assert old in text
    plugin.write_text(text.replace(old, new))
    run = tmp_path / "run"
    env = dict(os.environ, RVW_HOME=str(repo), RVW_VEX_LOCK="vex-csims", RVW_SBT_LOCK="sbt-csims",
               RVW_NICE="15", RISCVSIM_MAKE_JOBS="2", RISCVSIM_WORK=str(tmp_path / "work"),
               RVW_PYTHON=sys.executable, RVW_LOCK_PYTHON=sys.executable)
    result = run_group(["nice", "-n", "15", str(project / "run.sh"), "run", "--elf",
                    str(source / "out/programs/branches"), "--out", str(run), "--config", "rv32im",
                    "--rvfi-trace", "--probes", "--seed", "7", "--mem-latency", "0", "--json"],
                   cwd=repo, env=env, timeout=600, capture=True)
    assert result.returncode == 0, (result.stdout or "")[-8000:]
    code = main(["probes", "check", "--events", str(run / "probe-events.jsonl"),
                 "--validate", "--c2", str(run / "rvfi.jsonl"), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report["status"] == "violations"
    report = report["stream"]
    assert any(f["probe"] == "branch/misplaced_decode_branch" and f["check"] == "c2"
               for f in report["findings"])
