"""Native replay bookkeeping controls with an explicit deterministic API fixture."""
import ctypes as C
from pathlib import Path
import pytest
from rvw.cosim.spike import Effect
from rvw.ooo.spike_replay import Api

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def addon():
    path=ROOT/'Cosim/build/libspike_replay.so'
    if not path.exists():pytest.skip('build with Cosim/replay-build.sh')
    lib=C.CDLL(str(path));vp,u64=C.c_void_p,C.c_uint64
    lib.rvw_replay_create.argtypes=[C.POINTER(Api),C.c_char_p,C.POINTER(u64),C.c_size_t,C.POINTER(u64),C.c_size_t,u64,C.c_uint,u64,C.c_char_p,C.c_int,C.c_int]
    lib.rvw_replay_create.restype=vp
    lib.rvw_replay_write.argtypes=[vp,u64,vp,C.c_size_t]
    lib.rvw_replay_step.argtypes=[vp,C.POINTER(Effect),u64,u64,u64,C.c_int]
    lib.rvw_replay_redirect.argtypes=[vp,u64]
    lib.rvw_replay_checkpoint.argtypes=[vp];lib.rvw_replay_checkpoint.restype=vp
    lib.rvw_replay_restore.argtypes=[vp];lib.rvw_replay_restore.restype=vp
    lib.rvw_replay_checkpoint_free.argtypes=[vp];lib.rvw_replay_destroy.argtypes=[vp]
    lib.rvw_replay_error.restype=C.c_char_p
    return lib


def fixture_api():
    states={};serial=[0];entropy=[0];message=C.create_string_buffer(b'fixture failure')
    create_type=C.CFUNCTYPE(C.c_void_p,C.c_char_p,C.POINTER(C.c_uint64),C.c_size_t,
        C.POINTER(C.c_uint64),C.c_size_t,C.c_uint64,C.c_uint,C.c_uint64,C.c_char_p,C.c_int,C.c_int)
    @create_type
    def create(isa,ram,nr,io,ni,pc,pmp,grain,modes,misaligned,absent):
        serial[0]+=1;states[serial[0]]=dict(pc=pc,reg=0,memory={});return serial[0]
    @C.CFUNCTYPE(None,C.c_void_p)
    def destroy(handle):states.pop(handle,None)
    @C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint64,C.POINTER(C.c_uint8),C.c_size_t)
    def write(handle,address,data,n):
        for i in range(n):states[handle]['memory'][address+i]=data[i]
        return 0
    @C.CFUNCTYPE(C.c_int,C.c_void_p,C.POINTER(Effect),C.c_uint64,C.c_uint64,C.c_uint64,C.c_int)
    def step(handle,out,cause,address,value,inject):
        s=states[handle];pc=s['pc'];e=out[0];e.pc=pc;e.pc_next=pc+4;e.insn=0x13;e.mode=3
        if pc==0x2000:
            s['memory'][0x3000]=99;s['reg']=99;e.mem_addr=0x3000;e.mem_wmask=1;e.mem_wdata=99
        elif pc==0x1004:
            s['reg']=s['memory'].get(0x3000,0);e.mem_addr=0x3000;e.mem_rmask=1;e.mem_rdata=s['reg']
        else:s['reg']+=1+entropy[0]
        s['pc']=pc+4;e.rd=1;e.rd_wdata=s['reg'];e.regs[1]=s['reg'];return 0
    @C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint64)
    def redirect(handle,pc):states[handle]['pc']=pc;return 0
    @C.CFUNCTYPE(C.c_void_p)
    def error():return C.addressof(message)
    functions=(create,destroy,write,step,redirect,error)
    api=Api(*(C.cast(f,C.c_void_p).value for f in functions))
    return api,functions,states,entropy


def create_session(lib,api):
    ram=(C.c_uint64*2)(0x1000,0x10000)
    return lib.rvw_replay_create(C.byref(api),b'rv64im',ram,1,None,0,0x1000,0,4,b'M',0,0)


def step(lib,handle):
    e=Effect();assert lib.rvw_replay_step(handle,C.byref(e),0,0,0,0)==0;return e


def test_checkpoint_restores_memory_registers_and_pc(addon):
    api,functions,states,entropy=fixture_api();h=create_session(addon,api)
    saved=None;clones=[]
    try:
        assert addon.rvw_replay_write(h,0x3000,b'A',1)==0
        step(addon,h);saved=addon.rvw_replay_checkpoint(h);assert saved
        assert addon.rvw_replay_redirect(h,0x2000)==0
        assert step(addon,h).mem_wdata==99
        for _ in range(2):
            restored=addon.rvw_replay_restore(saved);assert restored;clones.append(restored)
            e=step(addon,restored)
            assert (e.pc,e.rd_wdata,e.mem_rdata)==(0x1004,65,65)
    finally:
        if saved:addon.rvw_replay_checkpoint_free(saved)
        for item in [h,*clones]:addon.rvw_replay_destroy(item)
    assert not states


def test_nondeterministic_replay_fails_without_returning_partial_state(addon):
    api,functions,states,entropy=fixture_api();h=create_session(addon,api)
    step(addon,h);saved=addon.rvw_replay_checkpoint(h)
    try:
        entropy[0]=1
        assert not addon.rvw_replay_restore(saved)
        assert b'effects differ' in addon.rvw_replay_error()
        assert len(states)==1
    finally:
        addon.rvw_replay_checkpoint_free(saved);addon.rvw_replay_destroy(h)
