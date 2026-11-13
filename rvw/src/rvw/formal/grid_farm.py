"""Distribute explicit-model property shards through rvw.farm.worker."""
from concurrent.futures import ThreadPoolExecutor
import base64
from hashlib import sha256
import json
import math
from pathlib import Path
import shlex
import uuid

from rvw.common.proc import run_group
from rvw.farm.executor import cancel_host
from .deep_grid import grid
from .deep_model import validate
from .grid_adapter import identity


def distributed(model, hosts, out, *, timeout=60, **settings):
    validate(model)
    if not hosts or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('remote hosts and positive finite timeout required')
    if len({h['name'] for h in hosts}) != len(hosts):
        raise ValueError('host names must be unique')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    names = list(model['properties'])
    # One local shard and one shard per host. Each property has one owner.
    groups = [names[i::len(hosts) + 1] for i in range(len(hosts) + 1)]
    controls = [{'host': h, 'token': uuid.uuid4().hex, 'dispatched': bool(groups[i + 1])}
                for i, h in enumerate(hosts)]
    (out / 'control.json').write_text(json.dumps(controls, indent=2))
    expected_identity = identity()
    raw = json.dumps(model, sort_keys=True).encode()
    (out / 'model.json').write_bytes(raw)

    def shard(index):
        selected = groups[index]
        host = hosts[index - 1] if index else None
        row = {'host': host['name'] if host else 'local', 'expected_properties': selected}
        if not selected:
            return {**row, 'status': 'empty', 'rows': []}
        subset = {**model, 'properties': {p: model['properties'][p] for p in selected}}
        if not host:
            return {**row, **grid(subset, out / 'local', **settings)}
        payload = json.dumps({'model': subset, 'settings': settings}, sort_keys=True).encode()
        control = controls[index - 1]
        python = host.get('python', 'python3')
        request = {'cells': [{'id': '0', 'options': {}, 'elf_bytes': base64.b64encode(payload).decode(),
                              'elf_sha256': sha256(payload).hexdigest()}],
                   'adapter': [python, '-m', 'rvw.formal.grid_adapter'],
                   'identity_command': [python, '-m', 'rvw.formal.grid_adapter', 'identity'],
                   'identity': expected_identity, 'jobs': 1, 'timeout': timeout,
                   'resources': {'cpu': settings.get('workers', 1), **host.get('resources', {})},
                   'limits': host.get('limits', {}), 'token': control['token']}
        (out / f'request-{index}.json').write_text(json.dumps(request))
        try:
            address = host['address']
            if address.startswith('-'):
                raise ValueError('invalid SSH address')
            command = ['ssh', '-oBatchMode=yes', '-oConnectTimeout=10', *host.get('ssh_options', []), address,
                       shlex.join([python, '-m', 'rvw.farm.worker'])]
            proc = run_group(command, input=json.dumps(request), capture=True, timeout=timeout + 90)
            if proc.timed_out or proc.returncode:
                row['cancellation'] = cancel_host(control)
                raise ValueError('SSH shard failed: ' + (proc.stderr or '')[-1000:])
            reply = json.loads(proc.stdout)
            if reply['identity'] != expected_identity or reply['returncode'] or reply['timed_out']:
                raise ValueError('remote identity or execution failed')
            if [c['id'] for c in reply['cells']] != ['0']:
                raise ValueError('missing or duplicate remote cell')
            artifact = reply['cells'][0]['files']['result.json']
            data = base64.b64decode(artifact['data'], validate=True)
            if sha256(data).hexdigest() != artifact['sha256']:
                raise ValueError('result transfer hash differs')
            report = json.loads(data)
            if report['request_sha256'] != sha256(payload).hexdigest():
                raise ValueError('result request identity differs')
            if [r['property'] for r in report['rows']] != selected:
                raise ValueError('result property coverage differs')
            (out / f'remote-{index}.json').write_bytes(data)
            return {**row, **report}
        except (OSError, ValueError, KeyError) as exc:
            return {**row, 'status': 'inconclusive', 'reason': str(exc),
                    'rows': [{'property': p, 'status': 'inconclusive'} for p in selected]}

    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        shards = list(pool.map(shard, range(len(groups))))
    rows = [r for s in shards for r in s['rows']]
    status = 'fail' if any(r['status'] == 'fail' for r in rows) else 'pass' if all(r['status'] == 'pass' for r in rows) else 'inconclusive'
    report = {'schema': 'rvw.formal-model-grid/1', 'status': status, 'rows': rows, 'shards': shards,
              'model_sha256': sha256(raw).hexdigest(), 'adapter_identity': expected_identity,
              'limits': 'Trusted remote hosts. Uses farm SSH transfer, identity, reservations and cancellation. '
                        'Proof covers the supplied explicit graph only.'}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
