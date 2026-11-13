from rvw.memory.axiomatic import search


def event(i, hart, order, kind, address=0, value=0, **kw):
    row = dict(id=i, hart=hart, order=order, kind=kind, address=address, size=8,
               addr=[], data=[], ctrl=[])
    if kind in ('R', 'LR', 'AMO'):
        row['read'] = value
    if kind in ('W', 'SC', 'AMO'):
        row['write'] = value
    return row | kw


def test_store_buffering_remains_allowed_in_both_models():
    es = [event('a', 0, 0, 'W', 0, 1), event('b', 0, 1, 'R', 8),
          event('c', 1, 0, 'W', 8, 1), event('d', 1, 1, 'R')]
    for model in ('rvwmo', 'ztso'):
        assert search(es, {(0, 8): 0, (8, 8): 0}, model)['status'] == 'allowed'


def test_message_passing_requires_fences_or_tso():
    es = [event('a', 0, 0, 'W', 0, 1), event('b', 0, 2, 'W', 8, 1),
          event('c', 1, 0, 'R', 8, 1), event('d', 1, 2, 'R')]
    init = {(0, 8): 0, (8, 8): 0}
    assert search(es, init)['status'] == 'allowed'
    assert search(es, init, 'ztso')['status'] == 'forbidden'
    es += [event('f', 0, 1, 'FENCE', pred='W', succ='W'),
           event('g', 1, 1, 'FENCE', pred='R', succ='R')]
    assert search(es, init)['status'] == 'forbidden'


def test_acquire_release_and_dependencies_reject_message_violation():
    es = [event('a', 0, 0, 'W', 0, 1), event('b', 0, 1, 'AMO', 8, 0, write=1, rl=True),
          event('c', 1, 0, 'AMO', 8, 1, write=1, aq=True), event('d', 1, 1, 'R')]
    assert search(es, {(0, 8): 0, (8, 8): 0})['status'] == 'forbidden'


def test_indivisible_rmw_rejects_both_amos_reading_initial_value():
    es = [event('a', 0, 0, 'AMO', write=1), event('b', 1, 0, 'AMO', write=2)]
    assert search(es, {(0, 8): 0})['status'] == 'forbidden'
    es[1]['read'] = 1
    assert search(es, {(0, 8): 0})['status'] == 'allowed'


def test_limits_and_unsupported_profiles_are_inconclusive():
    es = [event('a', 0, 0, 'W', value=1), event('b', 1, 0, 'W', value=1),
          event('r', 2, 0, 'R', value=2)]
    assert search(es, {(0, 8): 0})['status'] == 'forbidden'
    es[2]['read'] = 1
    es[2]['size'] = 4
    assert search(es, {(0, 8): 0})['status'] == 'inconclusive'
    es[2]['size'] = 8
    del es[2]['addr']
    assert search(es, {(0, 8): 0})['status'] == 'inconclusive'


def test_coherence_prevents_reading_old_value_after_own_store():
    es = [event('a', 0, 0, 'W', value=1), event('b', 0, 1, 'R')]
    assert search(es, {(0, 8): 0})['status'] == 'forbidden'


def test_search_limit_never_turns_partial_search_into_forbidden():
    es = [event('a', 0, 0, 'AMO', write=1), event('b', 1, 0, 'AMO', write=2)]
    result = search(es, {(0, 8): 0}, limit=1)
    assert result['status'] == 'inconclusive'
    assert result['candidates'] == 1


def test_seeded_concurrent_programs_are_reproducible_and_not_executed():
    from rvw.memory.concurrent import generate
    a = generate(7, 3, 20)
    assert a == generate(7, 3, 20)
    assert a != generate(8, 3, 20)
    assert len(a['programs']) == 3 and not a['executed']
    text = '\n'.join(p['assembly'] for p in a['programs'])
    for instruction in ('lr.d.aq', 'sc.d', 'amoadd.d', 'fence rw, w'):
        assert instruction in text


def test_c2_reader_crosschecks_annotation_bytes_and_requires_dependencies(tmp_path):
    import json
    import pytest
    from rvw.memory.axiomatic import check
    from rvw.cosim.trace import HEX, INT, BOOL
    header = dict(schema='rvw.rvfi/2', xlen=64, isa='rv64ia', core='example', config='two',
                  elf='shared', harts=[0, 1], memory_dependencies='complete', memory_addresses='physical')
    record = {k: '0x0' for k in HEX} | {k: 0 for k in INT} | {k: False for k in BOOL}
    record.update(hart=0, epoch=0, order='0', mode=3, insn='0x3003', mem_rmask=255,
                  memory_model=event('r', 0, 0, 'R'))
    rows = [dict(event='reset', hart=h, epoch=0) for h in (0, 1)] + [record]
    rows += [dict(event='hart_end', hart=h, epoch=0, status='pass') for h in (0, 1)]
    trace = tmp_path / 'trace.jsonl'
    reference = tmp_path / 'initial.json'
    reference.write_text(json.dumps(dict(schema='rvw.axiomatic-initial/1',
                                         locations=[dict(address='0x0', size=8, value='0x0')])))
    def save():
        trace.write_text(json.dumps(header)+'\n'+''.join(json.dumps(r | dict(cycle=i, capture_seq=str(i)))+'\n'
                                                        for i, r in enumerate(rows)))
    save()
    assert check(trace, reference)['status'] == 'allowed'
    record['memory_model'].update(read='0', address='0', order='0')
    save()
    assert check(trace, reference)['status'] == 'allowed'
    initial = json.loads(reference.read_text())
    initial['locations'][0]['value'] = '0xffffffffffffffff'
    reference.write_text(json.dumps(initial))
    record['mem_rdata'] = '0xffffffffffffffff'
    record['memory_model']['read'] = str((1 << 64)-1)
    save()
    assert check(trace, reference)['status'] == 'allowed'
    initial['locations'][0]['value'] = '0x0'
    reference.write_text(json.dumps(initial))
    record['mem_rdata'] = '0x0'
    record['memory_model']['read'] = '00'
    save()
    with pytest.raises(ValueError, match='canonical'):
        check(trace, reference)
    record['memory_model']['read'] = 1
    save()
    with pytest.raises(ValueError, match='bytes'):
        check(trace, reference)
    header.pop('memory_addresses')
    save()
    assert check(trace, reference)['status'] == 'inconclusive'
    header['memory_addresses'] = 'physical'
    header.pop('memory_dependencies')
    save()
    assert check(trace, reference)['status'] == 'inconclusive'


def test_native_generated_fragments_assemble(tmp_path):
    import shutil
    import subprocess
    import pytest
    from rvw.common.proc import run_group
    from rvw.memory.concurrent import generate
    compiler = shutil.which('riscv64-unknown-elf-gcc')
    if not compiler:
        compiler = '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
        from pathlib import Path
        if not Path(compiler).is_file():
            pytest.skip('RISC-V GCC is not installed')
    for program in generate(7, 3, 20)['programs']:
        source = tmp_path / f'hart{program["hart"]}.S'
        source.write_text(program['assembly'])
        output = source.with_suffix('.elf')
        result = run_group(['nice', '-n', '10', compiler, '-x', 'assembler-with-cpp',
                            '-DRVW_SHARED_BASE=0x80010000', '-march=rv64ima', '-mabi=lp64',
                            '-nostdlib', f'-Wl,-Ttext,{hex(0x80000000+4096*program["hart"])}',
                            str(source), '-o', str(output)], timeout=30,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert result.returncode == 0, result.stderr
        assert output.read_bytes().startswith(b'\x7fELF')
