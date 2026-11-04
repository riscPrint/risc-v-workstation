"""CLI for bounded security checks."""
import json
from pathlib import Path
from rvw.common.capture import Capture
from rvw.common.proc import run_group
from rvw.cosim.platform import Platform
from rvw.cosim.spike import capture_shim
from .contracts import reference, assess
from .ift import instrument


def register(sub):
    p = sub.add_parser('security', help='bounded hardware leakage and IFT checks')
    s = p.add_subparsers(dest='security_command', required=True)
    i = s.add_parser('ift', help='instrument a mapped Yosys JSON netlist')
    i.add_argument('netlist')
    i.add_argument('--top', required=True)
    i.add_argument('--out', required=True)
    i.set_defaults(func=run_ift)
    c = s.add_parser('contract', help='run Spike and an RTL observation adapter')
    c.add_argument('manifest')
    c.add_argument('--out', required=True)
    c.set_defaults(func=run_contract)


def run_ift(args):
    try:
        result = instrument(json.loads(Path(args.netlist).read_text()), args.top)
        Path(args.out).write_text(result)
        return 0
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f'IFT error: {exc}')
        return 2


def run_contract(args):
    out = Path(args.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'rvw.leakage/1', 'verdict': 'inconclusive'}
    try:
        capture = Capture(out/'inputs')
        manifest = capture.file(Path(args.manifest))
        cfg = json.loads(manifest.copy.read_text())
        base = Path(manifest.resolved).parent
        def file(name):
            return capture.file(base/cfg[name]).copy
        elf = file('elf')
        platform = Platform(**json.loads(file('platform').read_text()))
        shim = capture_shim(capture, base/cfg['shim'])
        # Capture the adapter source tree. The adapter owns RTL tool binding and reset.
        adapter = capture.tree(base/cfg['adapter_tree'], git=False)
        command = cfg['adapter_command']
        if not command or not all(isinstance(x, str) for x in command):
            raise ValueError('adapter_command must be an argv list')
        adapter_tool = capture.tool(command[0])
        if not (0 < cfg.get('timeout', 30) <= 300):
            raise ValueError('adapter timeout must be in 0..300 seconds')
        secrets = cfg['secret_registers']
        if not secrets or any(type(r) is not int or not 1 <= r < 32 for r in secrets):
            raise ValueError('secret_registers must declare source registers')
        rows = []
        for index, case in enumerate(cfg['cases']):
            regs = {int(k): v for k, v in case['registers'].items()}
            ref = reference(platform, elf, shim, regs, cfg['stop_pc'], cfg['max_steps'])
            request = out/f'case-{index}.json'
            response = out/f'rtl-{index}.json'
            request.write_text(json.dumps({'registers': case['registers'], 'elf': str(elf),
                                         'stop_pc': cfg['stop_pc'], 'max_steps': cfg['max_steps']}))
            argv = [x.replace('{tree}', str(adapter.copy)).replace('{case}', str(request)).replace('{out}', str(response)) for x in command]
            argv[0] = str(adapter_tool.path)
            proc = run_group(argv, capture=True, timeout=cfg.get('timeout', 30), cwd=out)
            if proc.timed_out or proc.returncode:
                raise ValueError(f'RTL adapter failed for case {index}: {proc.stderr}')
            rtl = json.loads(response.read_text())
            public_regs = {str(r): regs.get(r, 0) for r in range(1, 32) if r not in secrets}
            rows.append({'public_key': [case['public_key'], public_regs], 'reference': ref, 'rtl': rtl})
        report = assess(rows, cfg['observations'])
        report['unmodeled_channels'] = cfg['unmodeled_channels']
        report['secret_registers'] = secrets
        report['rows'] = rows
        capture.verify_tools()
        report['input_capture'] = capture.record()
        report['adapter_command'] = command
        report['adapter_binding'] = 'Adapter must bind its simulator and dependencies; no tool qualification claim.'
    except (OSError, KeyError, TypeError, ValueError) as exc:
        report['verdict'] = 'inconclusive'
        if 'zkt_verdict' in report:
            report['zkt_verdict'] = 'inconclusive'
        report['cause'] = str(exc)
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    return {'no_violation': 0, 'violation': 1, 'inconclusive': 3}[report['verdict']]
