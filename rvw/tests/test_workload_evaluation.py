from dataclasses import asdict
import json
from pathlib import Path
import pytest
from test_ooo import cfg
from rvw.workloads import evaluation

pytestmark = pytest.mark.fast


def test_default_set_has_open_application_categories():
    data = json.loads((evaluation.ASSETS/'evaluation.json').read_text())
    groups = {g['recipe']:g['bench'].split(',') for g in data['groups']}
    assert {'embench','coremark','riscv-tests','zstd'} <= groups.keys()
    assert 'slre' in groups['embench']
    assert {'qsort','rsort'} <= set(groups['riscv-tests'])


def setup_plan(tmp_path):
    (tmp_path/'model.json').write_text(json.dumps(asdict(cfg())))
    manifest = tmp_path/'evaluation.json'
    manifest.write_text(json.dumps(dict(schema='rvw.workload-evaluation/1',
        groups=[dict(recipe='local',bench='kernel')],models={'model':'model.json'})))
    build = tmp_path/'build.json'
    build.write_text(json.dumps(dict(workloads=[dict(id='kernel')])))
    return manifest,build


def test_failed_output_check_stops_before_timing(tmp_path,monkeypatch):
    manifest,build = setup_plan(tmp_path)
    monkeypatch.setattr(evaluation,'verify',lambda *a: {'status':'fail'})
    monkeypatch.setattr(evaluation,'run_group',lambda *a,**k: pytest.fail('must not trace a failed program'))
    with pytest.raises(ValueError,match='output check failed'):
        evaluation.evaluate(tmp_path/'out',builds={'local':str(build)},manifest=manifest)
    assert not (tmp_path/'out/report.json').exists()


def test_prebuilt_selection_cannot_silently_change(tmp_path):
    manifest,build = setup_plan(tmp_path)
    build.write_text(json.dumps(dict(workloads=[dict(id='different')])))
    with pytest.raises(ValueError,match='selection differs'):
        evaluation.evaluate(tmp_path/'out',builds={'local':str(build)},manifest=manifest)


def test_reused_capture_keeps_trace_identity(tmp_path,monkeypatch):
    from hashlib import sha256
    from test_ooo import trace
    manifest,build=setup_plan(tmp_path)
    elf=tmp_path/'kernel.elf';elf.write_bytes(b'program')
    build.write_text(json.dumps(dict(workloads=[dict(id='kernel',elf=str(elf),
        elf_sha256=sha256(elf.read_bytes()).hexdigest())])))
    t=tmp_path/'trace.jsonl';trace(t)
    lines=t.read_text().splitlines();header=json.loads(lines[0]);header['elf']=str(elf)
    lines[0]=json.dumps(header);t.write_text('\n'.join(lines)+'\n')
    spec=json.loads(manifest.read_text())
    spec.update(interval=2,max_k=1,warmup=1,seed=1,max_instructions=100,limits=[])
    manifest.write_text(json.dumps(spec))
    monkeypatch.setattr(evaluation,'verify',lambda *a: {'status':'pass'})
    r=evaluation.evaluate(tmp_path/'out',builds={'local':str(build)},manifest=manifest,
                          traces={'kernel':str(t)})
    row=r['workloads'][0]
    assert row['trace_sha256']==sha256(t.read_bytes()).hexdigest()
    assert row['trace_sha256']!=row['models']['model']['model_source_sha256']
    assert row['trace_elf_binding']=='producer_path'
    assert row['models']['model']['ipc']>0
