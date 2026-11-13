"""ctypes binding to the small Spike public-API shim."""
import ctypes as C
import os
import json
import sys
import threading
from pathlib import Path
from rvw.common.proc import run_group
from rvw.common.capture import CaptureError
from .elf import Elf


FIELDS = "pc pc_next insn mode rd rd_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata trap intr cause tval mem_fault halted fd_valid fd fd_wdata fflags fcsr".split()


class Effect(C.Structure):
    _fields_ = [(k, C.c_uint64) for k in FIELDS] + [("regs", C.c_uint64 * 32), ("disasm", C.c_char * 256)]


# Spike (libriscv) is not thread-safe: concurrent instances in one process corrupt shared state and
# left nearly every signal blocked in other threads (seen on macOS), so later child processes ignored
# SIGTERM. Every call into the shim holds this process-wide lock.
_SPIKE_LOCK = threading.RLock()


class _Serialized:
    """The shim library with each function call made under `_SPIKE_LOCK`."""

    def __init__(self, lib):
        self._lib = lib

    def __getattr__(self, name):
        fn = getattr(self._lib, name)

        def call(*args):
            with _SPIKE_LOCK:
                return fn(*args)
        return call


# The shim behaviour this code expects (Cosim/spike_shim.cc, rvw_shim_version). Bump both together.
SHIM_VERSION = 8
SHIM_SOURCE = Path(__file__).resolve().parents[4] / "Cosim/spike_shim.cc"
REBUILD = "rebuild with Cosim/build.sh"


def capture_shim(capture, path, source=None):
    """Capture the manifest, source, shim and linked Spike bytes exactly once."""
    library = capture.file(Path(path))
    try:
        manifest = capture.file(Path(str(path) + ".manifest.json"))
        built = json.loads(manifest.copy.read_text())
    except CaptureError as exc:
        raise CaptureError(exc.cause, f"no readable build manifest; {REBUILD}") from exc
    source = capture.file(Path(source) if source else SHIM_SOURCE)
    if built.get("shim_version") != SHIM_VERSION:
        raise ValueError(f"Spike shim {path} is version {built.get('shim_version')!r}, this rvw needs "
                         f"{SHIM_VERSION}; {REBUILD}")
    if built.get("shim_source_sha256") != source.sha256:
        raise ValueError(f"Spike shim {path} was built from another spike_shim.cc; {REBUILD}")
    from .build import build_id
    try:
        inputs = built['build_inputs']
        files = {row['source']: row for row in inputs['capture']['files']}
        bound_source = files[inputs['source']]['sha256']
        bound_library = files[inputs['libraries']['riscv']]['sha256']
        valid = (built.get('schema') == 'rvw.spike-build/1'
                 and inputs.get('schema') == 'rvw.spike-build-inputs/1'
                 and build_id(inputs) == built.get('build_id')
                 and bound_source == source.sha256
                 and bound_library == built.get('spike_library_sha256')
                 and built.get('shim_sha256') == library.sha256
                 and built.get('spike_identity') == inputs.get('spike_identity')
                 and bool(inputs['capture']['tools']) and bool(inputs['flags']))
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError(f"Spike shim {path} has an invalid build input binding; {REBUILD}")
    dependency = capture.file(Path(built["spike_library"]))
    if dependency.sha256 != built.get("spike_library_sha256"):
        raise ValueError(f"installed Spike library changed; {REBUILD}")
    record = capture.record()
    def row(item):
        return next(dict(r, copy=str(item.copy)) for r in record["files"]
                    if r["copy"] == item.copy.relative_to(capture.root).as_posix())
    dependency_row = row(dependency)
    load_name = inputs.get('spike_load_name')
    if load_name and not Path(load_name).is_absolute():
        if Path(load_name).name != load_name or load_name in ('.', '..'):
            raise ValueError(f"unsupported Spike load name; {REBUILD}")
        # $ORIGIN resolves beside the captured shim. Hard-link only captured bytes.
        adjacent = library.copy.parent / load_name
        if adjacent == library.copy:
            raise ValueError(f"Spike load name conflicts with shim; {REBUILD}")
        if not adjacent.exists():
            os.link(dependency.copy, adjacent)
        elif not adjacent.samefile(dependency.copy):
            raise CaptureError('input_not_captured:spike_loader', 'conflicting captured dependency')
        dependency_row['copy'] = str(adjacent)
    return {"library": row(library), "manifest": row(manifest), "source": row(source),
            "dependency": dependency_row, "manifest_data": built}


