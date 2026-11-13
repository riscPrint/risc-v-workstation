"""Keep all simulation-map fields except selected RX transaction entries."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.reduce.device_rx import reduce_device_rx

pytestmark=pytest.mark.fast


class Command(dict):
    def set(self,**changes):return Command(self,**changes)


def reducer(tmp_path):
    raw=dict(schema='rvw.sim-map/1',regions=[dict(name='ram')],devices=[
        dict(model='ns16550',region='uart',rx=[dict(cycle=30,byte=65),dict(cycle=30,byte=42),dict(cycle=80,byte=66)]),
        dict(model='clint',cycles_per_tick=10)])
    path=tmp_path/'map.json';path.write_text(json.dumps(raw))
    run=SimpleNamespace(artifact=lambda name:path,get=lambda name:hashlib.sha256(path.read_bytes()).hexdigest())
    capture=SimpleNamespace(file=lambda p:SimpleNamespace(copy=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    return SimpleNamespace(best=dict(cmd=Command(soc_map=str(path)),elf='original.elf'),
        run=run,out=tmp_path,trials=[],inputs=SimpleNamespace(capture=capture)),raw


def test_remove_rx_without_changing_order_time_or_device_setup(tmp_path):
    r,original=reducer(tmp_path)
    def search(name,items,command):
        assert name=='uart_rx' and list(items)==[0,1,2]
        cmd,meta=command([1])
        result=json.loads(Path(cmd['soc_map']).read_text())
        assert result['devices'][0]['rx']==[dict(cycle=30,byte=42)]
        result['devices'][0]['rx']=original['devices'][0]['rx']
        assert result==original
        assert meta['elf']=='original.elf' and meta['device_rx_kept']==[1]
        empty,_=command([])
        assert json.loads(Path(empty['soc_map']).read_text())['devices'][0]['rx']==[]
    r._stream_search=search
    reduce_device_rx(r)


def test_changed_map_and_absent_transactions_refuse(tmp_path):
    r,_=reducer(tmp_path)
    r.run.get=lambda name:'0'*64
    with pytest.raises(ValueError,match='digest'):reduce_device_rx(r)
    r,_=reducer(tmp_path)
    r.run.artifact=lambda name:None
    with pytest.raises(ValueError,match='captured'):reduce_device_rx(r)


@pytest.mark.parametrize('actual,expected', [({'1':7},True),({'0':7},False),({},None)])
def test_hart_reduction_preserves_assigned_hart_failure(actual,expected):
    from rvw.reduce.core import Reducer,Options
    class Run(dict):
        inconclusive=None
        @property
        def data(self):return self
    reducer=object.__new__(Reducer)
    reducer.o=Options(modes=['hart_instructions'])
    reducer.run=Run(status='fail',fail_code=7,details={'hart_failures':{'1':7}})
    reducer.sig='fail:7'
    candidate=Run(status='fail',fail_code=7,details={'hart_failures':actual})
    assert reducer.matches(candidate)[0] is expected
