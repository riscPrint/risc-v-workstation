"""Sequential Spike contracts and sampled RTL observations."""
from collections import defaultdict
from rvw.cosim.spike import Spike, probe


def reference(platform, elf, shim, registers, stop_pc, max_steps):
    """Run Spike independently. Never synchronize from a DUT observation."""
    if not 1 <= max_steps <= 100000:
        raise ValueError('max_steps must be in 1..100000')
    if any(type(r) is not int or not 1 <= r < 32 or type(v) is not int or not 0 <= v < 1 << platform.xlen
           for r, v in registers.items()):
        raise ValueError('register inputs must fit the platform XLEN')
    probe(platform, elf, shim=shim)
    model = Spike(platform, elf, shim=shim)
    trace, effects = [], []
    try:
        for reg, value in registers.items():
            model.set_reg(reg, value)
        for _ in range(max_steps):
            e = model.step()
            if e['trap'] or e['intr'] or e['halted'] or e['mem_fault']:
                raise ValueError('reference trapped or halted before the stop PC')
            trace.append([e['pc'], e['mem_addr'] if e['mem_rmask'] or e['mem_wmask'] else None])
            effects.append({k: e[k] for k in ('pc', 'insn', 'rd', 'rd_wdata', 'mem_addr', 'mem_rmask', 'mem_wmask', 'mem_wdata')})
            if e['pc_next'] == stop_pc:
                return {'contract': trace, 'effects': effects}
        raise ValueError('reference did not reach the stop PC')
    finally:
        model.close()


def eligible_zkt(insn):
    """Initial supported Zkt instruction: uncompressed integer ADD only."""
    return type(insn) is int and insn & 0xfe00707f == 0x33


def assess(rows, observation_names):
    """Compare equal-contract classes. Missing evidence cannot earn no_violation.

    Each row contains public_key, reference and RTL {complete, effects, cycles,
    observations}. The adapter must start from the declared reset for each case.
    """
    if len(rows) < 2 or not observation_names or len(set(observation_names)) != len(observation_names):
        raise ValueError('at least two cases and distinct observation names required')
    groups, errors = defaultdict(list), []
    for i, row in enumerate(rows):
        try:
            ref, rtl = row['reference'], row['rtl']
            n = len(ref['effects'])
            cycles = rtl['cycles']
            if (not n or rtl['complete'] is not True or rtl['effects'] != ref['effects']
                    or len(cycles) != n or any(type(x) is not int or x <= 0 for x in cycles)
                    or any(a >= b for a, b in zip(cycles, cycles[1:]))
                    or set(rtl['observations']) != set(observation_names)
                    or any(type(x) is not int or x < 0 for x in rtl['observations'].values())):
                raise ValueError('incomplete or architecturally mismatched RTL evidence')
            import json
            key = json.dumps([row['public_key'], ref['contract']], sort_keys=True)
            groups[key].append((i, row))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append({'case': i, 'cause': str(exc)})
    violations, compared, zkt_compared = [], 0, 0
    for group in groups.values():
        for pos, (i, a) in enumerate(group):
            for j, b in group[pos+1:]:
                compared += 1
                channels = [k for k in observation_names if a['rtl']['observations'][k] != b['rtl']['observations'][k]]
                if channels:
                    violations.append({'kind': 'contract', 'cases': [i, j], 'channels': channels})
                ac, bc = [0] + a['rtl']['cycles'], [0] + b['rtl']['cycles']
                for k, effect in enumerate(a['reference']['effects']):
                    if eligible_zkt(effect['insn']):
                        zkt_compared += 1
                        if ac[k+1]-ac[k] != bc[k+1]-bc[k]:
                            violations.append({'kind': 'zkt-add', 'cases': [i, j], 'instruction': k})
    verdict = 'violation' if violations else 'inconclusive' if errors or not compared else 'no_violation'
    return {'schema': 'rvw.leakage/1', 'verdict': verdict, 'cases': len(rows),
            'compared_pairs': compared, 'zkt_add_comparisons': zkt_compared,
            'zkt_verdict': ('violation' if any(v['kind'] == 'zkt-add' for v in violations) else
                            'inconclusive' if errors or not zkt_compared else 'no_violation'),
            'violations': violations, 'errors': errors,
            'limits': 'Sampled digital observations only. No absence-of-leakage or full Zkt claim.'}


def detection_rate(results):
    """Labels come from the experiment owner, never from the checker verdict."""
    seeded = [r for r in results if r['seeded'] is True]
    controls = [r for r in results if r['seeded'] is False]
    return {'seeded_total': len(seeded),
            'detected': sum(r['verdict'] == 'violation' for r in seeded),
            'missed': sum(r['verdict'] == 'no_violation' for r in seeded),
            'inconclusive': sum(r['verdict'] == 'inconclusive' for r in seeded),
            'detection_rate': sum(r['verdict'] == 'violation' for r in seeded)/len(seeded) if seeded else None,
            'controls': len(controls), 'false_positives': sum(r['verdict'] == 'violation' for r in controls)}
