from pathlib import Path
import pytest
from rvw.uvm.flow import build


@pytest.mark.parametrize('feature,diagnostic',[
    ('hdl_backdoor','unsupported:uvm_hdl_backdoor'),
    ('vpi_polling','unsupported:uvm_vpi_polling'),
    ('commercial_vip','unsupported:uvm_commercial_vip'),
    ('four_state','unsupported:uvm_four_state'),
    ('advanced_constraints','unsupported:uvm_advanced_constraints'),
    ('advanced_coverage','unsupported:uvm_advanced_coverage'),
    ('unknown','unsupported:uvm_unknown_feature'),
])
def test_requirements_refused_before_build_or_output(tmp_path,feature,diagnostic):
    with pytest.raises(ValueError,match=diagnostic):
        build(tmp_path/'absent.json',tmp_path/'out',required_features=[feature])
    assert not (tmp_path/'out').exists()


def test_cli_requirement(tmp_path,capsys):
    from rvw.cli import main
    code=main(['uvm','build',str(tmp_path/'absent.json'),'--out',str(tmp_path/'out'),
               '--require-feature','hdl_backdoor'])
    assert code == 2
    assert 'unsupported:uvm_hdl_backdoor' in capsys.readouterr().out
