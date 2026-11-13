"""`rvw regress cosim`: strict reference comparison of every C1 result in one regress run.

Each test gets one status. `match` needs a passing C1 result, a complete strict match with no
synchronization or masks, and an equal instruction count. `mismatch` is a reference difference
(a finding until a reviewer explains it). `fail` is a failing C1 result (the program's own
check). `error` is any other C1 status (assert, timeout, error). Everything else is
`inconclusive` with a reason. No status is promoted.
"""
import json
from collections import Counter
from pathlib import Path

from rvw.cosim.cli import execute_json as cosim
from rvw.mcp.spec import ToolSpec, schema
from rvw.regress.random_stream import complete
from rvw.regress.run_evidence import owned_run_paths
from rvw.results import load_run


def _member(path, root):
    # Test ids can contain directories. Locate the C3 membership boundary.
    try:
        parts = Path(path).resolve().relative_to(Path(root).resolve()).parts
        boundary = parts.index('tests')
        prefix = Path(root).resolve().parts
        absolute = prefix + parts
        if len(prefix) + boundary >= 2:
            return absolute[len(prefix) + boundary - 2], '/'.join(parts[boundary + 1:-1])
    except ValueError:
        pass
    return 'unknown', Path(path).parent.name


# Allowed synchronization: checker kind to enable, and the only applied reason it may show.
ALLOW = {'reset': ('csr', 'csr_reset_unknown'), 'irq': ('irq', 'irq'), 'mmio': ('mmio', 'mmio')}


def matched(comparison, run, allow):
    """A complete match. Each applied mask or synchronization must have an allowed reason."""
    reasons = {ALLOW[k][1] for k in allow}
    reason = lambda item: item.get('reason') if isinstance(item, dict) else None  # noqa: E731
    if any(reason(m) not in reasons for m in comparison.get('applied_masks', [])):
        return False
    recent = comparison.get('recent_synchronizations', [])
    if comparison.get('synchronized', 0) > len(recent):
        return False  # the history is truncated: some synchronizations cannot be checked
    if any(reason(x) not in reasons for x in recent):
        return False
    return complete(dict(comparison, synchronized=0), run)


def _mailbox_read(run, elf, mismatch):
    """True when a stimulus run's first difference is a load of its `stimulus_ack` word."""
    extra = getattr(run, 'extra', None) or {}
    actual = (mismatch or {}).get('actual') or {}
    if not extra.get('stimulus_sha256') or not actual.get('mem_rmask') or actual.get('mem_wmask'):
        return False
    if set((mismatch or {}).get('differences', {})) - {'mem_rdata', 'rd_wdata'}:
        return False
    from rvw.runs.elf import Elf
    try:
        ack = Elf(str(elf)).symbols().get('stimulus_ack')
    except (OSError, ValueError):
        return False
    return ack is not None and ack.value <= int(str(actual.get('mem_addr')), 0) < ack.value + 8