# Keep handles to captured dependencies. A loader may reuse an earlier mapping with the
# same install name. Accept it only if it came from a captured copy with the same bytes.
_DEPENDENCIES = {}
_MAPPING_HASHES = {}
_STEP_SYMBOL = "_ZN11processor_t4stepEm"  # processor_t::step(size_t), Spike's public C++ API


class _DlInfo(C.Structure):
    _fields_ = [("filename", C.c_char_p), ("base", C.c_void_p),
                ("symbol", C.c_char_p), ("address", C.c_void_p)]


def _address(library):
    return C.cast(getattr(library, _STEP_SYMBOL), C.c_void_p).value


def _verify_mapping(function, item):
    address = C.cast(function, C.c_void_p).value
    if address not in _MAPPING_HASHES:
        dladdr = C.CDLL(None).dladdr
        dladdr.argtypes = [C.c_void_p, C.POINTER(_DlInfo)]
        dladdr.restype = C.c_int
        info = _DlInfo()
        if not dladdr(address, C.byref(info)) or Path(os.fsdecode(info.filename)).resolve() != Path(item["copy"]):
            raise CaptureError("input_not_captured:spike_loader", "loader did not map the captured binary")
        _MAPPING_HASHES[address] = item["sha256"]
    if _MAPPING_HASHES[address] != item["sha256"]:
        raise CaptureError("input_not_captured:spike_loader", "loader reused a different binary")


def _load_captured(shim):
    dependency = shim["dependency"]
    digest = dependency["sha256"]
    try:
        if digest not in _DEPENDENCIES:
            native = C.CDLL(dependency["copy"], mode=C.RTLD_GLOBAL)
            address = _address(native)
            _verify_mapping(getattr(native, _STEP_SYMBOL), dependency)
            _DEPENDENCIES[digest] = native, address
        lib = C.CDLL(shim["library"]["copy"])
        if _address(lib) != _DEPENDENCIES[digest][1]:
            raise ValueError("shim did not bind to the captured Spike library")
        return lib
    except (OSError, AttributeError, ValueError) as exc:
        raise CaptureError("input_not_captured:spike_loader", str(exc)) from exc


def load_shim(shim):
    """Load only captured native inputs whose manifest and embedded identity agree."""
    path = shim["library"]["resolved"]
    try:
        with _SPIKE_LOCK:
            lib = _load_captured(shim)
        lib.rvw_shim_version.restype = C.c_uint
        lib.rvw_shim_source_sha256.restype = C.c_char_p
        lib.rvw_shim_build_sha256.restype = C.c_char_p
        with _SPIKE_LOCK:
            _verify_mapping(lib.rvw_shim_version, shim["library"])
        version = int(lib.rvw_shim_version())
        compiled = (lib.rvw_shim_source_sha256() or b"").decode(errors="replace")
        build_identity = (lib.rvw_shim_build_sha256() or b"").decode(errors="replace")
        if build_identity != shim['manifest_data']['build_id']:
            raise ValueError(f"Spike shim {path} has an invalid embedded build input binding; {REBUILD}")
        expected_source = shim["source"]["sha256"]
        if version != SHIM_VERSION or compiled != expected_source:
            raise ValueError(f"Spike shim {path} (version {version}) does not match this rvw "
                             f"(version {SHIM_VERSION}, source {expected_source[:12]}); {REBUILD}")
        return lib
    except AttributeError as exc:
        raise ValueError(f"Spike shim {path} has no version (an old build); {REBUILD}") from exc


