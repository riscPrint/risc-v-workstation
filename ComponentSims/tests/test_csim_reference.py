"""Differential checks of the csim engine against separate scalar Python references."""
import json
import random
import subprocess

import pytest


def run(csim, tmp_path, config, rows, n=None):
    cfg = tmp_path / 'c.kv'
    cfg.write_text(config)
    last = max(int(r.split()[1]) for r in rows)
    text = 'rvw.csim-trace/1\n' + '\n'.join(rows) + f'\nEND {n or last}\n'
    r = subprocess.run([str(csim), str(cfg)], input=text, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


class LruSets:
    """Set-associative LRU table with full tags (line or PC granularity)."""

    def __init__(self, sets, ways):
        self.sets, self.ways = sets, ways
        self.s = [[] for _ in range(sets)]  # most recent last: [tag, value]

    def lookup(self, key):
        row = self.s[key % self.sets]
        for e in row:
            if e[0] == key:
                row.remove(e); row.append(e)
                return e
        return None

    def fill(self, key, value=None):
        row = self.s[key % self.sets]
        for e in row:
            if e[0] == key:
                row.remove(e); e[1] = value; row.append(e)
                return
        if len(row) == self.ways:
            row.pop(0)
        row.append([key, value])


@pytest.mark.parametrize('entries,ways', [(16, 1), (16, 4), (64, 8)])
def test_btb_matches_lru_reference(csim, tmp_path, entries, ways):
    rng = random.Random(entries * ways)
    pcs = [0x1000 + 4 * rng.randrange(256) for _ in range(40)]
    targets = {pc: 0x8000 + 4 * rng.randrange(64) for pc in pcs}
    rows, o, misses, wrong = [], 0, 0, 0
    ref = LruSets(entries // ways, ways)
    for _ in range(3000):
        pc = rng.choice(pcs)
        taken = rng.random() < 0.7
        if rng.random() < 0.05:
            targets[pc] = 0x8000 + 4 * rng.randrange(64)
        o += 1
        rows.append(f'B {o} {pc:x} cond {int(taken)} {targets[pc]:x} 4')
        key = pc >> 1
        hit = ref.lookup(key)
        if taken:
            if hit is None:
                misses += 1
            elif hit[1] != targets[pc]:
                wrong += 1
            ref.fill(key, targets[pc])
    d = run(csim, tmp_path, f'btb.entries={entries}\nbtb.ways={ways}\n', rows)
    t = d['branch']['target']
    assert (t['btb_misses_taken'], t['btb_wrong_target']) == (misses, wrong)


@pytest.mark.parametrize('depth', [2, 4, 16])
def test_ras_matches_circular_reference(csim, tmp_path, depth):
    rng = random.Random(depth)
    stack, actual = [], []
    rows, o, misses = [], 0, 0
    ref, top, count = [0] * depth, 0, 0
    pc = 0x1000
    for _ in range(4000):
        o += 1
        if actual and (rng.random() < 0.45 or len(actual) > 3 * depth):
            ret = actual.pop()
            rows.append(f'B {o} {pc:x} ret 1 {ret:x} 4')
            if count:
                pred = ref[top]; top = (top - 1) % depth; count -= 1
            else:
                pred = None
            misses += pred != ret
            pc = ret
        else:
            target = 0x10000 + 16 * rng.randrange(512)
            length = rng.choice([2, 4])
            rows.append(f'B {o} {pc:x} call 1 {target:x} {length}')
            actual.append(pc + length)
            top = (top + 1) % depth; ref[top] = pc + length; count = min(depth, count + 1)
            pc = target
    d = run(csim, tmp_path, f'ras.entries={depth}\n', rows)
    assert d['branch']['target']['return_misses'] == misses


def srrip_reference(lines, sets, ways, bits=2):
    mx = (1 << bits) - 1
    s = [[] for _ in range(sets)]  # [tag, rrpv]
    misses = 0
    for line in lines:
        row = s[line % sets]
        e = next((x for x in row if x[0] == line), None)
        if e:
            e[1] = 0
            continue
        misses += 1
        if len(row) < ways:
            row.append([line, mx - 1])
            continue
        while not any(x[1] >= mx for x in row):
            for x in row:
                x[1] += 1
        v = next(i for i, x in enumerate(row) if x[1] >= mx)
        row[v] = [line, mx - 1]
    return misses


def lru_reference(lines, sets, ways):
    ref, misses = LruSets(sets, ways), 0
    for line in lines:
        if ref.lookup(line) is None:
            misses += 1
            ref.fill(line)
    return misses


@pytest.mark.parametrize('policy,ref', [('lru', lru_reference), ('srrip', srrip_reference)])
def test_cache_replacement_matches_reference(csim, tmp_path, policy, ref):
    rng = random.Random(11)
    hot = [rng.randrange(1 << 14) for _ in range(300)]
    lines = [rng.choice(hot) if rng.random() < 0.8 else rng.randrange(1 << 16) for _ in range(20000)]
    rows = [f'L {i + 1} 40 {line * 64:x} 8' for i, line in enumerate(lines)]
    d = run(csim, tmp_path, f'memory.l1d.size_kib=8\nmemory.l1d.ways=4\nmemory.l1d.replacement={policy}\n', rows)
    assert d['memory']['l1d']['demand_misses'] == ref(lines, 8 * 1024 // 64 // 4, 4)


def test_memory_access_spans_cache_lines_and_pages(csim, tmp_path):
    config = ('memory.l1d.size_kib=1\nmemory.l1d.ways=1\n'
              'memory.tlb.l1.entries=4\nmemory.tlb.l1.ways=1\n'
              'memory.tlb.walk_through_cache=false\n')
    report = run(csim, tmp_path, config, ['L 1 40 ffc 8', 'L 2 40 1000 4'])
    cache = report['memory']['l1d']
    assert cache['demand_accesses'] == 3
    assert cache['demand_misses'] == 2
    assert cache['demand_hits'] == 1
    assert cache['demand_hits'] + cache['demand_misses'] == cache['demand_accesses']
    assert report['memory']['tlb']['walks'] == 2


def test_opt_refuses_cross_line_next_use_ambiguity(csim, tmp_path):
    config = tmp_path / 'opt.kv'
    config.write_text('memory.l1d.size_kib=1\nmemory.l1d.ways=1\n'
                      'memory.l1d.replacement=opt\n')
    result = subprocess.run([str(csim), str(config)],
                            input='rvw.csim-trace/1\nL 1 40 3c 8\nEND 1\n',
                            text=True, capture_output=True)
    assert result.returncode == 2
    assert 'cross-line' in result.stderr
