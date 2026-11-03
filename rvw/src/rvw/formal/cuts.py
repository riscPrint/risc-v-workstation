"""Width-checked, unconstrained cut points. No assume-guarantee composition."""
import json
from . import common


def commands(args, out, files):
    cuts = getattr(args, 'cut', None) or []
    if not cuts:
        return '', []
    requested = []
    for value in cuts:
        parts = value.split(':')
        if len(parts) != 2:
            raise ValueError("cut must be SIGNAL:WIDTH")
        common.check_hier("--cut signal", parts[0])
        width = int(parts[1])
        if width <= 0 or parts[0] in {s for s, _ in requested}:
            raise ValueError("cut widths must be positive; signals must be unique")
        requested.append((parts[0], width))
    model = out / 'cut-model.json'
    script = (common.read_rtlil(files)
              + f"\nread_verilog -formal -sv {out / 'rvw_formal_top.sv'}"
              + f"\nprep -top rvw_formal_top -flatten\nwrite_json {model}\n")
    path = out / 'cuts.ys'
    path.write_text(script)
    rc, _ = common.run(['yosys', '-Q', '-T', '-s', str(path)], out, out / 'cuts.log', args.timeout)
    if rc != 0 or not model.exists():
        raise ValueError("cannot inspect cut-point widths")
    nets = json.loads(model.read_text())['modules']['rvw_formal_top']['netnames']
    records = []
    for signal, width in requested:
        name = 'dut.' + signal
        net = nets.get(name)
        if net is None or len(net['bits']) != width:
            raise ValueError(f"cut {signal}:{width}: missing signal or width mismatch")
        bits = net['bits']
        if any(not isinstance(bit, int) for bit in bits) or len(set(bits)) != width:
            raise ValueError(f'cut {signal}: constant or aliased bits cannot form a free cut')
        clock_bits = nets.get('dut.' + args.clock, {}).get('bits', [])
        if set(bits) & set(clock_bits):
            raise ValueError('clock signals cannot be cut')
        records.append({'signal': signal, 'width': width, 'semantics': 'unconstrained_anyseq'})
    return 'flatten\n' + '\n'.join(
        f'cutpoint rvw_formal_top/w:dut.{r["signal"]}' for r in records), records