class Spike:
    def __init__(self, platform, elf, *, shim):
        from .extensions import has_extension
        for letter in ("v", "h"):
            if has_extension(platform.reference_isa or platform.isa, letter) != has_extension(platform.isa, letter):
                raise ValueError("reference ISA must preserve V/H state requirements")
        self.platform = platform
        self.regs = [0] * 32
        self.elf = Elf(elf)
        if self.elf.xlen != platform.xlen:
            raise ValueError("ELF and platform XLEN differ")
        self.lib = lib = load_shim(shim)
        from .custom import load_extensions
        self.extension_libraries = load_extensions(platform.reference_extensions)
        if platform.reference_extensions:
            lib.rvw_register_extension.argtypes = [C.c_void_p, C.c_char_p]
            lib.rvw_register_extension.restype = C.c_int
        lib.rvw_external_pending.argtypes = [C.c_void_p, C.c_uint64, C.c_uint64]
        lib.rvw_external_pending.restype = None
        lib.rvw_add_hart.argtypes = [C.c_void_p, C.c_uint]
        lib.rvw_select_hart.argtypes = [C.c_void_p, C.c_uint]
        lib.rvw_debug_state.argtypes = [C.c_void_p, C.POINTER(C.c_uint64)]
        lib.rvw_debug_halt.argtypes = [C.c_void_p]
        lib.rvw_error.restype = C.c_char_p
        lib.rvw_create.argtypes = [C.c_char_p, C.POINTER(C.c_uint64), C.c_size_t,
                                  C.POINTER(C.c_uint64), C.c_size_t, C.c_uint64, C.c_uint, C.c_uint64, C.c_char_p, C.c_int, C.c_int]
        lib.rvw_create.restype = C.c_void_p
        lib.rvw_destroy.argtypes = [C.c_void_p]
        lib.rvw_scalar_split_ram.argtypes = [C.c_void_p, C.c_int]
        lib.rvw_write.argtypes = [C.c_void_p, C.c_uint64, C.c_void_p, C.c_size_t]
        lib.rvw_step.argtypes = [C.c_void_p, C.POINTER(Effect), C.c_uint64,
                                C.c_uint64, C.c_uint64, C.c_int]
        lib.rvw_sync_instret.argtypes = [C.c_void_p, C.c_uint64, C.c_uint64]
        lib.rvw_set_reg.argtypes = [C.c_void_p, C.c_uint, C.c_uint64]
        lib.rvw_set_trap_tval.argtypes = [C.c_void_p, C.c_uint64]
        lib.rvw_set_mscratch.argtypes = [C.c_void_p, C.c_uint64]
        if hasattr(lib, "rvw_seed_fcsr"):
            lib.rvw_seed_fcsr.argtypes = [C.c_void_p, C.c_uint64]
        if hasattr(lib, "rvw_external_mip"):
            lib.rvw_external_mip.argtypes = [C.c_void_p, C.c_uint64]
        lib.rvw_read_csr.argtypes = [C.c_void_p, C.c_uint, C.POINTER(C.c_uint64)]
        lib.rvw_read_host_csr.argtypes = [C.c_void_p, C.c_uint, C.POINTER(C.c_uint64)]
        lib.rvw_prv.argtypes = [C.c_void_p]
        lib.rvw_prv.restype = C.c_uint
        if hasattr(lib, "rvw_vector_memory"):
            lib.rvw_vector_memory.argtypes = [C.c_void_p]
            lib.rvw_vector_memory.restype = C.c_char_p
        lib.rvw_vector.argtypes = [C.c_void_p, C.POINTER(C.c_uint64), C.POINTER(C.c_uint8), C.c_size_t]
        lib.rvw_virtual.argtypes = [C.c_void_p, C.c_int]
        lib.rvw_virtual.restype = C.c_uint
        lib.rvw_read_physical.argtypes = [C.c_void_p, C.c_uint64, C.POINTER(C.c_uint64)]
        if hasattr(lib, 'rvw_reset_preserve_ram'):
            lib.rvw_reset_preserve_ram.argtypes = [C.c_void_p, C.c_uint64]
            lib.rvw_reset_preserve_ram.restype = C.c_int
        self.lib = lib = _Serialized(lib)
        def array(rs):
            return (C.c_uint64 * (len(rs)*2))(*(v for r in rs for v in r))
        self.handle = lib.rvw_create((platform.reference_isa or platform.isa).encode(), array(platform.ram), len(platform.ram),
                                     array(platform.mmio), len(platform.mmio), platform.reset_pc,
                                     platform.pmp_regions, platform.pmp_granularity, platform.privilege_modes.encode(),
                                     int(platform.misaligned["load"] == "emulate"),
                                     int(platform.absent_pmp_csrs == "read_zero_write_ignored"))
        if not self.handle:
            raise ValueError(self.error())
        lib.rvw_scalar_split_ram(self.handle, int(platform.scalar_split_ram))
        try:
            for extension in platform.reference_extensions:
                if lib.rvw_register_extension(self.handle, extension["name"].encode()):
                    raise ValueError(self.error())
            platform.check_segments(self.elf)
            for addr, data, memsz in self.elf.segments:
                if lib.rvw_write(self.handle, addr, data, len(data)):
                    raise ValueError(self.error())
        except BaseException:
            self.close()
            raise

    def error(self):
        return self.lib.rvw_error().decode(errors="replace")

    def reset_preserve_ram(self, pc):
        if not hasattr(self.lib, 'rvw_reset_preserve_ram'):
            raise ValueError('reference lacks reset support; rebuild with Cosim/build.sh')
        if self.lib.rvw_reset_preserve_ram(self.handle, pc):
            raise ValueError(self.error())
        self.regs = [0] * 32

    def close(self):
        if self.handle:
            self.lib.rvw_destroy(self.handle)
            self.handle = None

    def environment_inputs(self, levels):
        if self.platform.irq_input_mask & ~0x888:
            raise ValueError('ordered pin replay currently supports machine software, timer and external pins')
        if levels & ~self.platform.irq_input_mask:
            raise ValueError('environment pins exceed declared platform IRQ inputs')
        if not hasattr(self.lib, 'rvw_external_mip'):
            raise ValueError('rebuild Spike shim for ordered external input evidence')
        if self.lib.rvw_external_mip(self.handle, levels):
            raise ValueError(self.error())

    def external_pending(self, mask, levels):
        self.lib.rvw_external_pending(self.handle, mask, levels)

    def step(self, interrupt=0, mmio=None):
        """One reference step. `interrupt` is the cause of a core's interrupt trap event. Only a
        platform input (`irq_inputs`) is injected (for this step; the shim then restores the bit's
        earlier value). Any other interrupt, e.g. SSIP or STIP set by software, is not injected:
        the reference must take it from its own mip/mie state, else the checker reports the step."""
        if interrupt:
            code = interrupt & ~(1 << (self.platform.xlen - 1))
            if code not in self.platform.irq_inputs:
                interrupt = 0
        return self._step_raw(interrupt, mmio)

    def _step_raw(self, interrupt=0, mmio=None):
        from .extensions import has_extension
        if has_extension(self.platform.isa, "h"):
            roots = self.csr_snapshot(["0x280", "0x680"])
            self.translation_context = (bool(self.lib.rvw_virtual(self.handle, 0)), roots["0x280"], roots["0x680"])
        e = Effect()
        if self.lib.rvw_step(self.handle, C.byref(e), interrupt, *(mmio or (0, 0)), int(mmio is not None)):
            raise ValueError(self.error())
        mask = (1 << self.platform.xlen) - 1
        result = {k: int(getattr(e, k)) & (0xffffffffffffffff if k == "fd_wdata" else mask) for k in FIELDS}
        result.update(regs=[int(x) & mask for x in e.regs], before=list(self.regs),
                      disasm=e.disasm.decode(errors="replace"))
        if (result["trap"] and not result["intr"] and result["insn"] == 0x73
                and result["cause"] in (8, 9, 11)):
            wanted = 0x73 if self.platform.ecall_tval == "insn" else 0
            if result["tval"] != wanted:
                self.set_trap_tval(wanted)
                result["tval"] = wanted
        from .extensions import has_extension, H_CSRS
        if has_extension(self.platform.isa, "v"):
            meta = (C.c_uint64 * 7)()
            data = (C.c_uint8 * (32*65536//8))()
            if self.lib.rvw_vector(self.handle, meta, data, len(data)):
                raise ValueError(self.error())
            if hasattr(self.lib, "rvw_vector_memory"):
                import json
                result["vector_accesses"] = json.loads(self.lib.rvw_vector_memory(self.handle))
            self.vector_config = dict(vlen=int(meta[0]), elen=int(meta[1]))
            width = int(meta[0])//8
            result["vector"] = dict(zip(("vstart", "vl", "vtype", "vcsr", "vs"), map(int, meta[2:])))
            result["vector"]["regs"] = [int.from_bytes(bytes(data[r*width:(r+1)*width]), "little") for r in range(32)]
        if has_extension(self.platform.isa, "h"):
            result["hypervisor"] = dict(virtual=bool(self.lib.rvw_virtual(self.handle, 1)),
                virtual_after=bool(self.lib.rvw_virtual(self.handle, 0)), mode_after=self.mode(),
                csrs=self.csr_snapshot([hex(a) for a in H_CSRS], host=True), translations=[])
        result["debug"], _ = self.debug_snapshot()
        self.regs = list(result["regs"])
        return self.platform.normalize_effect(result)

    def add_hart(self, hart):
        if hart != 0 and (self.platform.reference_extensions or self.platform.absent_pmp_csrs != 'trap'):
            raise ValueError('multi-hart custom extensions and absent-PMP emulation are unsupported')
        if not 0 <= hart < 1 << 32:
            raise ValueError('reference hart id exceeds 32 bits')
        if self.lib.rvw_add_hart(self.handle, hart):
            raise ValueError(self.error())

    def select_hart(self, hart):
        if self.lib.rvw_select_hart(self.handle, hart):
            raise ValueError(self.error())

    def debug_snapshot(self):
        values = (C.c_uint64 * 4)()
        if self.lib.rvw_debug_state(self.handle, values):
            raise ValueError(self.error())
        return dict(mode=bool(values[0]), dpc=int(values[1]), dcsr=int(values[2]),
                    step=bool(values[2] & 4)), int(values[3])

    def debug_event(self, action):
        if action == 'halt':
            if self.lib.rvw_debug_halt(self.handle):
                raise ValueError(self.error())
        elif action != 'observe':
            raise ValueError('unsupported debug action')
        state, pc = self.debug_snapshot()
        return dict(debug=state, pc=pc, regs=list(self.regs), disasm='debug ' + action)

    def translations(self, effect):
        from .translation import observations
        return observations(effect, self.translation_context, self.read_physical)

    def read_physical(self, address):
        value = C.c_uint64()
        if self.lib.rvw_read_physical(self.handle, address, C.byref(value)):
            raise ValueError(self.error())
        return value.value

    def sync_instret(self, actual, expected):
        self.lib.rvw_sync_instret(self.handle, actual, expected)

    def seed_fcsr(self, value):
        if not hasattr(self.lib, 'rvw_seed_fcsr'):
            raise ValueError('reference lacks FCSR reset alignment; rebuild with Cosim/build.sh')
        self.lib.rvw_seed_fcsr(self.handle, value)

    def set_mscratch(self, value):
        self.lib.rvw_set_mscratch(self.handle, value)

    def csr_snapshot(self, addresses, *, host=False):
        values = {}
        for address in addresses:
            value = C.c_uint64()
            read = self.lib.rvw_read_host_csr if host else self.lib.rvw_read_csr
            if read(self.handle, int(address, 16), C.byref(value)):
                raise ValueError(self.error())
            values[address] = value.value
        return values

    def mode(self):
        """Privilege mode the model is in now (after the last step)."""
        return int(self.lib.rvw_prv(self.handle))

    def set_trap_tval(self, value):
        self.lib.rvw_set_trap_tval(self.handle, value)

    def set_reg(self, rd, value):
        # Spike stores RV32 GPRs sign-extended in its 64-bit register file.
        native_value = C.c_int32(value).value if self.platform.xlen == 32 else value
        self.lib.rvw_set_reg(self.handle, rd, native_value)
        if rd:
            self.regs[rd] = value


def probe(platform, elf, *, shim=None, executable=None, env=None, pythonpath=None):
    """Spike aborts on bad ISA strings. Contain initialization in a subprocess."""
    env = dict(os.environ if env is None else env)
    env["PYTHONPATH"] = str(pythonpath or Path(__file__).resolve().parents[2])
    result = run_group([str(executable or sys.executable), "-m", "rvw.cosim.spike", "--probe", str(elf),
                        json.dumps(vars(platform)), json.dumps(shim)], capture=True, timeout=15, env=env)
    if result.timed_out:
        raise ValueError("Spike initialization did not finish within 15 s")
    if result.returncode:
        diagnostic = (result.stderr or result.stdout).strip()[-2000:]
        raise ValueError(f"Spike initialization failed ({result.returncode}): {diagnostic}")


if __name__ == "__main__":
    from .platform import Platform
    try:
        model = Spike(Platform(**json.loads(sys.argv[3])), sys.argv[2],
                      shim=json.loads(sys.argv[4]) if len(sys.argv) > 4 else None)
        model.close()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
