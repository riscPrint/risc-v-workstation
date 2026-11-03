"""Bounded riscv-formal runner. Core wrappers belong to the selected project."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime, timezone

from rvw.common.proc import Result, run_group
from rvw.common.project import load_project
from rvw.results.schema import SuiteResults, TestEntry, Verdict, write_json
from rvw.formal.common import sigterm_raises


FIELDS = "valid order insn trap halt intr mode ixl rs1_addr rs2_addr rs1_rdata rs2_rdata rd_addr rd_wdata pc_rdata pc_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata".split()


def validate(cfg):
    required = {"root", "wrapper", "verilog", "isa", "nret", "checks", "depth", "solver", "ports"}
    if required - cfg.keys():
        raise ValueError(f"[riscv_formal] needs {sorted(required - cfg.keys())}")
    if not isinstance(cfg["isa"], str) or cfg["isa"] not in {f"rv{x}{e}" for x in (32, 64) for e in ("i", "im", "ic", "imc")}:
        raise ValueError("unsupported ISA: only RV32/64 I, IM, IC, IMC")
    if type(cfg["nret"]) is not int or cfg["nret"] != 1:
        raise ValueError("unsupported NRET: this increment supports one retirement channel")
    if type(cfg["depth"]) is not int or not 2 <= cfg["depth"] <= 200:
        raise ValueError("depth must be 2..200")
    if not isinstance(cfg["solver"], str) or cfg["solver"] not in {"bitwuzla", "yices", "z3", "boolector"}:
        raise ValueError("unsupported solver")
    checks = cfg["checks"]
    if not isinstance(checks, list) or not checks or not all(isinstance(c, str) for c in checks) or len(set(checks)) != len(checks):
        raise ValueError("checks must be a nonempty unique list")
    for check in checks:
        if not isinstance(check, str) or not re.fullmatch(r"(?:(?:insn_[a-z0-9_]+|reg|pc_fwd|pc_bwd|causal|unique)_ch0|cover)", check):
            raise ValueError(f"unsupported check {check!r}")
    if "cover" not in checks:
        raise ValueError("checks must include cover to test retirement reachability")
    ports = cfg['ports']
    if not isinstance(ports, dict) or set(ports) != set(FIELDS):
        raise ValueError("ports must map every RVFI field exactly once")
    if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', v) for v in ports.values()) or len(set(ports.values())) != len(ports):
        raise ValueError("RVFI ports must be distinct Verilog identifiers")
    if Path(cfg['wrapper']).read_text().count('@RVFI_CONNECTIONS@') != 1:
        raise ValueError("wrapper must contain one @RVFI_CONNECTIONS@ placeholder")
    defines = cfg.get("defines", [])
    if not isinstance(defines, list) or any(not isinstance(d, str) or '\n' in d or '\r' in d for d in defines):
        raise ValueError("defines must be single-line strings")
    files = cfg['verilog']
    if not isinstance(files, list) or not files:
        raise ValueError("verilog must be a nonempty path list")
    for path in [cfg['wrapper'], *files]:
        if not Path(path).is_file():
            raise ValueError(f"missing input {path}")
    root = Path(cfg['root'])
    for directory in ('checks', 'insns'):
        if not (root / directory).is_dir():
            raise ValueError(f"missing riscv-formal {directory}")


def prepare(cfg, out):
    """Copy inputs into a private riscv-formal tree. Never write into the source tree."""
    validate(cfg)
    if out.exists():
        raise ValueError("--out must not exist; use a new directory for each run")
    root = out / 'riscv-formal'
    identity = {}
    for directory in ('checks', 'insns'):
        shutil.copytree(Path(cfg['root']) / directory, root / directory,
                        ignore=shutil.ignore_patterns('__pycache__'))
    core = root / 'cores' / 'project'
    core.mkdir(parents=True)
    for i, src in enumerate([cfg['wrapper'], *cfg['verilog']]):
        dest = core / ('wrapper.sv' if i == 0 else f'design{i}.sv')
        shutil.copyfile(src, dest)
        if i == 0:
            dest.write_text(dest.read_text().replace('@RVFI_CONNECTIONS@', ',\n'.join(
                f'.{cfg["ports"][field]} (rvfi_{field})' for field in FIELDS)))
        identity[str(src)] = hashlib.sha256(dest.read_bytes()).hexdigest()
    # Include the actual checker bytes, including uncommitted changes.
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    identity['checker_sha256'] = digest.hexdigest()
    verilog = '\n'.join('@basedir@/cores/@core@/' + p.name for p in sorted(core.glob('*.sv')))
    depth = cfg['depth']
    (core / 'checks.cfg').write_text(
        f"[options]\nisa {cfg['isa']}\nnret 1\nsolver {cfg['solver']}\n"
        f"[depth]\ninsn {depth}\nreg 1 {depth}\npc_fwd 1 {depth}\npc_bwd 1 {depth}\n"
        f"causal 1 {depth}\nunique 1 2 {depth}\ncover 1 {depth}\n"
        '[defines]\n' + '\n'.join(cfg.get('defines', [])) + '\n'
        f'[verilog-files]\n{verilog}\n'
        '[cover]\nalways @* if (!reset) cover (channel[0].cnt_insns > 0);\n')
    return core, identity


def map_check(name, token, rc, timed_out):
    # SBY may expect FAIL and return 0. PASS needs a successful process.
    if timed_out:
        status, why = 'timeout', 'wall-clock timeout'
    elif token == 'PASS' and rc == 0:
        status, why = 'pass', None
    elif token == 'FAIL' and name != 'cover':
        status, why = 'fail', None
    else:
        status, why = 'error', 'missing, unreachable or unsuccessful check evidence'
    return TestEntry(name, status, signature=None if status == 'pass' else f'riscv-formal:{name}:{status}',
                     extra={'inconclusive': why} if why else {})


def invoke(argv, **kwargs):
    try:
        return run_group(argv, **kwargs)
    except OSError as exc:
        kwargs['stdout'].write(str(exc) + '\n')
        return Result(127)


def run(cfg, out, timeout, core_name):
    cfg = json.loads(json.dumps(cfg, default=str))
    core, identity = prepare(cfg, out)
    entries = []
    with (out / 'generate.log').open('w') as log:
        gen = invoke([sys.executable, '../../checks/genchecks.py'], cwd=core,
                        timeout=timeout, stdout=log, stderr=log)
    for name in cfg['checks']:
        work = core / 'checks'
        file = work / f'{name}.sby'
        if gen.returncode or not file.is_file():
            entry = map_check(name, '', gen.returncode or 2, gen.timed_out)
        else:
            with (out / f'{name}.log').open('w') as log:
                result = invoke(['sby', '-f', file.name], cwd=work,
                                   timeout=timeout, stdout=log, stderr=log)
            status = work / name / 'status'
            tokens = status.read_text().split() if status.is_file() else []
            token = tokens[0] if tokens else ''
            entry = map_check(name, token, result.returncode, result.timed_out)
        entries.append(entry)
    covered = next(t for t in entries if t.id == 'cover').status == 'pass'
    for entry in entries:
        if entry.status == 'pass' and entry.id != 'cover' and not covered:
            entry.extra['inconclusive'] = 'retirement cover was not reached; bounded check may be vacuous'
    suite = SuiteResults(out.name, 'riscv-formal', core_name, cfg['isa'],
                         datetime.now(timezone.utc).isoformat(),
                         source={'identity_complete': False, 'formal_inputs': identity}, tests=entries,
                         extra={'bounded_depth': cfg['depth'], 'settings': cfg})
    write_json(out / 'results.json', suite.to_dict())
    failed = any(t.status == 'fail' for t in entries)
    complete = all(t.status == 'pass' and t.conclusive for t in entries)
    verdict = Verdict('reject' if failed else 'inconclusive', tests='fail' if failed else 'pass' if complete else 'incomplete',
                      reasons=['Bounded checks only. Adapter conformance and committed gate identity are not established.'])
    write_json(out / 'verdict.json', verdict.to_dict())
    return verdict


def main(args):
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError('timeout must be positive and finite')
        project = load_project(getattr(args, 'project', None))
        if project is None:
            raise ValueError('riscv-formal requires a selected rvw.toml')
        cfg = project.sections['riscv_formal']
        with sigterm_raises():
            verdict = run(cfg, Path(args.out).absolute(), args.timeout, project.name)
        print(json.dumps(verdict.to_dict()) if args.json else verdict.verdict)
        return verdict.exit_code
    except (ValueError, OSError) as exc:
        print(f'riscv-formal: {exc}', file=sys.stderr)
        return 2
