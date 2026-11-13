"""`rvw init` with a port mapping: a working C1 adapter from one command.

The generic `riscvsim.MappedAdapter` reads `rvw/core-map.json` (`rvw.core-map/1`). The map
names the top (a no-argument Spinal Component class, or a Verilog module), the memory ports,
the RVFI port prefix, interrupt inputs and constant inputs. Nothing here names a core's signals.
Verilog ports come from Yosys. Spinal ports are checked when the adapter elaborates the top.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import rvw
from .optional import sim_script

PROTOCOLS = {
    'req-rsp': ({'cmd_valid', 'address', 'rsp_valid', 'rdata'},
                {'cmd_ready', 'write', 'wdata', 'mask', 'error', 'rsp_ready'}),
    'valid-ready': ({'valid', 'ready', 'address', 'rdata'}, {'wdata', 'mask'}),
}
INPUT_COMMANDS = '''[
  "ar", "awk", "basename", "cat", "chmod", "cmp", "cp", "cut", "date", "dirname", "du", "env",
  "expr", "find", "getconf", "grep", "head", "hostname", "ld", "ln", "mkdir", "mktemp", "mv", "nice",
  "perl", "ps", "readlink", "realpath", "rm", "rmdir", "sbt", "sed", "sh", "shasum", "sleep",
  "sort", "stat", "tail", "tee", "touch", "tr", "uname", "unzip", "wc", "which", "xargs",
  "zip",
]'''
INPUT_ENV = '''[
  "AR", "BASH_ENV", "CC", "CCACHE_CONFIGPATH", "CCACHE_PATH", "CCACHE_PREFIX",
  "CCC_OVERRIDE_OPTIONS", "CFLAGS", "COMPILER_PATH", "COURSIER_CACHE", "COURSIER_REPOSITORIES",
  "CPATH", "CPLUS_INCLUDE_PATH", "CPP", "CPPFLAGS", "CXX", "CXXFLAGS", "C_INCLUDE_PATH",
  "DEVELOPER_DIR", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "ENV", "GCC_EXEC_PREFIX",
  "GNUMAKEFLAGS", "HOME", "IVY_HOME", "JAVA_HOME", "JAVA_OPTS", "JAVA_TOOL_OPTIONS", "JDK_HOME",
  "JDK_JAVA_OPTIONS", "JVM_OPTS", "LDFLAGS", "LDLIBS", "LD_LIBRARY_PATH", "LD_PRELOAD",
  "LIBRARY_PATH", "LINK", "MACOSX_DEPLOYMENT_TARGET", "MAKE", "MAKEFILES", "MAKEFLAGS",
  "MAKEOVERRIDES", "MFLAGS", "OBJCACHE", "OBJC_INCLUDE_PATH", "OPT", "OPT_FAST", "OPT_GLOBAL",
  "OPT_SLOW", "PATH", "PERL5LIB", "PERL5OPT", "PYTHONHOME", "PYTHONPATH", "RISCVSIM_COVERAGE", "RISCVSIM_REQUIRES",
  "RISCVSIM_CP_CACHE", "RISCVSIM_EXTRA_INPUTS", "RISCVSIM_MAKE", "RISCVSIM_MAKE_JOBS",
  "RISCVSIM_WORK", "RISCVSIM_XMX", "SBT_BOOT_DIRECTORY", "SBT_GLOBAL_BASE", "SBT_IVY_HOME",
  "SBT_JAVA_OPTS", "SBT_OPTS", "SDKROOT", "RVW_HOME", "RVW_CORE_SOURCE", "RVW_CORE_MAP", "SPINAL_MAKE_CMD",
  "SPINAL_VERILATOR_FLAGS", "USER_CPPFLAGS", "USER_LDFLAGS", "USER_LDLIBS", "VERILATOR_BIN",
  "VERILATOR_FLAGS", "VERILATOR_GDB", "VERILATOR_GDBBT", "VERILATOR_NO_OPT", "VERILATOR_ROOT",
  "VFLAGS", "_JAVA_OPTIONS",
]'''
RVFI_FIELDS = ('valid', 'order', 'insn', 'trap', 'halt', 'intr', 'mode', 'rs1_addr', 'rs2_addr', 'rs1_rdata',
               'rs2_rdata', 'rd_addr', 'rd_wdata', 'pc_rdata', 'pc_wdata', 'mem_addr', 'mem_rmask', 'mem_wmask',
               'mem_rdata', 'mem_wdata')


def parse_int(text, what):
    try:
        return int(str(text), 0)
    except ValueError as exc:
        raise ValueError(f'{what} must be an integer (decimal or 0x hex): {text}') from exc


def parse_bus(text):
    """`NAME:PROTOCOL:key=port,key=port[,write_response=1]` -> core-map bus entry."""
    parts = text.split(':', 2)
    if len(parts) != 3:
        raise ValueError(f'--bus must be NAME:PROTOCOL:key=port,...: {text}')
    name, protocol, body = parts
    if protocol not in PROTOCOLS:
        raise ValueError(f'--bus protocol must be one of {", ".join(sorted(PROTOCOLS))}')
    signals, write_response = {}, False
    for item in filter(None, body.split(',')):
        key, sep, port = item.partition('=')
        if not sep or not port:
            raise ValueError(f'--bus item must be key=port: {item}')
        if key == 'write_response':
            write_response = port not in ('0', 'false')
            continue
        signals[key] = port
    return check_bus({'name': name, 'protocol': protocol, 'signals': signals, 'write_response': write_response})


def check_bus(bus):
    required, optional = PROTOCOLS[bus['protocol']]
    missing = required - bus['signals'].keys()
    extra = bus['signals'].keys() - required - optional
    if missing:
        raise ValueError(f'bus {bus["name"]} lacks {", ".join(sorted(missing))}')
    if extra:
        raise ValueError(f'bus {bus["name"]} has unknown keys {", ".join(sorted(extra))}')
    return bus


def verilog_ports(files, top, *, defines=(), yosys='yosys', timeout=120):
    """Top-level ports of a Verilog module, from Yosys JSON: [{name, dir, width}]."""
    if shutil.which(yosys) is None:
        raise ValueError(f'Yosys not found ({yosys}); it reads the Verilog ports. Install the formal tools.')
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'ports.json'
        flags = ' '.join(f'-D{d}' for d in defines)
        reads = '; '.join(f'read_verilog -sv {flags} {json.dumps(str(f))}' for f in files)
        script = f'{reads}; hierarchy -top {top}; proc; write_json {json.dumps(str(out))}'
        result = subprocess.run([yosys, '-q', '-p', script], capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 or not out.exists():
            raise ValueError('Yosys could not read the Verilog top: ' + (result.stderr or result.stdout).strip()[-800:])
        module = json.loads(out.read_text())['modules'].get(top)
    if module is None:
        raise ValueError(f'Yosys found no module {top}')
    ports = []
    for name, port in module['ports'].items():
        if port['direction'] not in ('input', 'output'):
            raise ValueError(f'port {name} is {port["direction"]}; only input and output ports are supported')
        ports.append(dict(name=name, dir='in' if port['direction'] == 'input' else 'out', width=len(port['bits'])))
    return ports


def guess_buses(ports):
    """Buses whose names follow a common pattern. The result is a starting point to review."""
    names = {p['name'] for p in ports}
    buses = []
    for valid in sorted(n for n in names if n.endswith('valid') and not n.startswith('rvfi_')):
        prefix = valid[:-len('valid')]
        def pick(*suffixes):
            return next((prefix + s for s in suffixes if prefix + s in names), None)
        signals = dict(valid=valid, ready=pick('ready'), address=pick('addr', 'address'),
                       rdata=pick('rdata'), wdata=pick('wdata'), mask=pick('wstrb', 'mask', 'be'))
        if all(signals[k] for k in ('ready', 'address', 'rdata')):
            buses.append(dict(name=prefix.strip('_') or 'mem', protocol='valid-ready',
                              signals={k: v for k, v in signals.items() if v}, write_response=False))
    return buses


def link_script(base, size):
    return f'''ENTRY(_start)
MEMORY {{ ram (rwx) : ORIGIN = {hex(base)}, LENGTH = {hex(size)} }}
SECTIONS {{
  .text : {{ *(.text.init) *(.text*) }} > ram
  .data : {{ *(.data*) *(.sdata*) *(.rodata*) *(.srodata*) }} > ram
  .bss : {{ *(.bss*) *(.sbss*) }} > ram
  /DISCARD/ : {{ *(.riscv.attributes) *(.comment) }}
}}
'''


SMOKE = '''/* Smoke program: arithmetic, one load and one store, then tohost = 1. */
.section .text.init
.globl _start
_start:
  li t0, 9
  li t1, 7
  add t2, t0, t1
  li t3, 16
  bne t2, t3, fail
  la t0, scratch
  sw t2, 0(t0)
  lw t3, 0(t0)
  bne t3, t2, fail
  li t1, 1
  j finish
fail:
  li t1, 3
finish:
  la t0, tohost
  sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
scratch: .word 0
'''

RVFI_TEMPLATE = '''// RVFI wiring template (riscv-formal names, NRET 1). Copy into the core's sources and drive
// each field from the core's own retirement logic. MappedAdapter reads the top-level ports
// <prefix>valid, <prefix>order, ... named in rvw/core-map.json ("rvfi": {"prefix": "rvfi_"}).
// Required: valid order insn trap halt intr mode rs1_addr rs2_addr rs1_rdata rs2_rdata
// rd_addr rd_wdata pc_rdata pc_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata.
// Optional: ixl, mem_fault. rd_addr 0 means no register write; rd_wdata is then 0.
import spinal.core._

case class RvfiPort(xlen: Int) extends Bundle {
  val valid = Bool()
  val order = UInt(64 bits)
  val insn = Bits(32 bits)
  val trap, halt, intr = Bool()
  val mode, ixl = Bits(2 bits)
  val rs1_addr, rs2_addr, rd_addr = UInt(5 bits)
  val rs1_rdata, rs2_rdata, rd_wdata = Bits(xlen bits)
  val pc_rdata, pc_wdata, mem_addr = UInt(xlen bits)
  val mem_rmask, mem_wmask = Bits(xlen / 8 bits)
  val mem_rdata, mem_wdata = Bits(xlen bits)
}

// In the top level: val rvfi = out(RvfiPort(32)).setName("rvfi"), then assign every field.
// Spinal names the ports rvfi_valid, rvfi_order, ...
'''


def write_files(root, files, *, force, dry_run, executable=()):
    conflicts = [key for key in files if (root / key).exists() or (root / key).is_symlink()]
    if conflicts and not force:
        raise ValueError('Refusing to overwrite: ' + ', '.join(conflicts) + '. Use --force only for intended replacement.')
    for key in files:
        target = root / key
        if target.is_dir():
            raise ValueError(f'Refusing to replace directory: {target}')
        for parent in target.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f'Parent is not a directory: {parent}')
    if not dry_run:
        for key, content in files.items():
            target = root / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            if key.endswith('.sh') or key in executable:
                target.chmod(0o755)
    return conflicts


def mapped_scaffold(path='.', *, isa, name=None, top=None, verilog_top=None, verilog=(), defines=(),
                    params=(), clock='clk', reset='reset', reset_active='high', buses=(), rvfi_prefix=None,
                    irq=(), constants=(), reset_pc, ram='0x80000000:0x100000', sbt_project=None,
                    accept_platform_defaults=False, yosys='yosys', force=False, dry_run=False):
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError(f'Not a directory: {root}')
    if (top is None) == (verilog_top is None):
        raise ValueError('Select exactly one of --spinal-top (Spinal class) and --verilog-top (Verilog module).')
    isa = (isa or '').lower()
    if re.fullmatch(r'rv(32|64)[ieg][a-z]*(?:_[a-z][a-z0-9]*)*', isa) is None:
        raise ValueError('Supply --isa from the core specification, for example rv32i.')
    xlen = int(isa[2:4])
    name = name or re.sub(r'[^A-Za-z0-9_-]', '-', root.name)
    if re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', name) is None:
        raise ValueError('Core name must start with a letter and contain letters, digits, _ or -.')
    base_text, _, size_text = ram.partition(':')
    base, size = parse_int(base_text, 'RAM base'), parse_int(size_text, 'RAM size')
    reset_value = parse_int(reset_pc, '--reset-pc')
    if size <= 0 or base + size > 1 << xlen or not base <= reset_value < base + size:
        raise ValueError('RAM must fit XLEN and contain the reset PC.')
    bus_list = [parse_bus(b) for b in buses]
    if top is not None:
        if re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', top) is None:
            raise ValueError('--spinal-top must be a fully qualified no-argument Component class.')
        if not (root / 'build.sbt').is_file():
            raise ValueError('--spinal-top needs the core repository build.sbt.')
        if not bus_list:
            raise ValueError('--spinal-top needs at least one --bus: Spinal ports are known only after elaboration.')
        if not sbt_project:
            found = sorted(set(re.findall(r'(?:lazy\s+)?val\s+(\w+)\s*=\s*\(?project\b', (root / 'build.sbt').read_text())))
            if len(found) != 1:
                raise ValueError('Supply --sbt-project with the core project ID.')
            sbt_project = found[0]
        ports = None
        top_entry = {'kind': 'spinal', 'class': top}
    else:
        if not verilog:
            raise ValueError('--verilog-top needs --verilog files.')
        files = [Path(f).resolve() for f in verilog]
        for f in files:
            if not f.is_file():
                raise ValueError(f'Verilog file not found: {f}')
        ports = verilog_ports(files, verilog_top, defines=defines, yosys=yosys)
        names = {p['name'] for p in ports}
        for port in (clock, reset):
            if port not in names:
                raise ValueError(f'clock/reset port {port} is not a port of {verilog_top}')
        if not bus_list:
            bus_list = guess_buses(ports)
            if not bus_list:
                raise ValueError('No bus found by name. Supply --bus NAME:PROTOCOL:key=port,...')
        def relative(f):
            try:
                return str(Path('..') / f.relative_to(root))
            except ValueError:
                return str(f)
        top_entry = {'kind': 'verilog', 'module': verilog_top, 'files': [relative(f) for f in files],
                     'defines': dict((d.split('=', 1) + [''])[:2] for d in defines),
                     'parameters': {k: parse_int(v, f'parameter {k}') for k, v in (p.split('=', 1) for p in params)},
                     'ports': ports, 'clock': clock, 'reset': reset, 'reset_active': reset_active}
        if rvfi_prefix is None and 'rvfi_valid' in names:
            rvfi_prefix = 'rvfi_'
    irq_map = {}
    for item in irq:
        bit, sep, port = item.partition('=')
        if not sep or parse_int(bit, 'interrupt bit') not in (3, 7, 9, 11):
            raise ValueError('--irq must be MIP_BIT=port with bit 3, 7, 9 or 11')
        irq_map[str(parse_int(bit, 'interrupt bit'))] = port
    const_map = {}
    for item in constants:
        port, sep, value = item.partition('=')
        if not sep:
            raise ValueError('--const must be port=value')
        const_map[port] = hex(parse_int(value, f'constant {port}'))
    unmapped = []
    if ports is not None:
        names = {p['name'] for p in ports}
        used = {clock, reset, *irq_map.values(), *const_map}
        for b in bus_list:
            used |= set(b['signals'].values())
        for b in bus_list:
            for port in b['signals'].values():
                if port not in names:
                    raise ValueError(f'bus {b["name"]} names port {port}, which {verilog_top} does not have')
        if rvfi_prefix:
            missing = [f for f in RVFI_FIELDS if rvfi_prefix + f not in names]
            if missing:
                raise ValueError(f'RVFI prefix {rvfi_prefix} lacks ports: ' + ', '.join(rvfi_prefix + f for f in missing))
            used |= {n for n in names if n.startswith(rvfi_prefix)}
        # Inputs no mapping drives are tied to zero and listed for review.
        unmapped = sorted(p['name'] for p in ports if p['dir'] == 'in' and p['name'] not in used)
        for port in unmapped:
            const_map[port] = '0x0'
    core_map = {'schema': 'rvw.core-map/1', 'core': name, 'config': 'default', 'isa': isa, 'xlen': xlen,
                'top': top_entry, 'reset_pc': hex(reset_value), 'ram': {'base': hex(base), 'size': hex(size)},
                'buses': bus_list, 'rvfi': {'prefix': rvfi_prefix} if rvfi_prefix else None,
                'irq': irq_map, 'constants': const_map}
    q = json.dumps
    cache_paths = ['rvw/core-map.json', 'rvw/run.sh', 'rvw/build.sbt', 'rvw/project/build.properties',
                   '${RVW_HOME}/RiscvSim/build.sbt', '${RVW_HOME}/RiscvSim/project/build.properties',
                   '${RVW_HOME}/RiscvSim/src', '${RVW_HOME}/RiscvSim/scripts', '${RVW_HOME}/scripts/with-lock.sh',
                   '${RVW_HOME}/rvw/src/rvw/sim']
    config = f'''[project]
schema = "rvw.project/1"
rvw_version = {q(rvw.__version__)}
root = "."

[core]
name = {q(name)}
adapter = "./rvw/run.sh"
configs = ["default"]
default_config = "default"
source_repo = "."
source_env = "RVW_CORE_SOURCE"
lock = {q(name)}
# The generic mapped adapter's inputs: the map, the launcher and build, RiscvSim and the native tools.
cache_paths = {q(cache_paths)}
identity = true
input_complete = true
identity_capture = true
identity_timeout_s = 1200
input_tools = ["git", "bash", "java", "verilator", "make"]
input_verilator_toolchain = true
input_commands = INPUT_COMMANDS
input_commands_by_platform = {{ darwin = ["xcode-select", "xcrun"] }}
input_env = INPUT_ENV
wall_timeout = true
jobs = 2
build_timeout_s = 3600
startup_s = 300

[suites.smoke]
dir = "rvw/out/programs"
include = ['^smoke$']
max_cycles = 20000
timeout_s = 120
mem_latency = 0

[tiers.quick]
runs = [{{ suite = "smoke" }}]

[cosim]
platform = "rvw/cosim.json"

[query]
build = ["./rvw/build-db.sh"]
db = "rvw/out/design.db"
'''
    config = config.replace('INPUT_COMMANDS', INPUT_COMMANDS).replace('INPUT_ENV', INPUT_ENV)
    info = dict(schema='rvw.adapter/1', core=name, configs=['default'], default_config='default',
                xlen=xlen, isa={'default': isa}, mapped=True)
    info_stub = f'''#!/usr/bin/env bash
# Launcher for the generic mapped adapter (RiscvSim MappedAdapter, rvw/core-map.json).
set -euo pipefail
if [ "${{1:-}}" = info ] && [ "$#" = 2 ] && [ "$2" = --json ]; then
  cat <<'RVW_INFO'
{json.dumps(info)}
RVW_INFO
  exit 0
fi
printf '%s'
'''
    launcher = sim_script(name, info_stub).replace(
        'export RVW_CORE_SOURCE=', 'export RVW_CORE_MAP="$here/core-map.json"\nexport RVW_CORE_SOURCE=').replace(
        ' rvwcore.Main "$@"', ' riscvsim.MappedMain "$@"')
    core_dep = f'ProjectRef(coreSource, {q(sbt_project)}), ' if top is not None else ''
    build = f'''// RVW_HOME selects the installed workstation. The adapter is the generic RiscvSim MappedAdapter.
ThisBuild / scalaVersion := "2.13.14"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
val coreSource = file(sys.env.getOrElse("RVW_CORE_SOURCE", "..")).getCanonicalFile
lazy val root = (project in file("."))
  .dependsOn({core_dep}ProjectRef(workstation / "RiscvSim", "riscvsim"),
    ProjectRef(workstation / "SpinalDB/spinaldb", "spinaldb"))
  .settings(name := "rvw-core-adapter", fork := true)
'''
    march = isa
    abi = 'ilp32' if xlen == 32 else 'lp64'
    smoke_build = f'''#!/usr/bin/env bash
# Build the smoke ELF at the mapped RAM and reset PC.
set -euo pipefail
here="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
prefix="${{RISCV_PREFIX:-riscv64-unknown-elf-}}"
mkdir -p "$here/out/programs"
"${{prefix}}gcc" -march={march} -mabi={abi} -nostdlib -nostartfiles -T "$here/programs/link.ld" \\
  -Wl,--build-id=none "$here/programs/smoke.S" -o "$here/out/programs/smoke"
'''
    if top is not None:
        db = f'''#!/usr/bin/env bash
# C6 entry for the mapped no-argument Component class.
set -euo pipefail
[ "$#" = 2 ] && [ "$1" = default ] || {{ echo 'usage: build-db.sh default OUT' >&2; exit 2; }}
here="$(cd "$(dirname "$0")" && pwd)"
: "${{RVW_HOME:?Set RVW_HOME to the installed workstation}}"
export SPINALDB_PROCESS_RUNNER="$RVW_HOME/SpinalDB/scripts/hdl-deps.py"
export SPINALDB_PYTHON="${{RVW_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}}"
exec "$RVW_HOME/scripts/with-lock.sh" {name} \\
  "$RVW_HOME/scripts/with-lock.sh" sbt nice -n 10 \\
  "$RVW_HOME/SpinalDB/build-db.sh" class {top} "$2" --sbt-dir "$here" --source-root "$here/../src"
'''
    else:
        sources = ' '.join(f'"$here/{f}"' for f in top_entry['files'])
        db = f'''#!/usr/bin/env bash
# C6 navigation entry for the Verilog top (Yosys front end; see rvw query build-hdl).
set -euo pipefail
[ "$#" = 2 ] && [ "$1" = default ] || {{ echo 'usage: build-db.sh default OUT' >&2; exit 2; }}
here="$(cd "$(dirname "$0")" && pwd)"
: "${{RVW_HOME:?Set RVW_HOME to the installed workstation}}"
exec nice -n 10 "${{RVW_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}}" -m rvw query build-hdl \\
  --top {verilog_top} --out "$2" {sources}
'''
    platform = dict(name=name, isa=isa, xlen=xlen, reset_pc=hex(reset_value),
                    ram=[dict(base=hex(base), size=hex(size))], mmio=[],
                    irq_inputs=sorted(int(b) for b in irq_map), privilege_modes='M', aligned_mem=True)
    if not accept_platform_defaults:
        platform['review_required'] = True
    readme = f'''# Core setup playbook (mapped adapter)

`rvw init` wrote a working C1 adapter: the generic RiscvSim `MappedAdapter` reads
`rvw/core-map.json`. Review every entry against the core before trusting a result.

1. Check `isa`, `reset_pc` and `ram` against the core specification.
2. Check each bus mapping and protocol. See RiscvSim/README.md, "Mapped adapter".
3. Check `constants`: unmapped inputs are tied to the listed values.
4. Build the smoke ELF: `rvw/build-smoke.sh`. Then run
   `rvw/run.sh run --elf rvw/out/programs/smoke --out rvw/out/smoke --rvfi-trace --json`.
5. Without RVFI ports, completion comes from bus stores to `tohost` and C2 is unavailable.
   Add RVFI with `rvw/templates/RvfiPort.scala` (Spinal) or the core's riscv-formal ports.
6. Review `rvw/cosim.json` (privilege modes, misaligned policy, PMP, ECALL `tval`).
   {'Remove `review_required` after the review.' if not accept_platform_defaults else 'It uses the platform defaults; check them.'}
7. Run `rvw doctor --json` and `rvw doctor --conformance --json`.
8. Review all result-changing inputs before enabling `input_complete` and `identity`.
9. Commit the project files before a gate.
'''
    files = {'rvw.toml': config, 'rvw/core-map.json': json.dumps(core_map, indent=2) + '\n',
             'rvw/run.sh': launcher, 'rvw/build.sbt': build, 'rvw/project/build.properties': 'sbt.version=1.10.7\n',
             'rvw/build-smoke.sh': smoke_build, 'rvw/programs/smoke.S': SMOKE,
             'rvw/programs/link.ld': link_script(base, size), 'rvw/build-db.sh': db,
             'rvw/cosim.json': json.dumps(platform, indent=2) + '\n', 'rvw/README.md': readme,
             'rvw/.gitignore': '/out/\n/target/\n/project/target/\n/project/project/\n'}
    if top is not None:
        files['rvw/templates/RvfiPort.scala'] = RVFI_TEMPLATE
        files['rvw/templates/CoreProbes.scala'] = PROBE_TEMPLATE
    conflicts = write_files(root, files, force=force, dry_run=dry_run)
    return dict(schema='rvw.init/1', status='planned' if dry_run else 'created', exit_code=0, root=str(root),
                isa=isa, xlen=xlen, mapped=True, files=files, overwritten=conflicts if force else [],
                unmapped_inputs=unmapped, buses=[b['name'] for b in bus_list], rvfi_prefix=rvfi_prefix,
                next=['Review rvw/core-map.json and rvw/cosim.json against the core.',
                      'Run rvw/build-smoke.sh, then rvw regress run --tier quick.',
                      'Run rvw doctor --conformance --json.'])


PROBE_TEMPLATE = """// Copy into the core build, which must depend on SpinalProbes/spinalprobes.
// Call at the real retirement point during elaboration. Probes are off by default.
import spinal.core._
import spinalprobes.Probe

object CoreProbes {
  def apply(retire: Bool, instructionId: UInt): Unit = {
    Probe.retire("commit", retire, instructionId)
    // Add branch, stage and stall probes only from actual core signals.
  }
}
"""
