"""Offline source/input relocation with a fixture adapter. No RTL claim."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import sys
import zipfile

import pytest
from rvw.common.proc import run_group
from rvw.runs.portable import pack, replay

pytestmark = pytest.mark.fast

ADAPTER = '''import argparse,json,pathlib,hashlib
p=argparse.ArgumentParser();p.add_argument('action');p.add_argument('--elf');p.add_argument('--out');p.add_argument('--seed',type=int);p.add_argument('--max-cycles',type=int);p.add_argument('--config',default='fixture');p.add_argument('--mem-latency',type=int);p.add_argument('--irq-schedule');a,rest=p.parse_known_args()
out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
header=dict(schema='rvw.rvfi/1',xlen=32,core='fixture',config='fixture',isa='rv32i',elf=a.elf)
row=dict(order=0,cycle=1,mode=3,trap=False,halt=False,intr=False,mem_fault=False,pc='0x80000000',pc_next='0x80000004',insn='0x13',rs1=0,rs2=0,rd=0,rs1_rdata='0x0',rs2_rdata='0x0',rd_wdata='0x0',mem_addr='0x0',mem_rmask=0,mem_wmask=0,mem_rdata='0x0',mem_wdata='0x0')
trace=[header,row,dict(event='trap',cycle=2,cause='0x3',tval='0x0',intr=False),dict(event='end',cycle=3,status='fail')]
(out/'rvfi.jsonl').write_text(''.join(json.dumps(r)+'\\n' for r in trace))
result=dict(elf_sha256=hashlib.sha256(pathlib.Path(a.elf).read_bytes()).hexdigest(),schema='rvw.run/1',wall_s=0,tools={},source={},core='fixture',config=a.config,elf=a.elf,seed=a.seed,max_cycles=a.max_cycles,mem_latency=a.mem_latency,status='fail',cycles=3,instret=1,fail_code=3,rtl_sha256='a'*64,artifacts={'rvfi_trace':'rvfi.jsonl'},details={'irq_schedule':a.irq_schedule})
(out/'result.json').write_text(json.dumps(result))
'''


def git(root, *args):
    result = run_group(['git', '-C', str(root), *args], capture=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def failing(tmp_path):
    tools = tmp_path / 'original tools'; tools.mkdir()
    core = tmp_path / 'original core'; core.mkdir()
    (tools / 'adapter.py').write_text(ADAPTER)
    (core / 'core.txt').write_text('source')
    for root in (tools, core):
        git(root, 'init', '-q'); git(root, 'add', '.')
        git(root, '-c', 'user.name=Replay Fixture', '-c', 'user.email=replay@example.invalid', 'commit', '-qm', 'fixture')
    elf = tmp_path / 'program.elf'; elf.write_bytes(b'fixture program')
    run = tmp_path / 'failure'
    command = [sys.executable, str(tools/'adapter.py'), 'run', '--elf', str(elf), '--out', str(run),
               '--seed', '7', '--max-cycles', '100', '--mem-latency', '0', '--irq-schedule', '1:0x0,2:0x80', '--rvfi-trace']
    done = run_group(command, capture=True, timeout=10)
    assert done.returncode == 0, done.stderr
    result = json.loads((run/'result.json').read_text())
    result.update(elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(), replay=shlex.join(command),
                  source=dict(tools_repo=str(tools), tools_rev=git(tools, 'rev-parse', 'HEAD'),
                              core_repo=str(core), core_rev_full=git(core, 'rev-parse', 'HEAD')))
    (run/'result.json').write_text(json.dumps(result))
    recipe = tmp_path/'recipe.json'
    recipe.write_text(json.dumps(dict(schema='rvw.replay-adapter/1', command=['{python}', '{tools}/adapter.py'],
                                     source_env='FIXTURE_CORE', source_inputs={'tools': ['adapter.py', 'extra'], 'core': ['core.txt']})))
    return run, recipe, tools, core


def test_offline_relocation_keeps_seed_stimulus_and_checkpoint(failing, tmp_path):
    run, recipe, tools, core = failing
    (tools/'adapter.py').write_text(ADAPTER+'\n# tracked patch\n')
    (tools/'extra').mkdir(); (tools/'extra/source.txt').write_text('extra source')
    archive = tmp_path/'failure.rvw'
    packed = pack(run, recipe, archive, checkpoint_cycle=2)
    assert packed['checkpoint']['mode'] == 'from-reset'
    shutil.rmtree(tools); shutil.rmtree(core)
    reproduced = replay(archive, tmp_path/'relocated')
    assert reproduced['status'] == 'reproduced'
    assert all(reproduced['checks'].values())
    assert (tmp_path/'relocated/tools/extra/source.txt').read_text() == 'extra source'
    assert (tmp_path/'relocated/tools/adapter.py').read_text().endswith('# tracked patch\n')
    report = json.loads((tmp_path/'relocated/run/result.json').read_text())
    assert report['seed'] == 7 and report['details']['irq_schedule'] == '1:0x0,2:0x80'


def test_corrupt_payload_refuses_before_source_checkout(failing, tmp_path):
    run, recipe, _, _ = failing
    archive = tmp_path/'failure.rvw'; pack(run, recipe, archive)
    damaged = tmp_path/'damaged.rvw'
    with zipfile.ZipFile(archive) as original, zipfile.ZipFile(damaged, 'w') as output:
        for name in original.namelist():
            output.writestr(name, b'changed' if name == 'program.elf' else original.read(name))
    with pytest.raises(ValueError, match='digest mismatch'):
        replay(damaged, tmp_path/'replay')
    assert not (tmp_path/'replay/tools').exists()


@pytest.mark.parametrize('key,value', [('status', 'pass'), ('inconclusive', 'unknown'), ('wall_clock_timeout', True)])
def test_pack_refuses_unearned_or_nondeterministic_evidence(failing, tmp_path, key, value):
    run, recipe, _, _ = failing
    result = json.loads((run/'result.json').read_text()); result[key] = value
    (run/'result.json').write_text(json.dumps(result))
    with pytest.raises(ValueError):
        pack(run, recipe, tmp_path/'bad.rvw')


def test_pack_refuses_changed_elf(failing, tmp_path):
    run, recipe, _, _ = failing
    result = json.loads((run/'result.json').read_text())
    Path(result['elf']).write_bytes(b'different')
    with pytest.raises(ValueError, match='ELF digest'):
        pack(run, recipe, tmp_path/'bad.rvw')


def test_changed_semantic_trace_header_is_not_reproduced(failing, tmp_path):
    run, recipe, tools, _ = failing
    (tools/'adapter.py').write_text(ADAPTER.replace("isa='rv32i'", "isa='rv32im'"))
    archive = tmp_path/'changed-header.rvw'; pack(run, recipe, archive)
    result = replay(archive, tmp_path/'replay')
    assert result['status'] == 'mismatch'
    assert result['checks']['complete_c2']
    assert not result['checks']['c2_header']


@pytest.mark.parametrize('option', ['debug', 'trace-ingress'])
def test_pack_refuses_external_debug_and_trace_bindings(failing, tmp_path, option):
    run, recipe, _, _ = failing
    result = json.loads((run/'result.json').read_text())
    result['replay'] += ' --' + option + ' external'
    (run/'result.json').write_text(json.dumps(result))
    with pytest.raises(ValueError, match='structured input'):
        pack(run, recipe, tmp_path/'bad.rvw')
