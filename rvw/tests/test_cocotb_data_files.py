import json
import pytest
from rvw.sim.cocotb import load
pytestmark=pytest.mark.fast


def test_memory_image_paths_and_duplicate_names(tmp_path):
    (tmp_path/'core.v').write_text('module Core; endmodule')
    (tmp_path/'image.bin').write_text('01010101\n')
    spec=dict(schema='rvw.cocotb/1',name='memory',backend='verilator',top='Core',
              sources=['core.v'],test_module='test_core',data_files=['image.bin'])
    path=tmp_path/'bench.json';path.write_text(json.dumps(spec))
    assert load(path)['data_files']==[str(tmp_path/'image.bin')]
    spec['data_files']*=2;path.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='distinct basenames'):load(path)
