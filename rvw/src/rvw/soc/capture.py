"""Map checks for live harness endpoint observations, without a proof verdict."""
import hashlib
import json
from pathlib import Path
from .model import load, number, exact_json


def check_capture(source, capture, result):
    soc = load(source)
    run = json.loads(Path(result).read_text())
    path = Path(capture)
    with path.open() as stream:
        header = json.loads(next(stream))
        if header.get('schema') != 'rvw.soc-capture/1':
            raise ValueError('requires rvw.soc-capture/1')
        # Compare captured map bytes to the run identity and its exact generated regions.
        raw = (path.parent / 'sim-map.json').read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        sim = json.loads(raw)
        if digest != header.get('map_sha256') or digest != run.get('soc_map_sha256'):
            raise ValueError('capture map identity differs from run')
        if sim.get('schema') != 'rvw.sim-map/1' or sim.get('address_bits') != soc['address_bits']:
            raise ValueError('capture map schema or address width differs from source')
        if sim.get('regions') != exact_json(soc['regions']) or sim.get('interrupts') != soc['interrupts']:
            raise ValueError('capture map differs from source map')
        identity = header.get('identity', {})
        if not identity.get('source') or not run.get('rtl_sha256') or identity.get('rtl_sha256') != run['rtl_sha256'] or identity.get('source') != run.get('source'):
            raise ValueError('missing or different source/RTL identity')
        if (not identity.get('session_id') or identity['session_id'] != run.get('details', {}).get('simulation_session', {}).get('id')
                or not identity.get('elf_sha256') or identity['elf_sha256'] != run.get('elf_sha256')
                or identity.get('seed') != run.get('seed')):
            raise ValueError('capture belongs to a different run')
        checks, ended = [], False
        for line in stream:
            t = json.loads(line)
            if ended:
                raise ValueError('records after capture end')
            if t.get('event') == 'end':
                ended = True
                continue
            address, size = number(t['address']), number(t['size'])
            if size <= 0:
                raise ValueError('invalid transaction size')
            permission = 'x' if t['bus'] == 'ibus' else 'w' if t['write'] else 'r'
            regions = [r for r in soc['regions'] if r['base'] <= address and address + size <= r['base'] + r['size'] and permission in r['permissions']]
            expected = regions[0]['name'] if len(regions) == 1 else None
            checks.append(dict(address=hex(address), size=size, selected=t['selected'], expected=expected,
                               status='consistent' if t['selected'] == expected else 'mismatch'))
        gaps = ['retirement-to-bus pairing', 'bridge width conversion', 'endianness',
                'error response propagation', 'register side effects', 'complete decode coverage']
        if header.get('observation') != 'harness_decoder':
            gaps.append('actual decoder selection')
        if not ended:
            gaps.append('capture end')
        if not checks:
            gaps.append('bus requests')
        return dict(schema='rvw.soc-capture-check/1', status='mismatch' if any(c['status'] == 'mismatch' for c in checks) else 'inconclusive',
                    transactions=len(checks), complete=ended, checks=checks, gaps=gaps)
