"""Functions behind the debug CLI and MCP tools. Each returns a JSON-serializable dict."""
from __future__ import annotations

from pathlib import Path

from . import profile as profiles


def _profile(path=None, project=None):
    return profiles.load(path) if path else profiles.from_project(project)


def suite_run(out, profile=None, groups=None, checks=None, reference=True, log=None, port=None, project=None):
    from . import suite, checks as _registered  # noqa: F401
    prof = _profile(profile, project)
    if port is not None:
        prof['transport'] = {**prof['transport'], 'kind': 'remote_bitbang', 'port': port,
                             'host': prof['transport'].get('host', '127.0.0.1')}
    entries = suite.run(prof, groups=groups, ids=checks, reference=reference, log=log)
    results = suite.to_c3(entries, prof)
    path = suite.write(results, out)
    status, code = suite.verdict(results)
    counts = {}
    for test in results['tests']:
        counts[test['status']] = counts.get(test['status'], 0) + 1
    failed = [t['id'] for t in results['tests'] if t['status'] != 'pass']
    return {'status': status, 'exit': code, 'results': str(path), 'counts': counts,
            'unsupported': len(results['unsupported']), 'not_passed': failed}


def tap_run(port, out, host='127.0.0.1', irlen=5, idcode=None, busy_probe=True):
    from . import dmi, suite, tap
    transport = dmi.SocketJtag(host, port)
    try:
        entries = tap.run(transport, irlen=irlen, idcode=idcode, busy_probe=busy_probe)
    finally:
        transport.close()
    for entry in entries:
        entry.setdefault('observations', {})
        entry.setdefault('dmi_accesses', 0)
    results = suite.to_c3(entries, {'name': f'{host}:{port}', 'version': 'jtag',
                                    'transport': {'kind': 'remote_bitbang'}})
    results['suite'] = 'jtag-dtm'
    results['run_id'] = results['run_id'].replace(suite.SUITE, 'jtag-dtm')
    path = suite.write(results, out)
    status, code = suite.verdict(results)
    return {'status': status, 'exit': code, 'results': str(path),
            'not_passed': [t['id'] for t in results['tests'] if t['status'] != 'pass']}


def list_checks():
    from . import suite, checks as _registered  # noqa: F401
    return [{'id': c.id, 'group': c.group, 'rule': c.doc} for c in suite.CHECKS.values()]


def interop_run(out, elf, port=None, profile=None, reset_pc=None, idcode=None, openocd='openocd', gdb=None,
                timeout=120):
    from . import interop
    prof = profiles.load(profile) if profile else None
    return interop.run(port=port, profile=prof, elf=elf, openocd=openocd, gdb=gdb, out=out, timeout=timeout,
                       reset_pc=reset_pc, idcode=idcode)


def _filter(path):
    if not path:
        return None
    import tomllib
    raw = tomllib.loads(Path(path).read_text())
    unknown = set(raw) - {'privileges', 'ranges', 'exclude', 'start', 'stop'}
    if unknown:
        raise ValueError(f'unknown trace filter keys: {", ".join(sorted(unknown))}')
    return raw


def etrace_check(out, reference, rvfi, static_config, user_config, toolchain, packets=None, filter_path=None,
                 losses=()):
    import json
    from . import etrace_flow
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result, expected = etrace_flow.check(reference, rvfi, static_config, user_config, toolchain=toolchain,
                                         packets=packets, filter_spec=_filter(filter_path), losses=losses)
    if expected:
        etrace_flow.write_packets(expected, out / 'expected.te_inst')
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    result['result'] = str(out / 'result.json')
    return result


def etrace_loss(out, reference, rvfi, static_config, user_config, toolchain, packets=None, positions=None):
    from . import etrace_flow, suite
    tests = etrace_flow.loss_campaign(reference, rvfi, static_config, user_config, toolchain=toolchain,
                                      packets=packets, positions=positions)
    return _write_tests(out, tests, suite_name='etrace-loss', core=str(packets or 'reference-encoder'),
                        config='e-trace-baseline')


def _write_tests(out, tests, *, suite_name, core, config, extra=None):
    import datetime
    import json
    from . import suite
    created = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    results = {'schema': 'rvw.results/1', 'run_id': f'{created.replace(":", "-")}-{suite_name}',
               'suite': suite_name, 'core': core, 'config': config, 'created': created, 'source': {},
               'tests': tests, **(extra or {})}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    status, code = suite.verdict(results)
    return {'status': status, 'exit': code, 'results': str(out / 'results.json'),
            'counts': {s: sum(t['status'] == s for t in tests) for s in {t['status'] for t in tests}}}


def _ntrace_options(mode='htm', sync_period=0, adapter=None):
    from . import ntrace_check
    if adapter:
        return None, ntrace_check.load_adapter(adapter)
    return {'mode': mode, 'sync_period': sync_period}, None


def ntrace_check(out, rvfi, elf, packets=None, filter_path=None, losses=(), mode='htm', sync_period=0, adapter=None):
    import json
    from . import ntrace_check as nc
    profile, loaded = _ntrace_options(mode, sync_period, adapter)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result, expected = nc.check(rvfi, elf, packets=packets, profile=profile, adapter=loaded,
                                filter_spec=_filter(filter_path), losses=losses)
    (out / 'expected.ntrace').write_bytes(expected)
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    result['result'] = str(out / 'result.json')
    return result


def ntrace_loss(out, rvfi, elf, positions=None, mode='htm', sync_period=0, adapter=None):
    from . import ntrace_check as nc
    profile, loaded = _ntrace_options(mode, sync_period, adapter)
    tests = nc.loss_campaign(rvfi, elf, profile=profile, adapter=loaded, positions=positions)
    params = nc.params_for(profile, loaded)
    return _write_tests(out, tests, suite_name='ntrace-loss', core='reference-encoder',
                        config=f'n-trace-{params["mode"]}', extra={'codec': 'rvw-ntrace/1'})


def trace_adapter(path):
    from . import ntrace_check
    adapter = ntrace_check.load_adapter(path)
    return {'name': adapter['name'], 'vendor': adapter['vendor'], 'verified': adapter['verified'],
            'vectors': adapter['vectors'], 'sha256': adapter['sha256'], 'specification': adapter['specification']}



def ingress_check(out, ingress, rvfi, elf, mode='htm', sync_period=0, reference=None, static_config=None,
                  user_config=None, toolchain=None):
    """Compare RTL trace ingress with C2 and trace the run from it (N-Trace; E-Trace with reference)."""
    import json
    from . import ingress_check as ic
    if reference is not None and not (static_config and user_config and toolchain):
        raise ValueError('E-Trace needs static_config, user_config and toolchain with reference')
    result = ic.check(ingress, rvfi, elf, ntrace_profile={'mode': mode, 'sync_period': sync_period},
                      reference=reference, static_config=static_config, user_config=user_config, toolchain=toolchain)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    result['result'] = str(out / 'result.json')
    return result
