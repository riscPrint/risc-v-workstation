"""Compare a bounded C2 window after a boot checkpoint with Spike.

Spike executes the prefix from the original ELF and payloads. Only recorded
counter values, device responses and interrupt inputs synchronize it. Ordinary
RTL registers and checkpoint RAM never seed the reference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from time import perf_counter
from rvw.common.capture import Capture
from rvw.common.riscv import integer_sources
from rvw.cosim.checker import counter_read, differences, masked, c2_view
from rvw.cosim.external_interrupts import validate
from rvw.cosim.platform import Platform
from rvw.cosim.spike import Spike, capture_shim
from rvw.cosim.trace import Trace


def snapshot(path):
    with zipfile.ZipFile(path) as archive:
        envelope = json.loads(archive.read('state.json'))
    state = envelope['state']
    # The Scala writer hashes compact insertion-ordered UTF-8 JSON.
    encoded = json.dumps(state, separators=(',', ':'), ensure_ascii=False).encode()
    if hashlib.sha256(encoded).hexdigest() != envelope['sha256']:
        raise ValueError('checkpoint state digest differs')
    if state['schema'] != 'rvw.vexii-boot-slice/1':
        raise ValueError('unsupported checkpoint')
    return state


def validate_window(header, rows, before, end):
    window = header['window']
    first, last = int(window['from_cycle']), min(int(window['to_cycle']), int(end['cycle']))
    if first < int(before['cycle']) or first >= last:
        raise ValueError('trace window does not follow the starting checkpoint')
    if not rows or rows[-1].get('event') != 'end' or rows[-1]['cycle'] != last:
        raise ValueError('trace end differs from the captured window')
    actual = [(row['cycle'], row['cause'], row['tval']) for row in rows if row.get('event') == 'trap']
    recorded = [(int(row['cycle']), int(row['cause'], 16), int(row['tval'], 16))
                for row in end['reference_inputs']['traps'] if first <= int(row['cycle']) < last]
    if actual != recorded:
        raise ValueError('trace trap events differ from checkpoint input history')
    keys = lambda row: {k: v for k, v in row.items() if k not in ('event', 'seq', 'before_order')}
    history = {json.dumps(keys(row), sort_keys=True) for row in end['reference_inputs']['external']}
    for row in rows:
        if row.get('event') == 'external_interrupt' and json.dumps(keys(row), sort_keys=True) not in history:
            raise ValueError('trace external event differs from checkpoint input history')
        if 'order' in row and not (int(before['retired']) <= int(row['absolute_order']) < int(end['retired'])):
            raise ValueError('trace retirement is outside the checkpoint interval')


def capture_reference(capture, path, shim):
    extension = capture.file(path)
    build = json.loads(capture.file(Path(str(path)+'.json')).copy.read_text())
    source = capture.file(Path(__file__).with_name('reference-profile.cc'))
    if (build.get('schema') != 'rvw.vexii-reference-build/1' or build.get('physical_bits') != 32
            or build.get('pmp_regions') != 8 or build.get('name') != 'rvw_vexii_linux'
            or build.get('library_sha256') != extension.sha256 or build.get('source_sha256') != source.sha256
            or build.get('spike_library_sha256') != shim['dependency']['sha256']):
        raise ValueError('Linux reference extension identity differs; rebuild it')
    return dict(name='rvw_vexii_linux', library=str(extension.copy))


def compare(model, records, inputs, n, start):
    if inputs.get('schema') != 'rvw.boot-reference-inputs/1' or not inputs.get('enabled'):
        raise ValueError('checkpoint has no compact reference input history')
    selected = {}
    for row in records:
        if 'event' in row:
            continue
        absolute = int(row['absolute_order'])
        if absolute < start or absolute in selected:
            raise ValueError('sample precedes checkpoint or repeats a retirement')
        selected[absolute] = row
    selected = dict(list(selected.items())[:n])
    if len(selected) != n or list(selected) != list(range(start, start+n)):
        raise ValueError('sample must contain N consecutive retirements after the checkpoint')
    by_order, counters, traps = {}, {}, {}
    levels = 0
    for seq, event in enumerate(inputs['external']):
        order = event['before_order']
        if type(order) is not int or order < 0:
            raise ValueError('invalid external retirement boundary')
        validate(event, {'xlen': 64, 'external_interrupts': {'schema': 'rvw.external-interrupts/1'}}, seq, order)
        by_order.setdefault(order, []).append(event)
    for row in inputs['counters']:
        order = int(row['order'])
        if order in counters or not counter_read(int(row['insn'], 16)):
            raise ValueError('invalid or duplicate counter input')
        counters[order] = row
    for row in inputs['traps']:
        traps.setdefault(int(row['order']), []).append(row)
    checked = synced = irq_count = trap_count = 0
    after_trap = False
    for order in range(start+n):
        mmio = None
        taken = []
        for event in by_order.get(order, []):
            if event['kind'] == 'pins':
                levels = int(event['levels'], 16)
            elif event['kind'] == 'taken':
                cause = int(event['cause'], 16)
                code = cause & ((1 << 63)-1)
                if code in model.platform.irq_inputs and not levels & (1 << code):
                    raise ValueError('interrupt was taken without an asserted input')
                taken.append(cause)
            elif event['kind'] == 'mmio':
                if mmio is not None:
                    raise ValueError('multiple device effects for one retirement')
                mmio = event
            else:
                raise ValueError('unsupported boot external input kind')
        for trap in traps.get(order, []):
            cause = int(trap['cause'], 16)
            if cause >> 63:
                if not taken or taken.pop(0) != cause:
                    raise ValueError('trap lacks matching taken evidence')
                irq_count += 1
            effect = model.step(interrupt=cause if cause >> 63 else 0)
            if (not effect['trap'] or effect['pc'] != int(trap['epc'], 16)
                    or effect['cause'] != cause or effect['tval'] != int(trap['tval'], 16)):
                return dict(status='mismatch', order=order, compared=checked, reason='trap differs',
                            observed=trap, reference=c2_view({k: effect[k] for k in ('pc','trap','cause','tval','mode','insn')}))
            after_trap = True
            trap_count += 1
        if taken:
            raise ValueError('taken evidence lacks a trap')
        if levels & ~0x888:
            raise ValueError('sampled replay currently binds machine software, timer and external pins only')
        # This shim path affects CSR reads. It does not deliver interrupts
        # before the independently observed taken boundary.
        model.environment_inputs(levels)
        inject = (int(mmio['address'], 16), int(mmio['value'], 16)) if mmio and not mmio['write'] else None
        expected = model.step(mmio=inject)
        if expected['trap']:
            return dict(status='mismatch', order=order, compared=checked, reason='unrecorded reference trap',
                        reference=c2_view({k: expected[k] for k in ('pc','cause','tval','mode','insn')}))
        counter = counters.get(order)
        if counter:
            if (expected['pc'] != int(counter['pc'], 16) or expected['insn'] != int(counter['insn'], 16)
                    or expected['rd'] != counter['rd']):
                return dict(status='mismatch', order=order, compared=checked, reason='counter access differs',
                            observed=counter, reference=c2_view({k: expected[k] for k in ('pc','insn','rd','rd_wdata','mode')}))
            value = int(counter['value'], 16)
            model.set_reg(counter['rd'], value)
            expected['rd_wdata'] = value
            synced += 1
        if mmio:
            direction = 'w' if mmio['write'] else 'r'
            if (expected['pc'] != int(mmio['pc'], 16) or expected['insn'] != int(mmio['insn'], 16)
                    or expected['mem_addr'] != int(mmio['virtual_address'], 16)
                    or expected[f'mem_{direction}mask'] != (1 << mmio['bytes'])-1
                    or masked(expected[f'mem_{direction}data'], expected[f'mem_{direction}mask']) != int(mmio['value'], 16)):
                return dict(status='mismatch', order=order, compared=checked, reason='device access differs',
                            observed=mmio, reference=c2_view({k: expected[k] for k in ('pc','insn','mem_addr','mem_rmask','mem_wmask','mem_rdata','mem_wdata')}))
        if order in selected:
            actual = selected[order]
            fields = ['pc', 'pc_next', 'insn', 'mode', 'trap', 'rd', 'rd_wdata', 'mem_rmask', 'mem_wmask', 'mem_fault']
            diff = differences(actual, expected, fields)
            if actual['intr'] != after_trap:
                diff['intr'] = {'expected': after_trap, 'actual': actual['intr']}
            sources = integer_sources(expected['insn'], 64)
            for k, source in zip(('rs1', 'rs2'), sources):
                if actual[k] != source or actual[f'{k}_rdata'] != expected['before'][source]:
                    diff[k] = {'expected': source, 'actual': actual[k]}
            if actual['mem_rmask'] or actual['mem_wmask'] or expected['mem_rmask'] or expected['mem_wmask']:
                diff.update(differences(actual, expected, ['mem_addr']))
            for direction in ('r', 'w'):
                key, mask = f'mem_{direction}data', f'mem_{direction}mask'
                if masked(actual[key], actual[mask]) != masked(expected[key], expected[mask]):
                    diff[key] = {'expected': expected[key], 'actual': actual[key]}
            if diff:
                return dict(status='mismatch', order=order, compared=checked, differences=diff)
            checked += 1
        after_trap = False
    return dict(status='match', compared=checked, fast_forwarded=start,
                counter_inputs=synced, interrupts=irq_count, trap_events=trap_count,
                scope='N retirements after checkpoint; prefix executes without full-trace comparison')


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('checkpoint', 'end-checkpoint', 'trace', 'elf', 'payloads', 'map', 'shim', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('-n', type=int, default=32)
    parser.add_argument('--reference-extension', type=Path,
                        help='project Linux reference library from build_reference.py')
    args = parser.parse_args()
    if args.n <= 0:
        parser.error('N must be positive')
    args.out.mkdir(parents=True, exist_ok=False)
    capture = Capture(args.out / 'inputs')
    capture.env('RVW_SPIKE_MEMORY_LOG')
    first_zip, end_zip = capture.file(args.checkpoint), capture.file(args.end_checkpoint)
    before, end = snapshot(first_zip.copy), snapshot(end_zip.copy)
    if before['identity'] != end['identity']:
        raise ValueError('checkpoint model or input identity differs')
    for key in ('external', 'counters', 'traps'):
        prefix = before['reference_inputs'][key]
        if end['reference_inputs'][key][:len(prefix)] != prefix:
            raise ValueError('reference input history is not a continuation')
    elf = capture.file(args.elf)
    payloads = json.loads(capture.file(args.payloads).copy.read_text())
    if payloads['schema'] != 'rvw.boot-payloads/1':
        raise ValueError('invalid payload manifest')
    parts = [(row, capture.file(args.payloads.parent / row['file'])) for row in payloads['payloads']]
    if [elf.sha256, *(item.sha256 for _, item in parts)] != before['identity']['inputs']:
        raise ValueError('original boot bytes differ from checkpoint')
    mapped = capture.file(args.map)
    if mapped.sha256 != before['identity']['map']:
        raise ValueError('map differs from checkpoint')
    mapping = json.loads(mapped.copy.read_text())
    ranges = lambda kind: [(int(row['base'], 0), int(row['size'], 0)) for row in mapping['regions'] if row['kind'] == kind]
    platform = Platform('vexii-boot-sample', 64, 'rv64imac_zicsr_zifencei_zicntr',
                        0x80000000, ranges('ram'), ranges('mmio'), pmp_regions=8, pmp_granularity=16,
                        irq_inputs=[3, 7, 11])
    shim = capture_shim(capture, args.shim)
    if args.reference_extension:
        platform.reference_extensions = [capture_reference(capture, args.reference_extension, shim)]
    trace = Trace(capture.file(args.trace).copy)
    if (trace.header['elf_sha256'] != elf.sha256 or trace.header['rtl_sha256'] != end['identity']['rtl']
            or not trace.header.get('window') or 'external_interrupts' not in trace.header
            or trace.header['external_interrupts'].get('map_sha256') != mapped.sha256
            or trace.header['isa'] != platform.isa or trace.header['config'] != 'rv64imacsu_linux'):
        raise ValueError('trace lacks matching bounded-window identity or external evidence')
    with_trace = list(trace)
    validate_window(trace.header, with_trace, before, end)
    model = Spike(platform, elf.copy, shim=shim)
    try:
        if args.reference_extension:
            # Spike installs an extension's CSRs during reset. Register the
            # project profile, then reset before executing any instruction.
            model.reset_preserve_ram(platform.reset_pc)
        for row, item in parts:
            data = item.copy.read_bytes()
            if model.lib.rvw_write(model.handle, int(row['address'], 0), data, len(data)):
                raise ValueError(model.error())
        started = perf_counter()
        result = compare(model, with_trace, end['reference_inputs'], args.n, int(before['retired']))
        result['reference_wall_seconds'] = perf_counter()-started
    finally:
        model.close()
    result.update(schema='rvw.boot-sample-result/1', start_checkpoint_sha256=first_zip.sha256,
                  end_checkpoint_sha256=end_zip.sha256,
                  capture=capture.record())
    result['reference_profile'] = ('rvw_vexii_linux' if args.reference_extension else 'spike-default')
    (args.out / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0 if result['status'] == 'match' else 1


if __name__ == '__main__':
    raise SystemExit(main())
