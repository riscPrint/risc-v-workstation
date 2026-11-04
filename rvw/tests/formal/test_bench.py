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
                           {'id':'case', 'mode':'bmc', 'depth':6}, directory, 5)
    assert row['status'] == 'pass'
    assert row['evidence_kind'] == 'trusted_adapter_observation'
    script.write_text(script.read_text().replace('hashlib.sha256(p).hexdigest()', '"wrong"'))
    directory = tmp_path / 'bad'
    directory.mkdir()
    row = licensed_adapter({'id':'licensed', 'command':str(script)}, [],
                           {'id':'case', 'mode':'bmc', 'depth':6}, directory, 5)
    assert row['status'] == 'inconclusive'


def test_missing_licensed_response_is_inconclusive(tmp_path):
    import sys
    from rvw.formal.bench import licensed_adapter
    script = tmp_path / 'adapter'
    script.write_text('#!' + sys.executable + '\nimport sys\n'
                      'if sys.argv[1] == "--version": print("test 1")\n')
    script.chmod(0o755)
    row = licensed_adapter({'id':'licensed', 'command':str(script)}, [],
                           {'id':'case', 'mode':'bmc'}, tmp_path, 5)
    assert row['status'] == 'inconclusive'


def test_benchmark_records_disagreement_and_unknown(tmp_path, monkeypatch):
    import json
    from argparse import Namespace
    from hashlib import sha256
    from rvw.formal import bench
    rtl = b'module dut(input clk,reset); endmodule'
    (tmp_path / 'dut.sv').write_bytes(rtl)
    manifest = tmp_path / 'suite.json'
    manifest.write_text(json.dumps({'schema':'rvw.formal-bench/1', 'baseline':'a', 'cases':[
        {'id':'one', 'top':'dut','clock':'clk','reset':'reset','depth':5,'mode':'bmc',
         'sources':[{'path':'dut.sv','sha256':sha256(rtl).hexdigest()}]}]}))
    monkeypatch.setattr(bench, 'ENGINES', {'a':'a', 'b':'b', 'c':'c'})
    monkeypatch.setattr(bench.shutil, 'which', lambda s: '/bin/'+s)
    monkeypatch.setattr(bench, 'measure', lambda sources,case,engine,target,timeout:
                        {'status':{'a':'pass','b':'fail','c':'timeout'}[engine], 'wall_s':1})
    out = tmp_path / 'out'
    assert bench.run(Namespace(manifest=manifest, out=out, timeout=5,json=False)) == 1
    result = json.loads((out / 'result.json').read_text())
    assert result['agreement'] == [{'case':'one', 'status':'disagree'}]
    assert result['comparisons']['b']['status'] == 'inconclusive'


def test_proof_mode_does_not_launch_bounded_btor_engines(tmp_path, monkeypatch):
    import json
    from argparse import Namespace
    from hashlib import sha256
    from rvw.formal import bench
    data = b'module dut(input clk, reset); endmodule'
    (tmp_path / 'dut.sv').write_bytes(data)
    manifest = tmp_path / 'suite.json'
    manifest.write_text(json.dumps({'schema':'rvw.formal-bench/1', 'cases':[
        {'id':'one','top':'dut','clock':'clk','reset':'reset','depth':5,'mode':'prove',
         'sources':[{'path':'dut.sv','sha256':sha256(data).hexdigest()}]}]}))
    monkeypatch.setattr(bench, 'ENGINES', {'btor:pono':'pono','btor:btormc':'btormc'})
    monkeypatch.setattr(bench.shutil, 'which', lambda s: '/bin/'+s)
    def unexpected(*args):
        raise AssertionError('incompatible engine was launched')
    monkeypatch.setattr(bench, 'measure', unexpected)
    out = tmp_path / 'out'
    bench.run(Namespace(manifest=manifest, out=out, timeout=5,json=False))
    result = json.loads((out / 'result.json').read_text())
    assert all(row['status'] == 'unsupported_mode' for row in result['rows'])


def test_error_measurement_retains_native_memory_and_log(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from rvw.formal import bench
    monkeypatch.setattr(bench, 'run_group', lambda *a, **k: SimpleNamespace(
        returncode=2, timed_out=False, stdout='', stderr='4096 maximum resident set size'))
    monkeypatch.setattr(bench.sys, 'platform', 'darwin')
    case = {'mode':'bmc','top':'dut','clock':'clk','reset':'reset','depth':5}
    result = bench.measure([], case, 'abc:bmc3', tmp_path / 'job', 1)
    assert result['status'] == 'error'
    assert result['peak_memory_bytes'] == 4096
    assert (tmp_path / 'job.measurement.log').exists()


def test_adapter_bounded_pass_requires_requested_depth(tmp_path):
    import sys
    from rvw.formal.bench import licensed_adapter
    script = tmp_path / 'adapter'
    script.write_text('#!' + sys.executable + '\n'
        'import sys,json,hashlib\n'
        'if sys.argv[1] == "--version": print("test adapter 1"); sys.exit(0)\n'
        'p=open(sys.argv[1],"rb").read()\n'
        'r={"schema":"rvw.formal-adapter-response/1","request_sha256":hashlib.sha256(p).hexdigest(),'
        '"status":"pass","mode":"bmc","wall_s":1,"peak_memory_bytes":1024,'
        '"reached_depth":2,"engine_version":"test 1"}\n'
        'open(sys.argv[2],"w").write(json.dumps(r))\n')
    script.chmod(0o755)
    row = licensed_adapter({'id':'licensed', 'command':str(script)}, [],
                           {'id':'case', 'mode':'bmc', 'depth':10}, tmp_path / 'run', 5)
    assert row['status'] == 'inconclusive'
