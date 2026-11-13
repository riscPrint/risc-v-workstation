"""Conservative cell-output cuts on pinned compiled problems.

This keeps the original constraints. Failures of variants are not DUT failures.
"""
from pathlib import Path
from hashlib import sha256
from rvw.common.proc import run_group

KINDS = {'ram': ['$mem_v2', '$memrd', '$memrd_v2'],
         'counter': ['$add'], 'cut-points': ['$dff', '$dffe', '$sdff', '$sdffe']}


def script(kind):
    if kind not in KINDS:
        raise ValueError('unknown compiled abstraction')
    return 'cutpoint ' + ' '.join('t:' + t for t in KINDS[kind])


def build(source, top, out, kind, timeout=10):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'source.il').write_bytes(Path(source).read_bytes())
    commands = 'read_rtlil source.il; hierarchy -top ' + top + '; ' + script(kind) + '; write_rtlil abstract.il'
    result = run_group(['yosys', '-Q', '-T', '-p', commands], cwd=out, capture=True, timeout=timeout)
    text = (result.stdout or '') + (result.stderr or '')
    (out/'transform.log').write_text(text)
    if result.returncode or result.timed_out:
        raise ValueError('compiled abstraction failed; see transform.log')
    target = out/'abstract.il'
    return {'top': top, 'sources': [{'path': str(target.resolve()), 'format': 'rtlil',
            'sha256': sha256(target.read_bytes()).hexdigest()}],
            'abstraction': kind, 'source_sha256': sha256(Path(source).read_bytes()).hexdigest(),
            'limits': 'RAM cuts free complete memory outputs. Counter cuts free all adder outputs, not a quotient. '
                      'State cuts free selected flip-flop outputs. No automatic refinement. '
                      'Failures are abstraction observations only. Source assumptions remain.'}
