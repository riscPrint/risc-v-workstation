import json
import socket
from concurrent.futures import ThreadPoolExecutor
from rvw.cosim.lockstep import serve_connection
from rvw.cosim.platform import Platform
from test_state import fixture, Model


def test_blocking_match_and_first_mismatch():
    for mutate in (False, True):
        header, row = fixture()
        model = Model(row.copy())
        if mutate:
            row['fd_wdata'] = '0x1'
        a, b = socket.socketpair()
        with a, b, ThreadPoolExecutor() as pool:
            future = pool.submit(serve_connection, a, model, Platform.load('boom'), reproduction={})
            stream = b.makefile('rwb')
            def send(record):
                stream.write((json.dumps(record)+'\n').encode())
                stream.flush()
                return json.loads(stream.readline())
            assert send(header)['status'] == 'continue'
            result = send(row)
            if mutate:
                assert result['status'] == 'mismatch'
                assert result['mismatch']['order'] == 0
            else:
                assert result['status'] == 'continue'
                result = send(dict(event='end', cycle=2, status='pass'))
                assert result['status'] == 'match'
                assert result['trace_complete']
            assert future.result(timeout=2) == result
            stream.close()


def test_launcher_blocks_each_record(tmp_path):
    import sys
    from rvw.cosim.online import launch_online
    header, row = fixture()
    records = [header, row, dict(event='end', cycle=2, status='pass')]
    script = tmp_path / 'adapter.py'
    script.write_text('import socket,os,json\n'
        's=socket.create_connection(("127.0.0.1",int(os.environ["RVW_COSIM_PORT"])))\n'
        'f=s.makefile("rwb")\n'
        f'for r in {records!r}:\n'
        ' f.write((json.dumps(r)+"\\n").encode()); f.flush()\n'
        ' response=json.loads(f.readline())\n'
        ' assert response["status"] in ("continue","match"), response\n'
        'f.close(); s.close()\n')
    result = launch_online([sys.executable, str(script)], Model(row), Platform.load('boom'),
                          out=tmp_path/'out', reproduction={}, lockstep=True, timeout=5)
    assert result['status'] == 'match', result
    assert result['mode'] == 'lockstep'


def test_launcher_reports_exit_before_connection(tmp_path):
    import sys
    import pytest
    from rvw.cosim.online import launch_online
    _, row = fixture()
    with pytest.raises(ValueError, match='exited before lockstep connection'):
        launch_online([sys.executable, '-c', 'raise SystemExit(2)'],
                      Model(row), Platform.load('boom'), out=tmp_path/'out',
                      reproduction={}, lockstep=True, timeout=5)
