"""Optional debug client and E-Trace reference commands."""
import json
from pathlib import Path
from . import campaign, etrace


def register(subparsers):
    parser = subparsers.add_parser('debug', help='simulated debug and E-Trace reference checks')
    sub = parser.add_subparsers(dest='debug_command', required=True)
    dm = sub.add_parser('openocd', help='check a caller-owned RV64 simulated JTAG target')
    dm.add_argument('--config', required=True, type=Path)
    dm.add_argument('--openocd', default='openocd')
    dm.add_argument('--log', type=Path, required=True)
    dm.add_argument('--timeout', type=float, default=30)
    dm.set_defaults(func=_campaign)
    ingress = sub.add_parser('ingress', help='export machine-mode C2 as baseline encoder input')
    ingress.add_argument('--rvfi', required=True, type=Path)
    ingress.add_argument('--out', required=True, type=Path)
    ingress.set_defaults(func=_ingress)
    trace = sub.add_parser('etrace', help='decode baseline E-Trace and compare exact C2 PCs')
    for name in ('reference', 'packets', 'static-config', 'user-config', 'toolchain', 'rvfi', 'out'):
        trace.add_argument('--' + name, required=True, type=Path)
    trace.add_argument('--loss', action='store_true', help='known loss or overflow: inconclusive')
    trace.add_argument('--timeout', type=float, default=30)
    trace.set_defaults(func=_trace)


def _campaign(args):
    try:
        result = campaign.run(args.config, openocd=args.openocd, timeout=args.timeout, log=args.log)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'inconclusive', 'reason': str(exc)}))
        return 3
    print(json.dumps(result, sort_keys=True))
    return {'pass': 0, 'fail': 1, 'inconclusive': 3}[result['status']]


def _ingress(args):
    try:
        rows, complete = etrace.retirement(args.rvfi)
        if not complete:
            raise ValueError('complete passing C2 end required')
        etrace.ingress(rows, args.out)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'status': 'inconclusive', 'reason': str(exc)}))
        return 3
    return 0


def _trace(args):
    try:
        rows, complete = etrace.retirement(args.rvfi)
        pcs, identity = etrace.decode(args.reference, args.packets, args.static_config,
                                      args.user_config, toolchain=args.toolchain, timeout=args.timeout)
        result = etrace.compare(pcs, [r['pc'] for r in rows], complete=complete, loss=args.loss)
        result.update(identity)
    except (OSError, ValueError, KeyError) as exc:
        result = {'status': 'inconclusive', 'reason': str(exc)}
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    return {'flow_match': 0, 'mismatch': 1, 'inconclusive': 3}[result['status']]
