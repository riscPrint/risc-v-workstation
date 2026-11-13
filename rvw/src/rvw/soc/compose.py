"""Generate a bounded SoC from a validated map, bus ingress and explicit binders."""
import hashlib
import struct
import json
import re
from pathlib import Path

from .model import dumps, generate, keys, load, number


def scala_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*', value):
        raise ValueError('invalid qualified Scala class name')
    return value


def compose(source, out, elf=None):
    source = Path(source).resolve()
    from .configuration import configuration
    spec, fragments = configuration(source)
    required = {'schema', 'map', 'core', 'clock_hz', 'reset', 'devices'}
    keys(spec, required | {'domains'}, required)
    if spec['schema'] != 'rvw.soc-compose/1':
        raise ValueError('unsupported composition schema')
    keys(spec['core'], {'class', 'bus', 'exports'}, {'class', 'bus'})
    core = scala_name(spec['core']['class'])
    bus = spec['core']['bus']
    if bus not in ('apb3', 'axi4', 'axi4-lite', 'tilelink', 'simple'):
        raise ValueError('core bus must be apb3, axi4, axi4-lite, tilelink or simple')
    byte_writes = bus != 'apb3'
    if type(spec['clock_hz']) is not int or spec['clock_hz'] <= 0 or spec['reset'] not in ('sync_high', 'async_high'):
        raise ValueError('positive clock_hz and sync_high or async_high reset required')
    obj = load(source.parent / spec['map'])
    if obj['address_bits'] != 32 or obj['platform']['xlen'] != 32:
        raise ValueError('first composition profile requires RV32 and 32 address bits')
    if not isinstance(spec['devices'], dict):
        raise ValueError('devices must map every region name to a binder')
    if set(spec['devices']) != {r['name'] for r in obj['regions']}:
        raise ValueError('every region needs exactly one device binder')
    domains = spec.get('domains', {})
    if not isinstance(domains, dict):
        raise ValueError('domains must be a dictionary')
    for name, domain in domains.items():
        if not re.fullmatch('[A-Za-z][A-Za-z_0-9]*', name) or name in {'core', 'io', 'fabricBus'} or name in spec['devices']:
            raise ValueError('invalid domain name')
        keys(domain, {'clock_hz', 'reset'}, {'clock_hz', 'reset'})
        if type(domain['clock_hz']) is not int or domain['clock_hz'] <= 0 or domain['reset'] not in ('sync_high', 'async_high'):
            raise ValueError('domain needs positive clock_hz and reset kind')
    images = {}
    elf_hash = None
    if elf:
        raw = Path(elf).read_bytes()
        elf_hash = hashlib.sha256(raw).hexdigest()
        if len(raw) < 52 or raw[:7] != b'\x7fELF\x01\x01\x01':
            raise ValueError('ELF must be little-endian RV32')
        header = struct.unpack_from('<16sHHIIIIIHHHHHH', raw)
        if header[2] != 243 or header[9] != 32:
            raise ValueError('ELF must use RISC-V and 32-byte program headers')
        for i in range(header[10]):
            pos = header[5] + i * 32
            if pos + 32 > len(raw):
                raise ValueError('truncated ELF program header')
            kind, offset, vaddr, base, filesz, size, flags, align = struct.unpack_from('<IIIIIIII', raw, pos)
            if kind != 1 or not size:
                continue
            matches = [r for r in obj['regions'] if r['kind'] == 'ram' and r['base'] <= base and base + size <= r['base'] + r['size']]
            if len(matches) != 1 or filesz > size or offset + filesz > len(raw):
                raise ValueError('ELF load segment must fit one memory region and input')
            r = matches[0]
            if r['size'] > 1024 * 1024:
                raise ValueError('bounded word-memory profile supports at most 1 MiB per window')
            buf = images.setdefault(r['name'], bytearray(r['size']))
            offset_in_region = base - r['base']
            buf[offset_in_region:offset_in_region+size] = raw[offset:offset+filesz] + bytes(size - filesz)
    lines = ['package generated', 'import spinal.core._', 'import spinal.lib._',
             'import spinal.lib.bus.amba3.apb._', 'import spinal.lib.bus.misc.SizeMapping',
             'import rvwsoc._', 'class ComposedSoc extends Component {',
             f'  val core = new {core}()', '  core.debugReset := False']
    exports = spec['core'].get('exports', [])
    if not isinstance(exports, list):
        raise ValueError('core exports must be a list of IO member names')
    for port in exports:
        if not isinstance(port, str) or not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', port) or port in ('bus', 'interrupts', 'debugReset'):
            raise ValueError('invalid exported core port')
        lines += [f'  val core_{port} = core.io.{port}.toIo()']
    if byte_writes:
        lines += ['  val fabricBus = BusIngress(core.bus)']
    for name, domain in domains.items():
        lines += [f'  val {name}_clk = in Bool()', f'  val {name}_reset = in Bool()',
                  f'  val {name}_domain = ClockDomain({name}_clk, {name}_reset, config = ClockDomainConfig(resetKind = {"SYNC" if domain["reset"] == "sync_high" else "ASYNC"}), frequency = FixedFrequency({domain["clock_hz"]} Hz))']
    targets, irq = [], []
    memories = []
    for r in obj['regions']:
        name, size = r['name'], r['size']
        if name in ('core', 'io') or (byte_writes and name == 'fabricBus'):
            raise ValueError('region name conflicts with generated top member')
        if size < 4 or size >= 1 << 32:
            raise ValueError('APB3 windows must be 4 bytes to 2 GiB')
        binder = spec['devices'][name]
        keys(binder, {'type', 'class', 'exports', 'irq', 'domain'}, {'type'})
        domain = binder.get('domain')
        if domain is not None and domain not in domains:
            raise ValueError('binder names an unknown domain')
        if binder['type'] in ('ram', 'rom'):
            if r['kind'] != 'ram' or ('w' in r['permissions']) != (binder['type'] == 'ram'):
                raise ValueError('memory binder must match map permissions and kind')
            if size > 1024 * 1024:
                raise ValueError('bounded word-memory profile supports at most 1 MiB per window')
            image = images.get(name, b'').rstrip(b'\0')
            image += bytes((-len(image)) % 4)
            values = ','.join(f'BigInt("{int.from_bytes(image[i:i+4], "little"):x}",16)' for i in range(0, len(image), 4))
            memory_extra = ', byteWrites = true' if byte_writes else ''
            lines += [f'  val {name} = new WordMemory({size.bit_length()-1}, {size//4}, {str(binder["type"] == "rom").lower()}, Seq({values}){memory_extra})']
            memories.append(dict(name=name, width=32, depth=size//4, read_only=binder['type']=='rom'))
        elif binder['type'] == 'project':
            if r['kind'] != 'mmio':
                raise ValueError('project peripheral needs an MMIO region')
            lines += [f'  val {name} = new {scala_name(binder["class"])}()']
        else:
            raise ValueError('unsupported binder type')
        if domain is not None:
            creation = lines.pop().replace(f'val {name} =', 'val device =')
            lines += [f'  val {name}_area = new ClockingArea({domain}_domain) {{', creation, '  }',
                      f'  val {name} = {name}_area.device']
        for port in binder.get('exports', []):
            if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', port) or port in ('bus','irq'):
                raise ValueError('invalid exported peripheral port')
            lines += [f'  val {name}_{port} = {name}.io.{port}.toIo()']
        endpoint = f'{name}.io.bus'
        if byte_writes and binder['type'] == 'project':
            lines += [f'  val {name}_port = Apb3(Apb3Config({size.bit_length()-1}, 32, useStrb = true))',
                      f'  BusIngress.legacy({name}_port, {name}.io.bus)']
            endpoint = f'{name}_port'
        if domain is not None:
            lines += [f'  val {name}_crossing = Apb3({endpoint}.config)',
                      f'  {endpoint} << BusClockCrossing({name}_crossing, {domain}_domain)']
            endpoint = f'{name}_crossing'
        targets.append(f'({endpoint}, SizeMapping(BigInt("{r["base"]:x}",16), BigInt("{size:x}",16)))')
    for cause in range(32):
        sources = []
        for i in obj['interrupts']:
            if i['cause'] == cause:
                port = spec['devices'][i['region']].get('irq', {}).get(i['name'], 'irq')
                if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', port):
                    raise ValueError('invalid interrupt port')
                signal = f'{i["region"]}.io.{port}'
                if spec['devices'][i['region']].get('domain') is not None:
                    signal = f'BufferCC({signal}, init = False)'
                sources.append(signal)
        irq += [f'  core.interrupts({cause}) := ' + (' || '.join(sources) or 'False')]
    lines += irq + ['  Fabric.connect(' + ('fabricBus' if byte_writes else 'core.bus') + ', Seq(' + ','.join(targets) + '))', '}',
                    'object Generate extends App {',
                    f'  SpinalConfig(targetDirectory = args.headOption.getOrElse("rtl"), defaultClockDomainFrequency = FixedFrequency({spec["clock_hz"]} Hz), defaultConfigForClockDomains = ClockDomainConfig(resetKind = {"SYNC" if spec["reset"] == "sync_high" else "ASYNC"})).generateVerilog(new ComposedSoc)', '}']
    target = Path(out)
    if target.exists():
        raise ValueError('output directory must be new')
    # Validate software exports before publishing generated source.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        generate(source.parent / spec['map'], tmp)
    target.mkdir(parents=True)
    files = generate(source.parent / spec['map'], target)
    from .software import board_dts, linker
    (target / 'board.dts').write_text(board_dts(obj, spec))
    files.append('board.dts')
    script = linker(obj)
    if script is not None:
        (target / 'link.ld').write_text(script)
        files.append('link.ld')
    if any(r['registers'] for r in obj['regions']):
        from .exports import ipxact
        (target / 'registers.ipxact.xml').write_text(ipxact(obj))
        files.append('registers.ipxact.xml')
    (target / 'ComposedSoc.scala').write_text('\n'.join(lines) + '\n')
    manifest = dict(schema='rvw.soc-composed/1', profile=f'{bus}-rv32-' + ('byte' if byte_writes else 'word'),
                    clock_hz=spec['clock_hz'], reset=spec['reset'], domains=domains, memories=memories,
                    map_sha256=hashlib.sha256((source.parent / spec['map']).read_bytes()).hexdigest(),
                    composition_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), elf_sha256=elf_hash,
                    fragments=fragments, effective_configuration=spec,
                    validation='generated_only', bus_ports=['core.bus'] + [r['name']+'.io.bus' for r in obj['regions']])
    (target / 'composition.json').write_text(dumps(manifest))
    return dict(status='generated', files=sorted(files + ['ComposedSoc.scala', 'composition.json']), profile=manifest['profile'])
