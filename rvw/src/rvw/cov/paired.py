"""Candidate wall-time curves from two qualified campaign histories."""
from hashlib import sha256
import html
import json
import math
from pathlib import Path


def curve(report):
    # Initial counts in the supported profile are recorded separately by the loop.
    credited = set(report.get('initial_hits', []))
    points = [{'attempt':0, 'elapsed_s':0.0, 'bins':len(credited)}]
    elapsed = 0.0
    for index, attempt in enumerate(report['attempts']):
        cost = attempt.get('elapsed_s')
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
            raise ValueError('attempt cost is missing or invalid')
        elapsed += cost
        if attempt['status'] in ('hit', 'miss'):
            credited.update(attempt['new_hits'])
        elif attempt.get('new_hits'):
            raise ValueError('unqualified attempt contains credited hits')
        points.append({'attempt':index+1, 'elapsed_s':elapsed, 'bins':len(credited)})
    if credited != set(report['hits']):
        raise ValueError('credited history differs from final hits')
    return points


def compare(directed, random, out):
    for key in ('pair_context', 'supported_bins', 'full_plan_bins', 'generation_groups', 'implementation_sha256', 'execution_identity', 'initial_hits'):
        if key not in directed or directed[key] != random.get(key):
            raise ValueError('incompatible paired campaign field: '+key)
    if directed.get('strategy') != 'directed' or random.get('strategy') != 'random':
        raise ValueError('need directed and random campaign arms')
    if directed.get('attempt_budget') != random.get('attempt_budget'):
        raise ValueError('attempt budgets differ')
    def initial_identity(report):
        return [{k:v for k,v in r.items() if k != 'comparison'} for r in report.get('initial', {}).get('records', [])]
    if initial_identity(directed) != initial_identity(random):
        raise ValueError('initial suites differ')
    result = {'schema':'rvw.paired-curves/1', 'supported_bins':directed['supported_bins'],
              'axis':'candidate attempt wall seconds; excludes initial suite and evidence publication',
              'arms':{name:{'campaign_sha256':sha256(json.dumps(report, sort_keys=True).encode()).hexdigest(),
                            'status':report['status'], 'points':curve(report)}
                      for name,report in [('directed',directed),('random',random)]}}
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    (out/'curves.json').write_text(json.dumps(result, indent=2)+'\n')
    maximum = max(1.0, *(p['elapsed_s'] for arm in result['arms'].values() for p in arm['points']))
    total = max(1, result['supported_bins'])
    drawing = ['<svg xmlns="http://www.w3.org/2000/svg" width="640" height="320" viewBox="0 0 640 320">',
               '<rect width="640" height="320" fill="white"/>',
               '<path d="M50 20 V270 H620" fill="none" stroke="black"/>',
               '<text x="50" y="15" font-size="12">Covered supported bins</text>',
               '<text x="210" y="310" font-size="12">Candidate attempt wall seconds</text>',
               f'<text x="20" y="30" font-size="12">{total}</text>',
               f'<text x="570" y="290" font-size="12">{maximum:.1f}</text>']
    for index,(name,arm) in enumerate(result['arms'].items()):
        color = ('#2266aa','#cc6600')[index]
        points = ' '.join(f'{50+570*p["elapsed_s"]/maximum:.2f},{270-240*p["bins"]/total:.2f}' for p in arm['points'])
        drawing += [f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>',
                    f'<text x="400" y="{25+index*18}" fill="{color}" font-size="12">{html.escape(name)}</text>']
    (out/'curves.svg').write_text('\n'.join(drawing+['</svg>'])+'\n')
    return result
