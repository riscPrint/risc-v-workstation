"""Wide AXI agent checks used by the native SoC fabric campaign."""
import pytest
from rvw.vip.axi import Address,Write,Pins,Monitor,Manager,Subordinate,Scoreboard,check_address
from rvw.vip.apb import ProtocolError

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('data_bytes',[8,16])
def test_wide_lanes_and_reset(data_bytes):
    model=Subordinate(31,data_bytes=data_bytes)
    def exercise():
        board=Scoreboard(data_bytes)
        monitor=Monitor(board.observe,data_bytes=data_bytes)
        def tick(p):
            result=model.step(p);monitor.sample(result);return result
        manager=Manager(tick,data_bytes=data_bytes)
        address=Address(0x100,id=1,size=data_bytes.bit_length()-1)
        value=int.from_bytes(bytes(range(1,data_bytes+1)),'little')
        assert manager.write(address,[Write(value,(1<<data_bytes)-1)]).response==0
        upper=Address(0x100+data_bytes-1,id=1,size=0)
        assert manager.write(upper,[Write(0xa5 << (8*(data_bytes-1)),1<<(data_bytes-1))]).response==0
        observed=manager.read(address)[0].data
        expected=(value & ((1<<(8*(data_bytes-1)))-1)) | 0xa5<<(8*(data_bytes-1))
        assert observed==expected
        monitor.finish()
        assert board.count==3
    exercise()
    model.step(Pins(reset_n=0))
    exercise()  # Reset must preserve the selected data width.


def test_default_profile_still_rejects_an_eight_byte_beat():
    with pytest.raises(ProtocolError,match='ADDRESS_PROFILE'):
        check_address(Address(0x100,size=3))
    check_address(Address(0x100,size=3),data_bytes=8)


def test_wide_error_responses_survive_reset():
    model=Subordinate(31,data_bytes=8,errors={('write',0x100):2,('read',0x100):3})
    for reset in (False,True):
        if reset:model.step(Pins(reset_n=0))
        manager=Manager(model.step,data_bytes=8)
        address=Address(0x100,size=3)
        assert manager.write(address,[Write(0x1122334455667788,255)]).response==2
        response=manager.read(address)[0]
        assert response.response==3 and response.data==0
