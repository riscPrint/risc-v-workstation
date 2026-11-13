"""Debug transport, Debug Module compliance, interoperability and trace commands."""
import json
import signal
from pathlib import Path
from . import campaign, etrace


def register(subparsers):
    parser = subparsers.add_parser('debug', help='simulated debug, compliance campaigns and trace checks')
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

    suite = sub.add_parser('suite', help='Debug Specification compliance campaign (C3 results)')
    suite.add_argument('--profile', type=Path, help='debug profile; default: project [debug_module] profile')
    suite.add_argument('--out', required=True, type=Path)
    suite.add_argument('--group', action='append', help='dm, abs, pb, dbg, trig or sba (repeatable)')
    suite.add_argument('--check', action='append', help='check id (repeatable)')
    suite.add_argument('--no-reference', action='store_true', help='skip the reference-model comparison')
    suite.add_argument('--port', type=int, help='remote_bitbang port; overrides the profile transport')
    suite.add_argument('--log', type=Path, help='adapter stderr log for dmi_process targets')
    suite.add_argument('--list', action='store_true', help='list the checks and exit')
    suite.set_defaults(func=_suite)

    tapc = sub.add_parser('tap', help='JTAG TAP and DTM conformance over remote_bitbang (C3 results)')
    tapc.add_argument('--host', default='127.0.0.1')
    tapc.add_argument('--port', type=int, required=True)
    tapc.add_argument('--irlen', type=int, default=5)
    tapc.add_argument('--idcode', type=lambda v: int(v, 0))
    tapc.add_argument('--no-busy-probe', action='store_true')
    tapc.add_argument('--out', required=True, type=Path)
    tapc.set_defaults(func=_tap)

    serve = sub.add_parser('serve', help='remote_bitbang JTAG server for the DM model or an adapter DMI bus')
    serve.add_argument('--profile', type=Path)
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=0)
    serve.add_argument('--dtm-latency', type=int, default=0, help='Run-Test/Idle cycles per DMI request')
    serve.add_argument('--idle', type=int, default=1, help='advertised dtmcs.idle')
    serve.add_argument('--ticks-per-ms', type=int, default=50, help='model hart steps per millisecond')
    serve.add_argument('--port-file', type=Path)
    serve.add_argument('--duration', type=float, help='stop after this many seconds')
    serve.add_argument('--log', type=Path)
    serve.set_defaults(func=_serve)


def _profile(path):
    from . import profile
    return profile.load(path) if path else profile.from_project()


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
        rows, complete = etrace.retirement(args.rvfi, require_rv64=True)
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


def _suite(args):
    from . import api
    if args.list:
        for item in api.list_checks():
            print(f"{item['id']}\t{item['rule']}")
        return 0
    try:
        result = api.suite_run(args.out, profile=args.profile, groups=args.group, checks=args.check,
                               reference=not args.no_reference, log=args.log, port=args.port,
                               project=getattr(args, 'project', None))
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'status': 'inconclusive', 'reason': str(exc)}))
        return 3
    print(json.dumps(result, sort_keys=True))
    return result['exit']


def _tap(args):
    from . import api
    try:
        result = api.tap_run(args.port, args.out, host=args.host, irlen=args.irlen, idcode=args.idcode,
                             busy_probe=not args.no_busy_probe)
    except OSError as exc:
        print(json.dumps({'status': 'inconclusive', 'reason': str(exc)}))
        return 3
    print(json.dumps(result, sort_keys=True))
    return result['exit']


def _interrupt(*_):
    raise KeyboardInterrupt


def _serve(args):
    from . import serve
    try:
        prof = _profile(args.profile)
        endpoint = serve.Endpoint(prof, host=args.host, port=args.port, latency=args.dtm_latency,
                                  idle=args.idle, ticks_per_ms=args.ticks_per_ms, log=args.log)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'status': 'error', 'reason': str(exc)}))
        return 2
    signal.signal(signal.SIGTERM, _interrupt)
    serve.serve_forever(endpoint, duration=args.duration, port_file=args.port_file,
                        announce=lambda line: print(line, flush=True))
    return 0
