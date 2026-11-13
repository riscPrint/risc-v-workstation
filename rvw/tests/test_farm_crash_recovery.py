import json
import subprocess
import sys
from pathlib import Path
from rvw.common.proc import kill_group
from rvw.farm.service import process_stamp
from rvw.farm.worker import control_root, cancel_remote
from rvw.farm.recovery import recover_dead


def test_dead_worker_cleanup_releases_only_its_reservation(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    token = 'a'*32
    root = control_root(token)
    capacity = tmp_path / '.cache/rvw/farm'
    reservations = capacity / 'reservations.json'
    reservations.write_text(json.dumps([dict(pid=2147483647, token='dead'), dict(pid=1, token='other')]))
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    try:
        state = dict(pid=2147483647, groups=[child.pid], group_stamps={str(child.pid): process_stamp(child.pid)})
        (root / 'state.json').write_text(json.dumps(state))
        ack = cancel_remote(token)
        assert ack['acknowledged'] and ack['reservation_released']
        assert json.loads(reservations.read_text()) == [dict(pid=1, token='other')]
    finally:
        kill_group(child, grace=.1)


def test_unknown_process_identity_is_not_reclaimed(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    root = control_root('b'*32)
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    try:
        result = recover_dead(root, dict(pid=2147483647, groups=[child.pid]), 'b'*32)
        assert not result['acknowledged']
        assert child.poll() is None
    finally:
        kill_group(child, grace=.1)
