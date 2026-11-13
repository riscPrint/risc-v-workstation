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
