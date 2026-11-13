"""Optional external gate-netlist/SDF handoff. Declarations are not signoff."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol


class TimingPort(Protocol):
    """A native adapter owns annotation and simulator-specific diagnostics.

    run_timing consumes captured bytes, not the original mutable paths. It must
    refuse unannotated cells, ignored delays and unsupported timing checks.
    The return value is a native C1 result, never inferred from compilation.
    """
    def timing_capabilities(self) -> dict: ...
    def run_timing(self, request: dict, files: dict[str, bytes]) -> dict: ...


def capture(manifest):
    path = Path(manifest).resolve(strict=True)
    request = json.loads(path.read_bytes())
    if request.get('schema') != 'rvw.timing-request/1':
        raise ValueError('unsupported timing replay request')
    if request.get('corner') not in ('min', 'typ', 'max'):
        raise ValueError('SDF corner must be min, typ or max')
    if not isinstance(request.get('top'), str) or not request['top']:
        raise ValueError('external timing replay needs an explicit top')
    if request.get('unknown_behavior') not in ('four-state', 'two-state'):
        raise ValueError('unknown behavior must be explicitly requested')
    for field in ('cells', 'delays', 'timing_checks', 'cell_libraries'):
        if not isinstance(request.get(field), list) or not all(isinstance(x, str) and x for x in request[field]):
            raise ValueError(f'{field} must be an explicit string inventory')
    if not request['cells'] or not request['cell_libraries']:
        raise ValueError('gate cells and cell libraries must be declared')
    files = {}
    for name in [request['netlist'], request['sdf'], *request['cell_libraries']]:
        if not isinstance(name, str) or not name:
            raise ValueError('netlist, SDF and library paths are required')
        files[name] = (path.parent / name).read_bytes()
        if not files[name]:
            raise ValueError(f'empty timing input: {name}')
    return request, files


def check(request, files, capabilities):
    if capabilities.get('schema') != 'rvw.timing-capabilities/1':
        raise ValueError('unsupported timing capability declaration')
    for name in ('simulator', 'version', 'unknown_behavior'):
        if not isinstance(capabilities.get(name), str) or not capabilities[name]:
            raise ValueError(f'timing adapter must declare {name}')
    for field in ('cells', 'delays', 'timing_checks'):
        supported = capabilities.get(field)
        if not isinstance(supported, list) or not all(isinstance(x, str) for x in supported):
            raise ValueError(f'timing adapter must declare {field}')
        missing = set(request[field]) - set(supported)
        if missing:
            raise ValueError(f'unsupported {field}: {sorted(missing)}')
    if request['unknown_behavior'] != capabilities['unknown_behavior']:
        raise ValueError('timing unknown-value behavior mismatch')
    if request['corner'] not in capabilities.get('corners', []):
        raise ValueError('unsupported SDF corner')
    return dict(schema='rvw.timing-handoff/1', status='declared_compatible',
        evidence='interface readiness only; no annotation or physical signoff',
        capabilities=capabilities, request=request,
        files={name: dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)) for name, raw in files.items()})


def inspect(manifest, capabilities):
    request, files = capture(manifest)
    return check(request, files, json.loads(Path(capabilities).read_bytes()))


def replay(port: TimingPort, manifest):
    request, files = capture(manifest)
    handoff = check(request, files, port.timing_capabilities())
    result = port.run_timing(request, files)
    if result.get('schema') != 'rvw.run/1' or result.get('status') not in ('pass', 'fail', 'timeout', 'assert', 'error', 'rvfi_error'):
        raise ValueError('external timing adapter did not return a native C1 outcome')
    return dict(handoff=handoff, result=result, physical_signoff=False)


def command(a):
    try:
        print(json.dumps(inspect(a.manifest, a.capabilities), indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status='error', message=str(exc))))
        return 2
