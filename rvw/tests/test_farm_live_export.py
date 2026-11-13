import json
import pytest
from rvw.farm.service import Queue
from rvw.farm.live import snapshot
from rvw.farm.live_export import export
from rvw.results import SuiteResults, TestEntry, save_results

pytestmark = pytest.mark.fast


def test_export_owner_scope_and_embedded_clusters(tmp_path):
    queue = Queue(tmp_path/'queue')
    job = queue.submit('alice', ['true'])
    foreign = queue.submit('bob', ['private-other-owner'])
    folder = queue.root/job['id']
    save_results(SuiteResults('native', 'isa', 'generic', 'small', '2026-11-13', tests=[
        TestEntry('</script>', 'fail', signature='fail:3', run='cell')]), folder)
    cluster = snapshot(queue, 'alice')['failure_clusters'][0]
    target = folder/'bundles'/cluster['id']
    target.mkdir(parents=True)
    (target/'summary.json').write_text(json.dumps(dict(schema='rvw.bundle/1', status='fail', message='</script>')))
    report = export(queue, 'alice', tmp_path/'view.html')
    page = (tmp_path/'view.html').read_text()
    assert report['runs'] == 1 and report['clusters'] == 1
    assert foreign['id'] not in page
    assert 'fetch(' not in page and 'Token' not in page
    assert '\\u003c/script>' in page
    assert 'bundles/' + cluster['id'] + '/summary.json' in page
    assert page.count('</script>') == 1
    assert 'byId(\'refresh\').click()' in page


def test_c5_storage_does_not_hide_sibling_c3(tmp_path):
    queue = Queue(tmp_path/'queue')
    job = queue.submit('alice', ['true'])
    folder = queue.root/job['id']
    save_results(SuiteResults('run', 'isa', 'generic', 'small', '2026-11-13', tests=[
        TestEntry('test', 'fail', signature='fail:3')]), folder/'attempt-1')
    bundle = folder/'bundles'/'cluster'
    bundle.mkdir(parents=True)
    (bundle/'summary.json').write_text('{"schema":"rvw.bundle/1"}')
    (bundle/'work').mkdir()
    (bundle/'work'/'run.json').write_text('invalid captured run metadata')
    view = snapshot(queue, 'alice')
    assert view['runs'][0]['tests'] == 1
    assert view['runs'][0]['issues'] == []
    assert len(view['failure_clusters']) == 1
