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
    suite.add_argument('--out', type=Path)
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

    interop = sub.add_parser('interop', help='OpenOCD and GDB functional campaign against a JTAG target (C3)')
    interop.add_argument('--port', type=int, help='remote_bitbang port of a running target')
    interop.add_argument('--profile', type=Path, help='serve the reference model for this profile instead')
    interop.add_argument('--elf', type=Path, required=True, help='RV32 or RV64 program with _start, loop, target, counter')
    interop.add_argument('--reset-pc', type=lambda v: int(v, 0), help='expected pc after monitor reset halt')
    interop.add_argument('--idcode', type=lambda v: int(v, 0))
    interop.add_argument('--openocd', default='openocd')
    interop.add_argument('--gdb')
    interop.add_argument('--out', required=True, type=Path)
    interop.add_argument('--timeout', type=float, default=120)
    interop.set_defaults(func=_interop)

    for name, helptext in (('etrace-check', 'expected E-Trace stream from C2; compare encoder packets, windows, leaks'),
                           ('etrace-loss', 'E-Trace loss and resynchronization campaign (C3)')):
        cmd = sub.add_parser(name, help=helptext)
        for option in ('reference', 'static-config', 'user-config', 'toolchain', 'rvfi', 'out'):
            cmd.add_argument('--' + option, required=True, type=Path)
        cmd.add_argument('--packets', type=Path, help='encoder output: .te_inst CSV or .te_inst_raw')
        if name == 'etrace-check':
            cmd.add_argument('--filter', type=Path, help='TOML trace filter: privileges, ranges, exclude, start, stop')
            cmd.add_argument('--loss-at', type=int, action='append', default=[],
                             help='packet index that follows a known gap (repeatable)')
            cmd.set_defaults(func=_etrace_check)
        else:
            cmd.add_argument('--at', type=int, action='append', help='packet index to damage (repeatable)')
            cmd.set_defaults(func=_etrace_loss)

    ncheck = sub.add_parser('ntrace-check', help='expected N-Trace stream from C2; compare a capture (separate from E-Trace)')
    nloss = sub.add_parser('ntrace-loss', help='N-Trace loss and resynchronization campaign (C3)')
    for cmd in (ncheck, nloss):
        cmd.add_argument('--rvfi', required=True, type=Path)
        cmd.add_argument('--elf', required=True, type=Path, help='program image for the decoder')
        cmd.add_argument('--out', required=True, type=Path)
        cmd.add_argument('--mode', choices=('htm', 'btm'), default='htm')
        cmd.add_argument('--sync-period', type=int, default=0, help='periodic ProgTraceSync after N address messages')
        cmd.add_argument('--adapter', type=Path, help='rvw.trace-adapter/1 file (overrides --mode and --sync-period)')
    ncheck.add_argument('--packets', type=Path, help='captured encoder bytes (MDO/MSEO)')
    ncheck.add_argument('--filter', type=Path)
    ncheck.add_argument('--loss-at', type=int, action='append', default=[], help='message index after a known gap')
    ncheck.set_defaults(func=_ntrace_check)
    nloss.add_argument('--at', type=int, action='append')
    nloss.set_defaults(func=_ntrace_loss)
    ingress = sub.add_parser('ingress-check', help='check RTL trace ingress (te_ingress.csv) against C2; '
                             'trace the run from it with N-Trace, and E-Trace with --reference')
    ingress.add_argument('--ingress', required=True, type=Path, help='te_ingress.csv from RiscvSim --trace-ingress')
    ingress.add_argument('--rvfi', required=True, type=Path)
    ingress.add_argument('--elf', required=True, type=Path)
    ingress.add_argument('--out', required=True, type=Path)
    ingress.add_argument('--mode', choices=('htm', 'btm'), default='htm')
    ingress.add_argument('--sync-period', type=int, default=0)
    for option in ('reference', 'static-config', 'user-config', 'toolchain'):
        ingress.add_argument('--' + option, type=Path, help='E-Trace reference flow (all four together)')
    ingress.set_defaults(func=_ingress_check)
    adapter = sub.add_parser('trace-adapter', help='check a vendor trace adapter against its known packet vectors')
    adapter.add_argument('adapter', type=Path)
    adapter.set_defaults(func=_trace_adapter)


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
    if args.out is None:
        print('--out is required unless --list is used')
        return 2
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


