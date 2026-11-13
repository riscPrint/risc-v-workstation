import json

import pytest

from rvw.common.capture import Capture
from rvw.formal.state_overlay import load

pytestmark=pytest.mark.fast


def setup(tmp_path):
    trace=tmp_path/'state.vcd'
    trace.write_text('''$timescale 1ns $end
$scope module dut $end
$var wire 1 ! clk $end
$var reg 1 " q $end
$var reg 1 # extra $end
$upscope $end
$enddefinitions $end
#0
0!
1"
0#
#5
''')
    event_file=tmp_path/'events.json'
    event_file.write_text('{}')
    inputs=tmp_path/'inputs'
    inputs.mkdir()
    (inputs/'temporal.sv').write_text('module m; endmodule')
    model={'m':dict(ports={'clk':dict(direction='input',bits=[1])},
                    netnames={'q':dict(bits=[2]),'extra':dict(bits=[3])},
                    cells={'ff':dict(type='$dff',connections={'Q':[2],'CLK':[1]})})}
    (tmp_path/'module_ports.json').write_text(json.dumps(dict(modules=model)))
    capture=Capture(tmp_path/'capture')
    item=capture.file(event_file)
    return capture,item,model


def run(tmp_path,capture,item,model,names=('q',)):
    (tmp_path/'module_ports.json').write_text(json.dumps(dict(modules=model)))
    lines=[]
    for module,definition in model.items():
        lines.append('module \\'+module)
        for index,cell in enumerate(definition.get('cells',{}).values()):
            if cell['type'].startswith(('$dff','$adff','$sdff','$ff')):
                wires=[name for name,net in definition.get('netnames',{}).items()
                       if set(cell['connections']['Q'])<=set(net['bits'])]
                lines += ['  cell '+cell['type']+' ff'+str(index),
                          '    connect \\Q \\'+wires[0], '  end']
        lines.append('end')
    (tmp_path/'module_ports.il').write_text('\n'.join(lines)+'\n')
    return load(dict(trace='state.vcd' ,time=5,scope='dut',registers=list(names)),capture,item,tmp_path,
                'm',dict(clk=1),dict(clk='0'),1)


def test_complete_state(tmp_path):
    capture,item,model=setup(tmp_path)
    result=run(tmp_path,capture,item,model)
    assert result['state_bits']==1
    assert result['registers']==[dict(signal='q',width=1,value='1')]
    assert len(result['trace_sha256'])==64


def test_hierarchy_requires_child_paths_and_memory_is_refused(tmp_path):
    capture,item,model=setup(tmp_path)
    model['child']=model['m'].copy()
    model['m']['cells']={'inst':dict(type='child')}
    with pytest.raises(ValueError,match='does not map to DUT register bits'):
        run(tmp_path,capture,item,model)
    model['m']['cells']={'memory':dict(type='$mem_v2')}
    with pytest.raises(ValueError,match='does not yet load memories'):
        run(tmp_path,capture,item,model)


def test_register_alias_cannot_replace_state(tmp_path):
    capture,item,model=setup(tmp_path)
    model['m']['netnames']['extra']=dict(bits=[2])
    with pytest.raises(ValueError,match='does not map to DUT register bits'):
        run(tmp_path,capture,item,model,('extra',))


def test_monitor_registers_excluded_but_alias_wires_are_not(tmp_path):
    capture,item,model=setup(tmp_path)
    model['m']['netnames']['rvw_sva_0_0_h0']=dict(bits=[3])
    model['m']['cells']['history']=dict(type='$dff',connections={'Q':[3],'CLK':[1]})
    (tmp_path/'inputs/temporal.sv').write_text('reg [($bits(payload[1:0]))-1:0] rvw_sva_0_0_h0;')
    assert run(tmp_path,capture,item,model)['state_bits']==1
    (tmp_path/'inputs/temporal.sv').write_text('wire rvw_sva_0_0_h0;')
    with pytest.raises(ValueError,match='incomplete trace register state'):
        run(tmp_path,capture,item,model)


def test_declared_wire_is_not_loaded_as_register(tmp_path):
    capture,item,model=setup(tmp_path)
    model['m']['netnames']['clk']=dict(bits=[2])
    with pytest.raises(ValueError,match='needs a trace variable'):
        run(tmp_path,capture,item,model,('clk',))


def test_selected_registers_are_exact(tmp_path):
    capture,item,model=setup(tmp_path)
    with pytest.raises(ValueError,match='does not map to DUT register bits'):
        run(tmp_path,capture,item,model,('extra',))
    with pytest.raises(ValueError,match='once'):
        run(tmp_path,capture,item,model,('q','q'))


def test_repeated_child_instances_have_distinct_state(tmp_path):
    capture,item,model=setup(tmp_path)
    child=model['m'].copy()
    model['child']=child
    model['m']['cells']={'left':dict(type='child'),'right':dict(type='child')}
    path=tmp_path/'state.vcd'
    text=path.read_text().replace('$upscope $end',
        '$scope module left $end\n$var reg 1 $ q $end\n$upscope $end\n'
        '$scope module right $end\n$var reg 1 % q $end\n$upscope $end\n$upscope $end')
    text=text.replace('#5','1$\n0%\n#5')
    path.write_text(text)
    result=run(tmp_path,capture,item,model,('left.q','right.q'))
    assert result['state_bits']==2
    assert [row['value'] for row in result['registers']]==['1','0']


def test_black_box_state_refused(tmp_path):
    capture,item,model=setup(tmp_path)
    model['child']=dict(attributes={'blackbox':'0'*31+'1'},ports={},netnames={},cells={})
    model['m']['cells']['box']=dict(type='child')
    with pytest.raises(ValueError,match='black-box state'):
        run(tmp_path,capture,item,model)
