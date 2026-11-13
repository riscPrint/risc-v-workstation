"""Campaign case manifests retain adapter files from the input manifest directory."""
import json
import pytest
from rvw.sec import campaign
from test_sec_campaign import manifest

pytestmark = pytest.mark.fast


def test_campaign_resolves_relative_adapter_script(tmp_path):
    path = manifest(tmp_path, classes=['alu'], budget={'pairs': 1, 'seconds': 30})
    data = json.loads(path.read_text())
    data['adapter_command'][1] = 'adapter.py'
    path.write_text(json.dumps(data))
    result = campaign.run(path, tmp_path / 'output')
    assert result['status'] == 'no_leak_observed', result['errors']
    assert result['eligible_pairs'] == 1