def _interop(args):
    from . import api
    try:
        result = api.interop_run(args.out, elf=args.elf, port=args.port, profile=args.profile,
                                 reset_pc=args.reset_pc, idcode=args.idcode, openocd=args.openocd,
                                 gdb=args.gdb, timeout=args.timeout)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'status': 'inconclusive', 'reason': str(exc)}))
        return 3
    print(json.dumps(result, sort_keys=True))
    return {'pass': 0, 'fail': 1}.get(result['status'], 3)



def _etrace_check(args):
    from . import api
    try:
        result = api.etrace_check(args.out, args.reference, args.rvfi, args.static_config, args.user_config,
                                  args.toolchain, packets=args.packets, filter_path=args.filter, losses=args.loss_at)
    except (OSError, ValueError, KeyError) as exc:
        result = {'status': 'inconclusive', 'reason': str(exc)}
    print(json.dumps({k: v for k, v in result.items() if k != 'windows'}, sort_keys=True))
    return {'flow_match': 0, 'mismatch': 1, 'leak': 1}.get(result['status'], 3)


def _etrace_loss(args):
    from . import api
    try:
        result = api.etrace_loss(args.out, args.reference, args.rvfi, args.static_config, args.user_config,
                                 args.toolchain, packets=args.packets, positions=args.at)
    except (OSError, ValueError, KeyError) as exc:
        result = {'status': 'inconclusive', 'reason': str(exc), 'exit': 3}
    print(json.dumps(result, sort_keys=True))
    return result['exit']



def _ntrace_args(args):
    return dict(mode=args.mode, sync_period=args.sync_period, adapter=args.adapter)


def _ntrace_check(args):
    from . import api
    try:
        result = api.ntrace_check(args.out, args.rvfi, args.elf, packets=args.packets, filter_path=args.filter,
                                  losses=args.loss_at, **_ntrace_args(args))
    except (OSError, ValueError, KeyError) as exc:
        result = {'status': 'inconclusive', 'reason': str(exc)}
    print(json.dumps({k: v for k, v in result.items() if k != 'windows'}, sort_keys=True))
    return {'flow_match': 0, 'mismatch': 1, 'leak': 1}.get(result['status'], 3)


def _ingress_check(args):
    from . import api
    try:
        result = api.ingress_check(args.out, args.ingress, args.rvfi, args.elf, mode=args.mode,
                                   sync_period=args.sync_period, reference=args.reference,
                                   static_config=args.static_config, user_config=args.user_config,
                                   toolchain=args.toolchain)
    except (OSError, ValueError, KeyError) as exc:
        result = {'status': 'inconclusive', 'reason': str(exc)}
    summary = {k: v for k, v in result.items() if k not in ('ntrace', 'etrace')}
    for key in ('ntrace', 'etrace'):
        if key in result:
            summary[key] = {k: v for k, v in result[key].items() if k != 'windows'}
    print(json.dumps(summary, sort_keys=True))
    return {'match': 0, 'mismatch': 1}.get(result['status'], 3)


def _ntrace_loss(args):
    from . import api
    try:
        result = api.ntrace_loss(args.out, args.rvfi, args.elf, positions=args.at, **_ntrace_args(args))
    except (OSError, ValueError, KeyError) as exc:
        result = {'status': 'inconclusive', 'reason': str(exc), 'exit': 3}
    print(json.dumps(result, sort_keys=True))
    return result['exit']


def _trace_adapter(args):
    from . import api
    try:
        result = api.trace_adapter(args.adapter)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'reason': str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result['verified'] else 1
