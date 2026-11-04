"""Remote control records survive a broken SSH connection. No unconfirmed cancel success."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from .executor import worker
from .resources import reserve


def record(root, name, value):
    temp = root / (name + '.tmp')
    temp.write_text(json.dumps(value)); temp.replace(root / name)


def control_root(token):
    if not re.fullmatch('[0-9a-f]{32}', token):
        raise ValueError('invalid shard token')
    root = Path.home() / '.cache/rvw/farm/shards' / token
    root.mkdir(parents=True, exist_ok=True)
    return root


def groups_gone(groups):
    listing = subprocess.check_output(['ps', '-axo', 'pgid=,stat='], text=True, timeout=5)
    return not any(int(parts[0]) in groups and not parts[1].startswith('Z')
                   for line in listing.splitlines() if len(parts := line.split()) >= 2)


def stop(signum, frame):
    raise KeyboardInterrupt('remote shard cancelled')


def serve(request):
    root = control_root(request['token'])
    groups = []
    def started(pid):
        groups.append(pid)
        record(root, 'state.json', {'pid': os.getpid(), 'groups': groups})
        if (root / 'cancel').exists():
            raise KeyboardInterrupt('remote shard cancelled')
    record(root, 'state.json', {'pid': os.getpid(), 'groups': groups})
    try:
        if (root / 'cancel').exists():
            raise KeyboardInterrupt('remote shard cancelled')
        with reserve(request.get('resources', {'cpu': request['jobs']}), request['timeout']) as reservation:
            reply = worker({**request, 'timeout': max(.001, request['timeout'] - reservation['queued_s'])}, on_start=started)
            reply['reservation'] = reservation
            return reply
    finally:
        # run_group has stopped and reaped all owned leaders before this point.
        deadline = time.monotonic() + 5
        while not groups_gone(groups) and time.monotonic() < deadline:
            time.sleep(.1)
        record(root, 'ack.json', {'token': request['token'], 'acknowledged': groups_gone(groups),
                                 'groups': groups, 'process_groups_gone': groups_gone(groups)})


def cancel_remote(token):
    root = control_root(token)
    (root / 'cancel').touch()
    deadline = time.monotonic() + 20
    signalled = False
    while time.monotonic() < deadline:
        if (root / 'ack.json').exists():
            ack = json.loads((root / 'ack.json').read_text())
            # Recheck on the host before returning an acknowledgement.
            ack['acknowledged'] = ack['acknowledged'] and groups_gone(ack['groups'])
            return ack
        if not signalled and (root / 'state.json').exists():
            state = json.loads((root / 'state.json').read_text())
            try:
                os.kill(state['pid'], signal.SIGTERM)
                signalled = True
            except ProcessLookupError:
                return {'token': token, 'acknowledged': False, 'cause': 'worker lost before cleanup acknowledgement'}
        time.sleep(.1)
    return {'token': token, 'acknowledged': False, 'cause': 'cleanup acknowledgement timeout'}


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    if len(sys.argv) == 3 and sys.argv[1] == '--cancel':
        print(json.dumps(cancel_remote(sys.argv[2])))
    else:
        print(json.dumps(serve(json.load(sys.stdin))))
