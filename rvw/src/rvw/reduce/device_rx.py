"""Reduction of timed UART RX transactions in a captured simulation map."""
import copy
import hashlib
import json
from pathlib import Path


def reduce_device_rx(reducer):
    base = reducer.best['cmd']
    original = reducer.run.artifact('soc_map')
    if base.get('soc_map') is None or original is None:
        raise ValueError('device-rx mode needs a captured --soc-map')
    raw = Path(original).read_bytes()
    if hashlib.sha256(raw).hexdigest() != reducer.run.get('soc_map_sha256'):
        raise ValueError('captured simulation map digest differs')
    data = json.loads(raw)
    if data.get('schema') != 'rvw.sim-map/1':
        raise ValueError('expected rvw.sim-map/1')
    slots = [(i, j) for i, d in enumerate(data.get('devices', []))
             if d.get('model') == 'ns16550' for j in range(len(d.get('rx', [])))]
    if not slots:
        raise ValueError('device-rx mode needs UART RX events')
    def command(kept):
        selected = {slots[k] for k in kept}
        candidate = copy.deepcopy(data)
        for i, d in enumerate(candidate['devices']):
            if d.get('model') == 'ns16550':
                d['rx'] = [v for j, v in enumerate(d.get('rx', [])) if (i, j) in selected]
        path = reducer.out / f'device-rx-{len(reducer.trials)}.json'
        path.write_text(json.dumps(candidate) + '\n')
        saved = reducer.inputs.capture.file(path)
        return base.set(soc_map=str(saved.copy)), dict(
            soc_map_sha256=saved.sha256, device_rx_kept=kept, elf=reducer.best['elf'])
    reducer._stream_search('uart_rx', range(len(slots)), command)
