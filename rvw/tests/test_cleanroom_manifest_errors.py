"""Setup errors name the missing project inputs before native work starts."""
import json
from argparse import Namespace
import pytest

pytestmark = pytest.mark.fast


def test_security_empty_manifest_names_the_adapter_and_observations(tmp_path):
    from rvw.sec.campaign import run
    manifest = tmp_path / 'campaign.json'
    manifest.write_text('{}')
    with pytest.raises(ValueError, match='adapter_command.*observations.*INTEGRATION_GUIDE'):
        run(manifest, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_what_if_missing_parameter_names_config_action(tmp_path):
    from rvw.ooo.whatif import what_if
    config = tmp_path / 'timing.json'
    config.write_text('{}')
    with pytest.raises(ValueError, match='issue_width.*existing scalar.*INTEGRATION_GUIDE'):
        what_if(config, tmp_path / 'trace', 'issue_width', 2, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_autocheck_missing_binding_precedes_database_load(tmp_path, capsys):
    from rvw.formal.autocheck import run
    manifest = tmp_path / 'autocheck.json'
    manifest.write_text('{}')
    args = Namespace(manifest=manifest, out=tmp_path/'out', db=tmp_path/'absent.db')
    assert run(args) == 2
    error = json.loads(capsys.readouterr().out)['error']
    assert 'top, verilog' in error
    assert 'INTEGRATION_GUIDE' in error
