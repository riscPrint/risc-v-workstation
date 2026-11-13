"""Bounded riscv-formal runner. Core wrappers belong to the selected project."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys
import time
from datetime import datetime, timezone

from rvw.common.proc import Result, run_group
from rvw.common.project import load_project
from rvw.results.schema import SuiteResults, TestEntry, Verdict, write_json
from rvw.formal.common import sigterm_raises


FIELDS = "valid order insn trap halt intr mode ixl rs1_addr rs2_addr rs1_rdata rs2_rdata rd_addr rd_wdata pc_rdata pc_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata".split()


MEM_FAULT_FIELDS = "mem_fault mem_fault_rmask mem_fault_wmask".split()


def validate(cfg):
    required = {"root", "wrapper", "verilog", "isa", "nret", "checks", "depth", "solver", "ports"}
    if required - cfg.keys():
        raise ValueError(f"[riscv_formal] needs {sorted(required - cfg.keys())}")
    if not isinstance(cfg["isa"], str) or cfg["isa"] not in {f"rv{x}{e}" for x in (32, 64) for e in ("i", "im", "ic", "imc")}:
        raise ValueError("unsupported ISA: only RV32/64 I, IM, IC, IMC")
    if type(cfg["nret"]) is not int or not 1 <= cfg["nret"] <= 16:
        raise ValueError("unsupported NRET: expected 1..16 retirement channels")
    if type(cfg["depth"]) is not int or not 2 <= cfg["depth"] <= 200:
        raise ValueError("depth must be 2..200")
    if not isinstance(cfg["solver"], str) or cfg["solver"] not in {"bitwuzla", "yices", "z3", "boolector"}:
        raise ValueError("unsupported solver")
    if type(cfg.get("multiclock", False)) is not bool:
        raise ValueError("multiclock must be a boolean")
    checks = cfg["checks"]
    if not isinstance(checks, list) or not checks or not all(isinstance(c, str) for c in checks) or len(set(checks)) != len(checks):
        raise ValueError("checks must be a nonempty unique list")
    for check in checks:
        if not isinstance(check, str) or not re.fullmatch(r"(?:(?:insn_[a-z0-9_]+|reg|pc_fwd|pc_bwd|liveness|causal|unique)_ch[0-9]+|cover)", check):
            raise ValueError(f"unsupported check {check!r}")
        if check != 'cover' and int(check.rsplit('_ch', 1)[1]) >= cfg['nret']:
            raise ValueError('check channel exceeds NRET')
    if "cover" not in checks:
        raise ValueError("checks must include cover to test retirement reachability")
    options = cfg.get('check_options', {})
    if not isinstance(options, dict) or set(options) - set(checks):
        raise ValueError("check_options must name requested checks")
    for name in checks:
        opt = options.get(name, {})
        if not isinstance(opt, dict) or set(opt) - {'cycles', 'engine', 'defines'}:
            raise ValueError("check_options supports cycles, engine and defines")
        settings = check_settings(cfg, name)
        cycles = settings['cycles']
        count = 1 if name.startswith('insn_') else 3 if name.startswith(('unique_', 'liveness_')) else 2
        if (not isinstance(cycles, list) or len(cycles) != count or
            any(type(c) is not int or not 1 <= c <= 200 for c in cycles) or
            cycles != sorted(set(cycles))):
            raise ValueError(f"invalid cycles for {name}")
        if not isinstance(settings['engine'], str) or settings['engine'] not in {'abc bmc3', 'btor btormc', 'smtbmc bitwuzla', 'smtbmc yices', 'smtbmc z3', 'smtbmc boolector'}:
            raise ValueError("unsupported engine")
        if name == 'cover' and not settings['engine'].startswith('smtbmc '):
            raise ValueError("cover needs an smtbmc engine")
        if not isinstance(settings['defines'], list) or any(not isinstance(d, str) or '\n' in d or '\r' in d for d in settings['defines']):
            raise ValueError("check defines must be single-line strings")
    ports = cfg['ports']
    if not isinstance(ports, dict) or set(ports) not in (set(FIELDS), set(FIELDS + MEM_FAULT_FIELDS)):
        raise ValueError("ports must map every RVFI field and optionally the complete mem_fault group")
    if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', v) for v in ports.values()) or len(set(ports.values())) != len(ports):
        raise ValueError("RVFI ports must be distinct Verilog identifiers")
    if Path(cfg['wrapper']).read_text().count('@RVFI_CONNECTIONS@') != 1:
        raise ValueError("wrapper must contain one @RVFI_CONNECTIONS@ placeholder")
    from .isa_memory import render
    environment = render(cfg)
    if environment and Path(cfg["wrapper"]).read_text().count("@MEMORY_ENVIRONMENT@") != 1:
        raise ValueError("memory contract needs one @MEMORY_ENVIRONMENT@ placeholder")
    defines = cfg.get("defines", [])
    if not isinstance(defines, list) or any(not isinstance(d, str) or '\n' in d or '\r' in d for d in defines):
        raise ValueError("defines must be single-line strings")
    files = cfg['verilog']
    if not isinstance(files, list) or not files:
        raise ValueError("verilog must be a nonempty path list")
    for path in [cfg['wrapper'], *files]:
        if not Path(path).is_file():
            raise ValueError(f"missing input {path}")
    models = cfg.get('instruction_models', {})
    if not isinstance(models, dict) or any(not isinstance(k, str) or not re.fullmatch(r'[a-z0-9_]+', k) or not isinstance(v, (str, Path)) or not Path(v).is_file() for k,v in models.items()):
        raise ValueError('instruction_models must map instruction names to existing files')
    root = Path(cfg['root'])
    for directory in ('checks', 'insns'):
        if not (root / directory).is_dir():
            raise ValueError(f"missing riscv-formal {directory}")


def check_settings(cfg, name):
    depth = cfg['depth']
    cycles = [depth] if name.startswith('insn_') else [1, 2, depth] if name.startswith(('unique_', 'liveness_')) else [1, depth]
    return dict(cycles=cycles, engine=f"smtbmc {cfg['solver']}", defines=[]) | cfg.get('check_options', {}).get(name, {})


def prepare(cfg, out):
    """Copy inputs into a private riscv-formal tree. Never write into the source tree."""
    validate(cfg)
    if out.exists():
        raise ValueError("--out must not exist; use a new directory for each run")
    root = out / 'riscv-formal'
    identity = {}
    snapshots = {}
    identity['settings_sha256'] = hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()
    for directory in ('checks', 'insns'):
        shutil.copytree(Path(cfg['root']) / directory, root / directory,
                        ignore=shutil.ignore_patterns('__pycache__'))
    for path in sorted(root.rglob('*')):
        if path.is_file():
            snapshots[str(Path(cfg['root']) / path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    core = root / 'cores' / 'project'
    core.mkdir(parents=True)
    for i, src in enumerate([cfg['wrapper'], *cfg['verilog']]):
        dest = core / ('wrapper.sv' if i == 0 else f'design{i}.sv')
        shutil.copyfile(src, dest)
        snapshots[str(src)] = hashlib.sha256(dest.read_bytes()).hexdigest()
        if i == 0:
            from .isa_memory import render
            environment = render(cfg)
            text = dest.read_text()
            if environment:
                if text.count("@MEMORY_ENVIRONMENT@") != 1:
                    raise ValueError("memory contract needs one @MEMORY_ENVIRONMENT@ placeholder")
                text = text.replace("@MEMORY_ENVIRONMENT@", environment)
            else:
                text = text.replace("@MEMORY_ENVIRONMENT@", "")
            dest.write_text(text.replace('@RVFI_CONNECTIONS@', ',\n'.join(
                f'.{cfg["ports"][field]} (rvfi_{field})' for field in cfg["ports"])))
        identity[str(src)] = hashlib.sha256(dest.read_bytes()).hexdigest()
    for insn, src in cfg.get('instruction_models', {}).items():
        dest = root / 'insns' / f'insn_{insn}.v'
        if not dest.is_file():
            if not any(re.fullmatch(r'insn_' + re.escape(insn) + r'_ch[0-9]+', check) for check in cfg['checks']):
                raise ValueError(f'new instruction model must have a requested check: {insn}')
            isa_list = root / 'insns' / f"isa_{cfg['isa']}.txt"
            if not isa_list.is_file():
                raise ValueError('missing upstream ISA instruction list')
            isa_list.write_text(isa_list.read_text().rstrip() + '\n' + insn + '\n')
            identity.setdefault('instruction_set_additions', []).append(insn)
        shutil.copyfile(src, dest)
        snapshots.pop(str(Path(cfg['root']) / 'insns' / f'insn_{insn}.v'), None)
        snapshots[str(src)] = hashlib.sha256(dest.read_bytes()).hexdigest()
        identity[str(src)] = hashlib.sha256(dest.read_bytes()).hexdigest()
    # Include the actual checker bytes, including uncommitted changes.
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    identity['checker_sha256'] = digest.hexdigest()
    from .input_identity import committed_inputs
    identity['committed_inputs'] = committed_inputs(snapshots)
    verilog = '\n'.join('@basedir@/cores/@core@/' + p.name for p in sorted(core.glob('*.sv')))
    depth_lines = '\n'.join(name + ' ' + ' '.join(map(str, check_settings(cfg, name)['cycles'])) for name in cfg['checks'])
    # Exact check names avoid accidentally enabling other upstream checks.
    (core / 'checks.cfg').write_text(
        f"[options]\nisa {cfg['isa']}\nnret {cfg['nret']}\nsolver {cfg['solver']}\n"
        f"[depth]\n{depth_lines}\n"
        '[defines]\n' + '\n'.join(cfg.get('defines', []) +
            (['`define RISCV_FORMAL_MEM_FAULT'] if 'mem_fault' in cfg['ports'] else [])) + '\n'
        f'[verilog-files]\n{verilog}\n'
        '[cover]\n' + ''.join(f'always @* if (!reset) cover (channel[{i}].cnt_insns > 0);\n' for i in range(cfg['nret'])))
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
    from .runtime import load_average, timeout_details
    cfg = json.loads(json.dumps(cfg, default=str))
    core, identity = prepare(cfg, out)
    entries = []
    generation_start = time.monotonic()
    generation_load = load_average()
    with (out / 'generate.log').open('w') as log:
        gen = invoke([sys.executable, '../../checks/genchecks.py'], cwd=core,
                        timeout=timeout, stdout=log, stderr=log)
    generation_wall = time.monotonic() - generation_start
    for name in cfg['checks']:
        started = time.monotonic()
        load_start = load_average()
        work = core / 'checks'
        file = work / f'{name}.sby'
        if gen.returncode or not file.is_file():
            entry = map_check(name, '', gen.returncode or 2, gen.timed_out)
        else:
            settings = check_settings(cfg, name)
            source = file.read_text()
            if cfg.get('multiclock'):
                source = re.sub(r'(?m)^\[options\]$', '[options]\nmulticlock on', source, count=1)
            if settings['defines']:
                source = source.replace('[file defines.sv]\n', '[file defines.sv]\n' + '\n'.join(settings['defines']) + '\n', 1)
            source = re.sub(r'(?m)^(\[engines\]\n)[^\n]+', lambda m: m[1] + settings['engine'], source)
            if settings['engine'] == 'abc bmc3':
                source = re.sub(r'(?m)^skip [^\n]+\n', '', source)
            file.write_text(source)
            with (out / f'{name}.log').open('w') as log:
                result = invoke(['sby', '-f', file.name], cwd=work,
                                   timeout=timeout, stdout=log, stderr=log)
            status = work / name / 'status'
            tokens = status.read_text().split() if status.is_file() else []
            token = tokens[0] if tokens else ''
            entry = map_check(name, token, result.returncode, result.timed_out)
        entry.extra['formal_settings'] = check_settings(cfg, name)
        entry.extra['wall_s'] = time.monotonic() - started
        if gen.timed_out:
            entry.extra['wall_s'] = generation_wall
            load_start = generation_load
            entry.extra['timeout_phase'] = 'generation'
        entry.extra['timeout_s'] = timeout
        entry.extra['load_average_start'] = load_start
        if entry.status == 'timeout':
            entry.extra.update(timeout_details(entry.extra['wall_s'], timeout, load_start,
                                               engine=entry.extra['formal_settings']['engine']))
        entries.append(entry)
    covered = next(t for t in entries if t.id == 'cover').status == 'pass'
    for entry in entries:
        if entry.status == 'pass' and entry.id != 'cover' and not covered:
            entry.extra['inconclusive'] = 'retirement cover was not reached; bounded check may be vacuous'
    suite = SuiteResults(out.name, 'riscv-formal', core_name, cfg['isa'],
                         datetime.now(timezone.utc).isoformat(),
                         source={'identity_complete': False, 'formal_inputs': identity}, tests=entries,
                         extra={'bounded_depth': max(check_settings(cfg, name)['cycles'][-1] for name in cfg['checks']), 'settings': cfg})
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
