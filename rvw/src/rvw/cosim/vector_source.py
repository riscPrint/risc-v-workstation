"""Pinned external source setup for the existing strict vector suite runner."""
import json
from pathlib import Path
from rvw.common.proc import run_group

REVISION = 'f76bff121dce91b6b23e1d37be77a5e44af914c3'
ENV_REVISION = '81721c126d7dd7335829948b4a19070546e465d6'
REPOSITORY = 'https://github.com/chipsalliance/riscv-vector-tests.git'
ENV_REPOSITORY = 'https://github.com/riscv/riscv-test-env.git'
ROOT = Path(__file__).resolve().parents[4]


def fetch(out, *, timeout=120):
    out = Path(out).resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError('vector sources must be outside the workstation repository')
    if out.exists():
        raise ValueError('vector source destination already exists')
    out.parent.mkdir(parents=True, exist_ok=True)
    def run(args):
        result = run_group(args, capture=True, timeout=timeout)
        if result.timed_out or result.returncode:
            raise ValueError('vector source setup failed: ' + (result.stderr or 'timeout'))
        return result.stdout.strip()
    for repository, revision, path in [(REPOSITORY, REVISION, out),
            (ENV_REPOSITORY, ENV_REVISION, out/'env/riscv-test-env')]:
        # Ordinary clones, with no submodule registration in the workstation.
        run(['git', 'clone', '--no-checkout', '--filter=blob:none', repository, str(path)])
        run(['git', '-C', str(path), 'checkout', '--detach', revision])
        actual = run(['git', '-C', str(path), 'rev-parse', 'HEAD'])
        if actual != revision:
            raise ValueError('vector source revision mismatch')
    report = dict(schema='rvw.vector-source/1', status='prepared', path=str(out),
                  revision=REVISION, env_revision=ENV_REVISION, built=False,
                  vector_comparison_required=True)
    (out/'rvw-source.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def register(subs):
    parser = subs.add_parser('vector-source', help='fetch pinned vector test sources outside the repository')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def execute_json(**options):
    try:
        return fetch(**options)
    except (OSError, ValueError) as exc:
        return dict(schema='rvw.vector-source/1', status='error', message=str(exc))


def run(args):
    result = execute_json(out=args.out, timeout=args.timeout)
    print(json.dumps(result))
    return 2 if result['status'] == 'error' else 0


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.mcp.worker import handler
    return [ToolSpec('cosim_vector_source', 'Fetch pinned riscv-vector-tests and environment sources outside the workstation. '
                     'No build or vector correctness claim.',
        schema(dict(out={'type': 'string'}, timeout={'type': 'number', 'exclusiveMinimum': 0, 'default': 120}), ['out']),
        handler('rvw.cosim.vector_source'), long=True,
        side_effects='long-running; launches git; downloads pinned sources under requested source output directory', native_tools=(),
        )]
