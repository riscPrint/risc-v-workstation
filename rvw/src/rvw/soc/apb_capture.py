"""Check independently sampled SoC APB pins with the existing VIP and RAL oracle."""
import json
from pathlib import Path
from rvw.vip.apb import Monitor, Pins
from rvw.checks.soc_registers import RegisterEffects
from .model import load


def check(source, capture):
    model = load(source)
    regions = {r['name']:r for r in model['regions']}
    effects = RegisterEffects(source)
    monitors, transfers, last = {}, dict.fromkeys(regions, 0), {}
    for name, region in regions.items():
        def completed(t, name=name, region=region):
            if t.aborted:
                return
            transfers[name] += 1
            effects.observe(region['base']+t.address, t.write, t.data, t.response, error=t.error)
        monitors[name] = Monitor(completed)
    ended = False
    samples = 0
    with Path(capture).open() as stream:
        header = json.loads(next(stream))
        if header != dict(schema='rvw.soc-apb-samples/1', observation='rtl_peripheral_ports'):
            raise ValueError('expected independently sampled SoC APB ports')
        for line in stream:
            row = json.loads(line)
            if ended:
                raise ValueError('samples after end record')
            if row == {'end':True}:
                ended = True
                continue
            row = dict(row)
            name, cycle = row.pop('bus'), row.pop('cycle')
            if name not in regions or type(cycle) is not int or cycle <= last.get(name,-1):
                raise ValueError('invalid bus or sample cycle')
            last[name] = cycle
            monitors[name].sample(Pins(**row))
            samples += 1
    return dict(status='samples_match' if ended and samples and not any(m.pending for m in monitors.values()) else 'inconclusive',
                ended=ended, samples=samples, transfers=transfers,
                unexercised=[name for name,n in transfers.items() if not n], registers=effects.finish(),
                scope='sampled peripheral APB ports; core AXI ingress and formal decode are outside this capture')
