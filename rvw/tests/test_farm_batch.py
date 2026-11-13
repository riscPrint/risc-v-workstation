import json
import sys
from rvw.farm.batch import render, collect, LocalExecutor, KubernetesExecutor


def plan():
    return dict(name='demo', image='toolset@sha256:abc', volumes=[dict(claim='cache', mount='/cache', read_only=True)],
                shards=[dict(command=[sys.executable, '-c', 'pass'], results=[dict(path='result.json', contract='C1')])])


def test_render_and_missing_results(tmp_path):
    job = render(plan())['items'][0]
    assert job['spec']['backoffLimit'] == 0
    assert job['spec']['template']['spec']['containers'][0]['volumeMounts'][0]['readOnly']
    assert collect(plan(), tmp_path)['status'] == 'inconclusive'


def test_local_same_plan(tmp_path):
    executor = LocalExecutor(tmp_path)
    ids = executor.submit(plan())
    assert executor.queue.work_once()['state'] == 'complete'
    assert executor.status(ids)[0]['state'] == 'complete'
    # Process success does not fabricate C1 evidence.
    assert collect(plan(), tmp_path)['missing'] == ['result.json']


def test_fake_kubectl(tmp_path):
    fake = tmp_path / 'kubectl'
    fake.write_text('#!' + sys.executable + '\nimport json,sys\nprint(json.dumps({"args":sys.argv[1:]}))\n')
    fake.chmod(0o755)
    executor = KubernetesExecutor(str(fake))
    ids = executor.submit(plan())
    assert ids == [dict(name='demo-0', namespace='default')]
    assert executor.status(ids)[0]['args'][:3] == ['get', 'job', 'demo-0']
    assert executor.cancel(ids)['status'] == 'cancelled'