def check_run(run_dir, platform, model='spike', on_row=None, allow=()):
    """Compare each owned C1 result of `run_dir` with the reference. Returns rows and counts.

    `allow` names synchronizations a match may use: `reset` (the architecturally unspecified
    mscratch reset value from the C2 snapshot), `irq` (pending bits of inputs that C2 `irq`
    events show asserted; the reference has no input pins) and `mmio` (DUT data for loads from
    the platform's declared MMIO regions; the reference has no device state). Anything else keeps the row
    inconclusive. A match row records its `synchronized` count."""
    allow = tuple(sorted(set(allow)))
    if set(allow) - set(ALLOW):
        raise ValueError(f'unknown --allow-sync kinds {sorted(set(allow) - set(ALLOW))}')
    rows = []
    for path in owned_run_paths(run_dir):
        run = load_run(path)
        elf = run.elf.get('path') if isinstance(run.elf, dict) else run.elf
        suite, test = _member(path, run_dir)
        row = dict(suite=suite, test=test, c1_status=run.status,
                   cycles=run.cycles, instret=run.instret, status='inconclusive')
        trace = run.artifact('rvfi_trace')
        if run.why_inconclusive:
            row['reason'] = run.why_inconclusive
        elif run.status != 'pass':
            row['status'] = 'fail' if run.status == 'fail' else 'error'
            row['reason'] = run.message
        elif not trace:
            row['reason'] = 'C1 result has no C2 trace'
        else:
            enabled = {ALLOW[k][0] for k in allow}
            options = (dict(strict=False, strict_sync=tuple(k for k in ('counter', 'mmio', 'csr', 'irq') if k not in enabled))
                       if allow else dict(strict=True))
            comparison = cosim('check', elf=str(elf), trace=str(trace), platform=str(platform), model=model,
                               core=run.core, **options)
            if comparison.get('status') == 'mismatch' and _mailbox_read(run, elf, comparison['mismatch']):
                # The harness wrote this RAM word (rvw.stimulus/1 acknowledgement); the single-hart
                # reference cannot model it, so the comparison stops here without a verdict.
                row['reason'] = 'reference stopped at a harness-written stimulus_ack read'
                row['mismatch'] = comparison.get('mismatch')
            elif comparison.get('status') == 'mismatch':
                row['status'] = 'mismatch'
                row['mismatch'] = comparison.get('mismatch')
            elif matched(comparison, run, allow):
                row['status'] = 'match'
                row['synchronized'] = comparison.get('synchronized', 0)
            else:
                row['reason'] = comparison.get('message') or f"comparison {comparison.get('status')} is incomplete"
        rows.append(row)
        if on_row:
            on_row(row)
    suites = {}
    for row in rows:
        suites.setdefault(row['suite'], Counter())[row['status']] += 1
    return dict(schema='rvw.regress-cosim/1', run=str(Path(run_dir).resolve()), platform=str(Path(platform).resolve()),
                model=model, allow_sync=list(allow), counts=dict(Counter(r['status'] for r in rows)),
                suites={k: dict(v) for k, v in sorted(suites.items())}, rows=rows)


def register(commands):
    p = commands.add_parser('cosim', help='strictly compare every C1 result of a regress run with the reference')
    p.add_argument('run', type=Path, help='rvw regress run output directory')
    p.add_argument('--platform', type=Path, required=True, help='cosim platform JSON of the core profile')
    p.add_argument('--model', default='spike')
    p.add_argument('--allow-sync', default='', help='comma-separated: reset (unspecified mscratch reset value), '
                   'irq (pending bits of asserted inputs), mmio (loads from declared MMIO regions); default none (strict)')
    p.add_argument('--out', type=Path, help='write the full report here')
    p.add_argument('--json', action='store_true')
    def run(args):
        import sys
        try:
            result = check_run(args.run, args.platform, args.model,
                               on_row=None if args.json else lambda r: print(f"{r['suite']}/{r['test']}: {r['status']}", flush=True),
                               allow=[k for k in args.allow_sync.split(',') if k])
        except (ValueError, OSError, KeyError) as exc:
            print(f'rvw regress cosim: {exc}', file=sys.stderr)
            return 2
        if args.out:
            args.out.write_text(json.dumps(result, indent=1) + '\n')
        print(json.dumps(result if args.json else dict(counts=result['counts'], suites=result['suites'])))
        return 0 if set(result['counts']) <= {'match'} and result['counts'] else 1
    p.set_defaults(func=run)


def mcp_tools():
    return [ToolSpec('regress_cosim', 'Strictly compare every C1 result of one regress run with the reference. '
                     'Statuses: match, mismatch, fail, error, inconclusive. Nothing is masked or promoted.',
                     schema({'run_dir': {'type': 'string'}, 'platform': {'type': 'string'}, 'model': {'type': 'string'},
                             'allow_sync': {'type': 'array', 'items': {'type': 'string', 'enum': sorted(ALLOW)}}},
                            ['run_dir', 'platform']),
                     lambda run_dir, platform, model='spike', allow_sync=(): check_run(run_dir, platform, model, allow=allow_sync),
                     annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=('Spike',))]
