from rvw.formal.ric3_compat import translate, wrapper
import subprocess


def test_bound_and_quiet_translation():
    assert translate(['--bmc-max-k', '19', '-e', 'bmc', '-v', '0', '--witness', 'model.aig']) == [
        '--end', '19', '-e', 'bmc', '--witness', 'model.aig']
    assert translate(['--rseed', '7']) == ['--rseed', '7']


def test_wrapper_executes_actual_engine(tmp_path, monkeypatch):
    import sys
    engine = tmp_path / 'fake-engine'
    engine.write_text('#!' + sys.executable + '\nimport sys\nprint(repr(sys.argv[1:]))\n')
    engine.chmod(0o755)
    shim = wrapper(tmp_path, str(engine))
    monkeypatch.setenv('PYTHONEXECUTABLE', '/invalid/python')
    monkeypatch.setenv('PYTHONHOME', '/invalid/home')
    result = subprocess.check_output([str(shim), '--bmc-max-k', '4', '-v', '0'], text=True)
    assert result.strip() == "['--end', '4']"
