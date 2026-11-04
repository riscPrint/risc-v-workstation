"""Check a project-owned riscv-vector-tests ELF suite with complete V evidence."""
from argparse import Namespace
from pathlib import Path
import hashlib
import json


def check(elf_dir, results, platform_path, *, project=None):
    from rvw.common.project import load_project
    from rvw.cosim.platform import Platform
    from rvw.cosim.extensions import has_extension
    from rvw.cosim.cli import calculate
    from rvw.results import load_run
    selected = load_project(project) if project or not platform_path else None
    platform_path = platform_path or (selected.get('cosim', 'platform') if selected else None)
    if platform_path is None:
        raise ValueError('select a project with cosim.platform or give --platform')
    platform = Platform.load('reference', platform_path)
    if not has_extension(platform.isa, 'v'):
        raise ValueError('riscv-vector-tests requires a platform declaring V')
    elfs = sorted(p for p in Path(elf_dir).iterdir() if p.is_file() and p.read_bytes()[:4] == b'\x7fELF')
    if not elfs:
        raise ValueError('no ELF tests in suite directory')
    runs = [load_run(p) for p in Path(results).rglob('result.json')]
    rows = []
    for elf in elfs:
        digest = hashlib.sha256(elf.read_bytes()).hexdigest()
        candidates = [r for r in runs if r.elf_sha256 == digest]
        status, reason, comparison = 'inconclusive', 'need exactly one C1 result per ELF', None
        if len(candidates) == 1:
            run = candidates[0]
            reason = run.why_inconclusive
            if not reason and run.status != 'pass':
                status, reason = 'fail', 'C1 self-check failed: '+run.status
            elif not reason:
                trace = run.artifacts.get('rvfi_trace')
                if not trace:
                    reason = 'missing C2 trace'
                else:
                    args = Namespace(cosim_action='check', core='reference', platform=Path(platform_path),
                        elf=elf, trace=run.path / trace, model='spike', history=10,
                        strict=True, strict_sync=(), sail_config=None, timeout=120)
                    comparison, code = calculate(args)
                    reason = 'need complete strict vector state match and passing termination'
                    if comparison.get('status') == 'mismatch':
                        status, reason = 'fail', 'architectural mismatch'
                    elif (code == 0 and comparison.get('status') == 'match'
                          and comparison.get('trace_complete') is True
                          and comparison.get('end_status') == 'pass'
                          and comparison.get('instructions', 0) > 0
                          and comparison['instructions'] == run.instret
                          and comparison.get('synchronized') == 0
                          and comparison.get('state_coverage', {}).get('vector')):
                        status, reason = 'pass', None
        rows.append(dict(id=elf.name, elf_sha256=digest, status=status, reason=reason, comparison=comparison))
    return dict(schema='rvw.vector-check/1',
        status='fail' if any(r['status'] == 'fail' for r in rows) else 'pass' if all(r['status'] == 'pass' for r in rows) else 'inconclusive',
        tests=rows)


def register(sub):
    cmd = sub.add_parser('vector', help='check riscv-vector-tests C1 runs with complete Spike V state')
    cmd.add_argument('--elf-dir', required=True, type=Path)
    cmd.add_argument('--results', required=True, type=Path)
    cmd.add_argument('--platform', type=Path)
    cmd.add_argument('--json', action='store_true')
    cmd.set_defaults(func=run)


def run(args):
    try:
        result = check(args.elf_dir, args.results, args.platform, project=getattr(args, 'project', None))
        code = {'pass': 0, 'fail': 1, 'inconclusive': 3}[result['status']]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result, code = dict(status='error', message=str(exc)), 2
    print(json.dumps(result))
    return code
