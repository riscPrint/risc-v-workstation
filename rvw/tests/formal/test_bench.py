from rvw.formal.bench import compare


def rows(a='pass', b='pass', t=1):
    return [{'case':'one', 'engine':'a', 'status':a, 'wall_s':1},
            {'case':'one', 'engine':'b', 'status':b, 'wall_s':t}]


def test_paired_comparison():
    assert compare(rows(t=.5), 'a', 'b')['superior_on_suite']
    assert compare(rows(t=1.04), 'a', 'b')['noninferior_on_suite']
    assert not compare(rows(t=2), 'a', 'b')['noninferior_on_suite']


def test_missing_timeout_disagreement_never_claim_parity():
    for data in ([], rows(b='timeout'), rows(b='fail'), rows()[:1]):
        assert compare(data, 'a', 'b')['status'] == 'inconclusive'


def test_hash_mismatch_launches_no_engine(tmp_path):
    import json
    from argparse import Namespace
    import pytest
    from rvw.formal.bench import run
    (tmp_path / 'dut.sv').write_text('module dut; endmodule')
    manifest = tmp_path / 'suite.json'
    manifest.write_text(json.dumps({'schema':'rvw.formal-bench/1', 'cases':[
        {'id':'dut', 'sources':[{'path':'dut.sv', 'sha256':'0'*64}]}]}))
    out = tmp_path / 'out'
    with pytest.raises(ValueError, match='hash mismatch'):
        run(Namespace(manifest=str(manifest), out=str(out), timeout=1, json=False))
    assert not out.exists()


def test_licensed_adapter_bound_to_request(tmp_path):
    import sys
    import pytest
    from rvw.formal.bench import licensed_adapter
    if not sys.executable.startswith('/'):
        pytest.skip('absolute Python path required')
    script = tmp_path / 'adapter'
    script.write_text('#!' + sys.executable + '\n'
        'import sys,json,hashlib\n'
        'if sys.argv[1] == "--version": print("test adapter 1"); sys.exit(0)\n'
        'p=open(sys.argv[1],"rb").read()\n'
        'r={"schema":"rvw.formal-adapter-response/1","request_sha256":hashlib.sha256(p).hexdigest(),'
        '"status":"pass","mode":"bmc","wall_s":1,"peak_memory_bytes":1024,'
        '"reached_depth":5,"engine_version":"test 1"}\n'
        'open(sys.argv[2],"w").write(json.dumps(r))\n')
    script.chmod(0o755)
    directory = tmp_path / 'run'
    directory.mkdir()
    row = licensed_adapter({'id':'licensed', 'command':str(script)}, [],
                           {'id':'case', 'mode':'bmc'}, directory, 5)
    assert row['status'] == 'pass'
    assert row['evidence_kind'] == 'trusted_adapter_observation'
    script.write_text(script.read_text().replace('hashlib.sha256(p).hexdigest()', '"wrong"'))
    directory = tmp_path / 'bad'
    directory.mkdir()
    row = licensed_adapter({'id':'licensed', 'command':str(script)}, [],
                           {'id':'case', 'mode':'bmc'}, directory, 5)
    assert row['status'] == 'inconclusive'
