"""Captured Spike API and additive native functional replay checkpoints."""
import ctypes as C
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from rvw.common.capture import Capture
from rvw.cosim.spike import Effect, FIELDS, capture_shim, load_shim, _SPIKE_LOCK
from rvw.cosim.elf import Elf

ROOT=Path(__file__).resolve().parents[4]


class Api(C.Structure):
    _fields_=[(name,C.c_void_p) for name in ('create','destroy','write','step','redirect','error')]


class Checkpoint:
    def __init__(self,owner,handle):
        self.owner,self.handle,self.regs=owner,handle,list(owner.regs)
    def close(self):
        if self.handle:
            with _SPIKE_LOCK:
                self.owner.lib.rvw_replay_checkpoint_free(self.handle)
            self.handle=None
    def __enter__(self): return self
    def __exit__(self,*args): self.close()


class Replay:
    def __init__(self,platform,elf,shim=None,library=None):
        if 'zkr' in (platform.reference_isa or platform.isa).lower():
            raise ValueError('functional replay does not preserve external entropy sources')
        if platform.reference_extensions:
            raise ValueError('replay sessions do not register custom extensions')
        self.handle=None
        self.temp=tempfile.TemporaryDirectory(prefix='rvw-spike-replay-')
        self.capture=Capture(Path(self.temp.name)/'capture')
        self.platform=platform
        self.elf=Elf(elf)
        if self.elf.xlen!=platform.xlen:
            raise ValueError('ELF and platform XLEN differ')
        base=capture_shim(self.capture,shim or os.environ.get('RVW_SPIKE_SHIM') or ROOT/'Cosim/build/librvw_spike.so')
        self.base=load_shim(base)
        if not hasattr(self.base,'rvw_redirect'):
            raise ValueError('Spike redirect API is missing; rebuild with Cosim/build.sh')
        source=self.capture.file(ROOT/'Cosim/spike_replay.cc')
        lp=Path(library or os.environ.get('RVW_SPIKE_REPLAY') or ROOT/'Cosim/build/libspike_replay.so')
        binary=self.capture.file(lp)
        receipt=self.capture.file(Path(str(lp)+'.manifest.json'))
        manifest=json.loads(receipt.copy.read_text())
        if manifest.get('abi')!=1 or manifest.get('source_sha256')!=source.sha256 or manifest.get('library_sha256')!=binary.sha256:
            raise ValueError('replay add-on identity differs; rebuild with Cosim/replay-build.sh')
        self.lib=lib=C.CDLL(str(binary.copy))
        lib.rvw_replay_abi.restype=C.c_uint
        lib.rvw_replay_effect_size.restype=C.c_size_t
        if lib.rvw_replay_abi()!=1 or lib.rvw_replay_effect_size()!=C.sizeof(Effect):
            raise ValueError('unsupported replay ABI or Effect layout')
        self.api=Api(*(C.cast(getattr(self.base,'rvw_'+name),C.c_void_p).value
                       for name in ('create','destroy','write','step','redirect','error')))
        vp,u64=C.c_void_p,C.c_uint64
        lib.rvw_replay_create.argtypes=[C.POINTER(Api),C.c_char_p,C.POINTER(u64),C.c_size_t,
            C.POINTER(u64),C.c_size_t,u64,C.c_uint,u64,C.c_char_p,C.c_int,C.c_int]
        lib.rvw_replay_create.restype=vp
        for name in ('rvw_replay_destroy','rvw_replay_checkpoint_free'):
            getattr(lib,name).argtypes=[vp]
        lib.rvw_replay_write.argtypes=[vp,u64,vp,C.c_size_t]
        lib.rvw_replay_step.argtypes=[vp,C.POINTER(Effect),u64,u64,u64,C.c_int]
        lib.rvw_replay_redirect.argtypes=[vp,u64]
        lib.rvw_replay_checkpoint.argtypes=[vp];lib.rvw_replay_checkpoint.restype=vp
        lib.rvw_replay_restore.argtypes=[vp];lib.rvw_replay_restore.restype=vp
        lib.rvw_replay_error.restype=C.c_char_p
        def array(regions): return (u64*(2*len(regions)))(*(v for pair in regions for v in pair))
        self.regs=[0]*32
        with _SPIKE_LOCK:
            self.handle=lib.rvw_replay_create(C.byref(self.api),(platform.reference_isa or platform.isa).encode(),
                array(platform.ram),len(platform.ram),array(platform.mmio),len(platform.mmio),platform.reset_pc,
                platform.pmp_regions,platform.pmp_granularity,platform.privilege_modes.encode(),
                int(platform.misaligned['load']=='emulate'),int(platform.absent_pmp_csrs=='read_zero_write_ignored'))
            if not self.handle: raise ValueError(self.error())
            try:
                platform.check_segments(self.elf)
                for address,data,memsz in self.elf.segments:
                    if lib.rvw_replay_write(self.handle,address,data,len(data)): raise ValueError(self.error())
            except BaseException:
                self.close();raise
        self.identity=dict(primary_source_sha256=base['source']['sha256'],
                           primary_library_sha256=base['library']['sha256'],
                           replay_source_sha256=source.sha256,replay_library_sha256=binary.sha256)

    def error(self): return self.lib.rvw_replay_error().decode(errors='replace')
    def close(self):
        if self.handle:
            with _SPIKE_LOCK:self.lib.rvw_replay_destroy(self.handle)
            self.handle=None
        self.temp.cleanup()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def step(self,interrupt=0,mmio=None):
        effect=Effect()
        with _SPIKE_LOCK:
            if not self.handle: raise ValueError('closed replay session')
            if self.lib.rvw_replay_step(self.handle,C.byref(effect),interrupt,*(mmio or (0,0)),int(mmio is not None)):
                raise ValueError(self.error())
        mask=(1<<self.platform.xlen)-1
        result={name:int(getattr(effect,name)) & (0xffffffffffffffff if name=='fd_wdata' else mask) for name in FIELDS}
        result.update(before=list(self.regs),regs=[int(x)&mask for x in effect.regs],
                      disasm=effect.disasm.decode(errors='replace'))
        self.regs=result['regs']
        return result
    def redirect(self,pc):
        with _SPIKE_LOCK:
            if not self.handle: raise ValueError('closed replay session')
            if self.lib.rvw_replay_redirect(self.handle,pc): raise ValueError(self.error())
    def checkpoint(self):
        with _SPIKE_LOCK:
            if not self.handle: raise ValueError('closed replay session')
            handle=self.lib.rvw_replay_checkpoint(self.handle)
            if not handle: raise ValueError(self.error())
            return Checkpoint(self,handle)
    def restore(self,checkpoint):
        if checkpoint.owner is not self or not checkpoint.handle:
            raise ValueError('checkpoint is closed or belongs to another replay session')
        with _SPIKE_LOCK:
            if not self.handle: raise ValueError('closed replay session')
            handle=self.lib.rvw_replay_restore(checkpoint.handle)
            if not handle: raise ValueError(self.error())
            self.lib.rvw_replay_destroy(self.handle)
            self.handle=handle
            self.regs=list(checkpoint.regs)
