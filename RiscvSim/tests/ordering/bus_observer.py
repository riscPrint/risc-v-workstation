"""Match planned single-beat accesses to an independent external TileLink capture.

This boundary excludes cache hits and device-side effects. Plans must use unique
addresses. Each planned access must cause exactly one external request.
"""
import argparse
import json
from itertools import groupby
from pathlib import Path
from observer import check


def observe(plan, rows):
    boundary = 'accepted-external-tilelink'
    result = {'boundary': boundary, 'independent': True, 'complete': False, 'events': []}
    try:
        if plan['boundary'] != boundary or rows[0]['schema'] != 'rvw.bus-observations/1':
            raise ValueError('capture boundary or schema')
        if rows[0]['boundary'] != boundary or rows[0]['independent'] is not True:
            raise ValueError('independent bus capture required')
        width = rows[0]['bus_bytes']
        if type(width) is not int or width <= 0 or width & (width - 1):
            raise ValueError('bus width')
        if rows[-1].get('kind') != 'end' or rows[-1].get('status') != 'pass':
            raise ValueError('successful terminal capture required')
        planned = {}
        for op in plan['accesses']:
            address = int(op['address'], 0)
            if address in planned or not op['id'] or op['class'] not in 'rwio' or len(op['class']) != 1:
                raise ValueError('ambiguous access plan')
            if op['opcode'] not in (0, 1, 4) or not 0 <= op['size_log2'] <= width.bit_length() - 1:
                raise ValueError('only single-beat Get and Put supported')
            planned[address] = op
        if len({v['id'] for v in planned.values()}) != len(planned):
            raise ValueError('duplicate plan ID')
        pending, seen = {}, set()
        last = -1
        for seq, row in enumerate(rows[1:-1]):
            cycle = int(row['cycle'])
            if int(row['sequence']) != seq or cycle < last:
                raise ValueError('capture order or missing row')
            if row['channel'] not in ('a', 'b', 'c', 'd', 'e'):
                raise ValueError('unknown bus channel')
            last = cycle
        # A response and the next request may reuse a source on the same edge.
        # Capture order is not an ordering between those hardware effects.
        for cycle, batch in groupby(rows[1:-1], key=lambda row: int(row['cycle'])):
            batch = sorted(batch, key=lambda row:
                0 if row['channel'] == 'd' and row['source'] in pending else
                1 if row['channel'] == 'a' else 2)
            for row in batch:
                channel, source = row['channel'], row.get('source')
                if channel == 'a':
                    op = planned.get(int(row['address'], 0))
                    if op is None:
                        continue
                    if op['id'] in seen or source in pending:
                        raise ValueError('repeated access or source reuse')
                    if row['opcode'] != op['opcode'] or row['size_log2'] != op['size_log2']:
                        raise ValueError('request differs from plan')
                    if 'mask' in op and int(row['mask'], 0) != int(op['mask'], 0):
                        raise ValueError('request mask differs from plan')
                    if 'data' in op:
                        mask = int(row['mask'], 0)
                        selected = sum(255 << (lane * 8) for lane in range(width) if mask & (1 << lane))
                        if (int(row['data'], 0) ^ int(op['data'], 0)) & selected:
                            raise ValueError('request data differs from plan')
                    seen.add(op['id'])
                    pending[source] = (op, cycle)
                elif channel == 'd' and source in pending:
                    op, start = pending.pop(source)
                    if row['denied'] is not False or row['opcode'] != (1 if op['opcode'] == 4 else 0):
                        raise ValueError('denied or unexpected response')
                    if row['size_log2'] != op['size_log2']:
                        raise ValueError('response size')
                    lane = int(op['address'], 0) % width
                    selected = ((1 << (8 * (1 << op['size_log2']))) - 1) << (lane * 8)
                    if 'expected_read_data' in op and (int(row['data'], 0) ^ int(op['expected_read_data'], 0)) & selected:
                        raise ValueError('read data differs from independent stimulus')
                    result['events'].append({'id': op['id'], 'class': op['class'], 'issue': start, 'complete': cycle})
        if pending or seen != {v['id'] for v in planned.values()} or int(rows[-1]['cycle']) < last:
            raise ValueError('missing planned accesses or responses')
        result['complete'] = True
    except (KeyError, ValueError, TypeError, IndexError) as error:
        result['reason'] = str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    observation = observe(plan, [json.loads(line) for line in args.capture.read_text().splitlines()])
    result = check(plan, observation)
    print(json.dumps({'observation': observation, 'ordering': result}, indent=2))
    return {'consistent': 0, 'mismatch': 1, 'inconclusive': 3}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
