import json
import sys
from rvw.farm.shard_plan import plan
from rvw.farm.batch import LocalExecutor, collect, render


def test_same_manifest_local_execution_and_cluster_render(tmp_path):
    elf = tmp_path / 'input.elf'
    elf.write_bytes(b'fake ELF')
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text('\n'.join(json.dumps(dict(elf=str(elf), config='small', seed=s)) for s in [1, 2]))
    adapter = tmp_path / 'adapter.py'
    adapter.write_text("""import json,sys,hashlib
from pathlib import Path
manifest=Path(sys.argv[sys.argv.index('--manifest')+1])
for line in manifest.read_text().splitlines():
 r=json.loads(line); out=Path(r['out']); out.mkdir(parents=True)
 result=dict(schema='rvw.run/1',status='pass',core='fixture',config=r['config'],seed=r['seed'],elf_sha256=hashlib.sha256(Path(r['elf']).read_bytes()).hexdigest())
 (out/'result.json').write_text(json.dumps(result))
""")
    root = tmp_path / 'shared'
    document = plan(manifest, [sys.executable, str(adapter)], root, 'fixture-image', 'results', shards=2)
    assert document['expected_cells'] == 2
    assert len(render(document)['items']) == 2
    local = LocalExecutor(tmp_path / 'queue')
    ids = local.submit(document)
    for _ in ids:
        assert local.queue.work_once()['state'] == 'complete'
    report = collect(document, root)
    assert report['status'] == 'complete'
    assert len(report['evidence']) == 2
    # A changed expected identity cannot earn completeness.
    document['shards'][0]['results'][0]['identity']['seed'] = 999
    assert collect(document, root)['status'] == 'inconclusive'
