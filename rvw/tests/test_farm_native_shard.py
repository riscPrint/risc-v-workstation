import json
import sys
from pathlib import Path
import pytest
from rvw.farm.native_shard import execute
from rvw.results import load_results

pytestmark = pytest.mark.fast


def adapter(tmp_path, mutation='', exit_code=0):
    script = tmp_path / 'adapter.py'
    script.write_text('''import json,sys,hashlib
from pathlib import Path
assert '--persistent' in sys.argv
for line in Path(sys.argv[sys.argv.index('--manifest')+1]).read_text().splitlines():
 r=json.loads(line); assert 'id' not in r; p=Path(r['out']); p.mkdir(parents=True)
 d=dict(schema='rvw.run/1',status='pass',core='fixture',config=r['config'],seed=r['seed'],elf_sha256=hashlib.sha256(Path(r['elf']).read_bytes()).hexdigest(),execution_mode='server')
 ''' + mutation + '''
 (p/'result.json').write_text(json.dumps(d))
''' + f'sys.exit({exit_code})\n')
    elf = tmp_path / 'program'; elf.write_bytes(b'elf')
    manifest = tmp_path / 'jobs.jsonl'
    manifest.write_text(json.dumps(dict(elf=str(elf), config='small', seed=1, id='program'))+'\n')
    return manifest, [sys.executable, str(script)]


def test_persistent_shard_records_validated_c3(tmp_path):
    manifest, command = adapter(tmp_path)
    report = execute(manifest, command, tmp_path/'out')
    assert report['status'] == 'complete'
    result = load_results(tmp_path/'out/results.json')
    assert result.tests[0].id == 'program'
    assert result.tests[0].run == 'cells/0'
    assert result.tests[0].conclusive
    assert result.tests[0].extra['kind'] == 'elf-dir'
    assert 'config' not in result.tests[0].extra['options']
    assert 'seed' not in result.tests[0].extra['options']
    assert result.source['identity_complete'] is False


@pytest.mark.parametrize('mutation', ["d['seed']=2", "d['execution_mode']='process'", "d['inconclusive']='missing capture'"])
def test_shard_refuses_wrong_or_incomplete_evidence(tmp_path, mutation):
    manifest, command = adapter(tmp_path, mutation)
    assert execute(manifest, command, tmp_path/'out')['status'] == 'inconclusive'


def test_shard_collects_dut_failure_without_claiming_pass(tmp_path):
    manifest, command = adapter(tmp_path, "d.update(status='fail',fail_code=3)")
    assert execute(manifest, command, tmp_path/'out')['status'] == 'complete'
    result = load_results(tmp_path/'out/results.json')
    assert result.tests[0].signature == 'fail:3'
    assert result.tests[0].failed


def test_recovery_does_not_retry_cancelled_worker(tmp_path):
    from rvw.farm.service import Queue
    queue = Queue(tmp_path)
    job = queue.submit('owner', ['true'], retries=1)
    queue.claim()
    queue.cancel(job['id'], 'owner')
    queue.update(job['id'], controller=2147483647, heartbeat=0)
    recovered = queue.recover()
    assert recovered[0]['state'] == 'cancelled'
    assert queue.work_once() is None


def test_native_dut_exit_is_complete_collection(tmp_path):
    manifest, command = adapter(tmp_path, "d.update(status='fail',fail_code=3)", exit_code=1)
    assert execute(manifest, command, tmp_path/'out')['status'] == 'complete'
    assert load_results(tmp_path/'out/results.json').tests[0].failed


def test_nonzero_exit_with_only_passes_is_not_complete(tmp_path):
    manifest, command = adapter(tmp_path, exit_code=1)
    assert execute(manifest, command, tmp_path/'out')['status'] == 'inconclusive'
