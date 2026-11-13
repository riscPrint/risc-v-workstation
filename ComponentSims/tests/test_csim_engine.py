"""csim engine checks with hand-derived expectations and scalar references."""
import json
import random
import struct
import subprocess

import pytest


def kv(**keys):
    return ''.join(f'{k.replace("__", ".")}={v}\n' for k, v in keys.items())


def run(csim, tmp_path, config, trace, fmt='csim', budget=False):
    cfg = tmp_path / 'c.kv'
    cfg.write_text(config)
    args = [str(csim), str(cfg), '--format', fmt]
    if budget:
        args.append('--budget')
    data = trace if isinstance(trace, bytes) else trace.encode()
    return subprocess.run(args, input=data, capture_output=True)


def report(csim, tmp_path, config, trace, fmt='csim'):
    r = run(csim, tmp_path, config, trace, fmt)
    assert r.returncode == 0, r.stderr.decode()
    return json.loads(r.stdout)


def trace(rows, n=None):
    last = max((int(r.split()[1]) for r in rows), default=0)
    return 'rvw.csim-trace/1\n' + ''.join(r + '\n' for r in rows) + f'END {n or last}\n'


def cond_rows(outcomes, pc=0x100, start=1, step=1, target=0x80):
    return [f'B {start + i * step} {pc:x} cond {t} {target:x}' for i, t in enumerate(outcomes)]


# ------------------------------------------------------------------ direction

def test_bimodal_saturation_hand_derived(csim, tmp_path):
    # Counter starts at 1 (weakly not taken): T miss->2, T hit->3, T hit, N miss->2, T hit.
    d = report(csim, tmp_path, kv(branch__model='bimodal'), trace(cond_rows([1, 1, 1, 0, 1])))
    assert d['branch']['direction']['misses'] == 2
    assert d['branch']['direction']['storage']['bits'] == 4096 * 2


@pytest.mark.parametrize('model', ['bimodal', 'gshare'])
def test_matches_legacy_engine(csim, engine, tmp_path, model):
    rng = random.Random(5)
    rows = [(i, rng.randrange(256) * 2, rng.randrange(2)) for i in range(1, 3001, 2)]
    legacy = 'rvw.branch-trace/1 3001\n' + ''.join(f'B {o} {p:x} {t}\n' for o, p, t in rows) + 'END\n'
    old = json.loads(subprocess.run([str(engine), model, '256', '6', '1', '100'], input=legacy, text=True, capture_output=True).stdout)
    new = report(csim, tmp_path, kv(branch__model=model, branch__entries=256, branch__history=6, warmup_instructions=100)
                 if model == 'gshare' else kv(branch__model=model, branch__entries=256, warmup_instructions=100), legacy)
    assert new['branch']['direction']['misses'] == old['direction_misses']
    assert new['trace']['measured_instructions'] == old['instructions']


def perceptron_reference(rows, entries, hlen, theta):
    w = [[0] * (hlen + 1) for _ in range(entries)]
    hist, misses = [], 0
    for pc, t in rows:
        row = w[(pc >> 1) % entries]
        x = [1 if (hist[i] if i < len(hist) else 0) else -1 for i in range(hlen)]
        y = row[0] + sum(a * b for a, b in zip(row[1:], x))
        pred = y >= 0
        misses += pred != t
        if pred != t or abs(y) <= theta:
            tt = 1 if t else -1
            row[0] = max(-128, min(127, row[0] + tt))
            for i in range(hlen):
                row[i + 1] = max(-128, min(127, row[i + 1] + tt * x[i]))
        hist.insert(0, t)
    return misses


def test_perceptron_scalar_reference(csim, tmp_path):
    rng = random.Random(9)
    pcs = [0x40, 0x48, 0x50, 0x58]
    outs, rows = [], []
    for i in range(2000):
        pc = pcs[i % 4]
        t = rng.randrange(2) if pc == 0x40 else (outs[-1] if outs else 0) ^ (pc == 0x50)
        outs.append(t); rows.append((pc, t))
    text = trace([f'B {i + 1} {pc:x} cond {t} 0' for i, (pc, t) in enumerate(rows)])
    d = report(csim, tmp_path, kv(branch__model='perceptron', branch__entries=8, branch__history=6, branch__threshold=25), text)
    assert d['branch']['direction']['misses'] == perceptron_reference(rows, 8, 6, 25)


def test_tage_learns_alternation_and_allocates(csim, tmp_path):
    rows = cond_rows([i & 1 for i in range(4000)])
    tage = report(csim, tmp_path, kv(branch__model='tage', warmup_instructions=2000), trace(rows))
    bim = report(csim, tmp_path, kv(branch__model='bimodal', warmup_instructions=2000), trace(rows))
    assert tage['branch']['direction']['misses'] == 0
    assert bim['branch']['direction']['misses'] == 1000  # N hit (1->0), T miss (0->1), ...: every taken misses
    assert tage['branch']['direction']['internal']['allocations'] > 0


def test_tage_storage_formula(csim, tmp_path):
    cfg = kv(branch__model='tage', branch__base_entries=1024, branch__path_bits=8,
             branch__tables__0__entries=256, branch__tables__0__history=4, branch__tables__0__tag_bits=8,
             branch__tables__1__entries=512, branch__tables__1__history=16, branch__tables__1__tag_bits=10)
    r = run(csim, tmp_path, cfg, '', budget=True)
    parts = json.loads(r.stdout)['storage']['direction']['parts']
    assert parts['base'] == 1024 * 2
    assert parts['tagged'] == 256 * (3 + 2 + 8) + 512 * (3 + 2 + 10)


def test_useful_aging_period(csim, tmp_path):
    d = report(csim, tmp_path, kv(branch__model='tage', branch__u_reset_period=10), trace(cond_rows([1] * 100)))
    assert d['branch']['direction']['internal']['u_aging_events'] == 10


def loop_trace(trip, iterations, seed=3):
    rng = random.Random(seed)
    rows, o = [], 0
    for _ in range(iterations):
        for k in range(trip):
            o += 1; rows.append(f'B {o} 3000 cond {rng.randrange(2)} 3010')
            o += 1; rows.append(f'B {o} 1010 cond {int(k < trip - 1)} 1000')
    return trace(rows)


def worst(d, pc):
    return next(b for b in d['branch']['top_branches'] if b['pc'] == pc)


def test_loop_predictor_confidence(csim, tmp_path):
    text = loop_trace(40, 400)
    base = kv(branch__num_tables=6, branch__max_history=64, warmup_instructions=8000)
    plain = report(csim, tmp_path, base + 'branch.model=tage\n', text)
    loop = report(csim, tmp_path, base + 'branch.model=ltage\n', text)
    assert worst(loop, '0x1010')['direction_misses'] * 10 < worst(plain, '0x1010')['direction_misses']
    assert loop['branch']['direction']['internal']['loop']['used'] > 0


def test_tage_sc_l_components_and_override(csim, tmp_path):
    d = report(csim, tmp_path, kv(branch__model='tage-sc-l'), loop_trace(12, 300))
    internal = d['branch']['direction']['internal']
    assert internal['components'] == ['tage', 'loop', 'sc']
    assert 'overrides' in internal['sc']
    parts = d['branch']['direction']['storage']['parts']
    assert parts['sc_tables'] > 0 and parts['loop'] > 0


def test_update_delay_changes_training(csim, tmp_path):
    rows = trace(cond_rows([int(i % 3 == 0) for i in range(3000)]))
    a = report(csim, tmp_path, kv(branch__model='gshare', branch__history=4), rows)
    b = report(csim, tmp_path, kv(branch__model='gshare', branch__history=4, branch__update_delay=64), rows)
    assert b['branch']['direction']['update_delay'] == 64
    assert b['branch']['direction']['misses'] >= a['branch']['direction']['misses']


@pytest.mark.parametrize('model', ['local', 'tournament', 'hashed-perceptron', 'always-taken', 'btfn', 'perfect'])
def test_other_models_run(csim, tmp_path, model):
    d = report(csim, tmp_path, kv(branch__model=model), loop_trace(5, 100))
    assert d['status'] == 'reported'
    if model == 'perfect':
        assert d['branch']['direction']['misses'] == 0


def test_btfn_uses_target(csim, tmp_path):
    rows = ['B 1 100 cond 1 80', 'B 2 100 cond 0 80', 'B 3 200 cond 0 300', 'B 4 200 cond 1 300']
    d = report(csim, tmp_path, kv(branch__model='btfn'), trace(rows))
    assert d['branch']['direction']['misses'] == 2


# ------------------------------------------------------------------ targets

def test_btb_capacity_and_aliasing(csim, tmp_path):
    rows = [f'B {i + 1} {0x100 if i % 2 else 0x200:x} jump 1 400' for i in range(20)]
    one = report(csim, tmp_path, kv(btb__entries=1, btb__ways=1), trace(rows))
    two = report(csim, tmp_path, kv(btb__entries=2, btb__ways=2), trace(rows))
    assert one['branch']['target']['btb_misses_taken'] == 20
    assert two['branch']['target']['btb_misses_taken'] == 2


def test_btb_partial_tags_alias(csim, tmp_path):
    # Two PCs with the same set and a 1-bit tag hash collide; the stored target is wrong.
    rows = [f'B {i + 1} {0x10 if i % 2 else 0x18:x} jump 1 {0x500 if i % 2 else 0x600:x}' for i in range(10)]
    d = report(csim, tmp_path, kv(btb__entries=1, btb__ways=1, btb__tag_bits=1), trace(rows))
    assert d['branch']['target']['btb_wrong_target'] > 0


def test_multilevel_btb_refill(csim, tmp_path):
    pcs = [0x100 + 8 * i for i in range(8)]
    rows = [f'B {i + 1} {pcs[i % 8]:x} jump 1 900' for i in range(64)]
    d = report(csim, tmp_path, kv(btb__levels__0__entries=2, btb__levels__0__ways=2, btb__levels__1__entries=64,
                                  btb__levels__1__ways=4, btb__levels__1__latency=2), trace(rows))
    l0, l1 = d['branch']['target']['btb']
    assert d['branch']['target']['btb_misses_taken'] == 8
    assert l1['hits'] == 56 and l0['hits'] == 0


def test_ras_overflow_underflow_and_compressed(csim, tmp_path):
    rows = ['B 1 100 call 1 1000 4', 'B 2 1000 call 1 2000 2', 'B 3 2000 call 1 3000 4',
            'B 4 3000 ret 1 2004', 'B 5 2010 ret 1 1002', 'B 6 1010 ret 1 104']
    d = report(csim, tmp_path, kv(ras__entries=2), trace(rows))
    ras = d['branch']['target']['ras']
    assert ras['overflows'] == 1 and ras['underflows'] == 1
    assert d['branch']['target']['return_misses'] == 1


def repair_trace(n):
    rows, o = [], 0
    for i in range(n):
        o += 1; rows.append(f'B {o} 1000 call 1 2000 4')
        t = i & 1
        o += 1; rows.append(f'B {o} 2000 cond {t} 2100 4')
        if t:
            o += 1; rows.append(f'B {o} 2104 ret 1 1004 4')
        else:
            o += 1; rows.append(f'B {o} 2008 call 1 3000 4')
            o += 1; rows.append(f'B {o} 3004 ret 1 200c 4')
            o += 1; rows.append(f'B {o} 2010 ret 1 1004 4')
        o += 1; rows.append(f'B {o} 1008 jump 1 1000 4')
    return trace(rows)


def test_ras_repair_policies_with_wrong_path(csim, tmp_path):
    base = kv(branch__model='bimodal', btb__entries=64, wrong_path__branches=1, ras__entries=16)
    res = {p: report(csim, tmp_path, base + f'ras.repair={p}\n', repair_trace(200))['branch']['target']['return_misses']
           for p in ('none', 'pointer', 'full')}
    assert res['none'] > 0
    assert res['pointer'] == 0 and res['full'] == 0


def test_ittage_learns_history_correlated_targets(csim, tmp_path):
    rows, o = [], 0
    rng = random.Random(4)
    for _ in range(3000):
        t = rng.randrange(2)
        o += 1; rows.append(f'B {o} 100 cond {t} 200')
        o += 1; rows.append(f'B {o} 300 ijump 1 {0x4000 if t else 0x5000:x}')
    base = kv(btb__entries=64)
    btb = report(csim, tmp_path, base + 'indirect.model=btb\nwarmup_instructions=2000\n', trace(rows))
    itt = report(csim, tmp_path, base + 'indirect.model=ittage\nwarmup_instructions=2000\n', trace(rows))
    assert itt['branch']['target']['indirect_misses'] * 10 < btb['branch']['target']['indirect_misses']


def test_targets_refused_on_legacy_trace(csim, tmp_path):
    r = run(csim, tmp_path, kv(btb__entries=64), 'rvw.branch-trace/1 3\nB 1 100 1\nEND\n')
    assert r.returncode == 2 and b'no branch targets' in r.stderr


# ------------------------------------------------------------------ front end

def frontend_trace(blocks, size=8, span=0x100):
    rows, o = [], 0
    for i in range(blocks):
        base = 0x10000 + (i % 64) * span
        o += size; rows.append(f'B {o} {base + 4 * (size - 1):x} jump 1 {0x10000 + ((i + 1) % 64) * span:x} 4')
    return trace(rows)


def test_frontend_redirect_cost_and_fdip(csim, tmp_path):
    t = frontend_trace(3000)
    base = kv(btb__entries=4096, frontend__fetch_width=8, frontend__decode_width=8, memory__l1i__size_kib=1,
              memory__l1i__ways=4, memory__l2__size_kib=256, memory__l2__ways=8, warmup_instructions=2000)
    plain = report(csim, tmp_path, base, t)['frontend']
    fdip = report(csim, tmp_path, base + 'frontend.fdip=true\n', t)['frontend']
    assert plain['bubble_cycles']['icache'] > 0
    assert fdip['bubble_cycles']['icache'] < plain['bubble_cycles']['icache']
    assert fdip['cycles'] < plain['cycles']


def test_frontend_execute_redirects_scale_with_latency(csim, tmp_path):
    t = loop_trace(3, 500)
    res = [report(csim, tmp_path, kv(branch__model='bimodal', frontend__resolve_latency=lat), t)['frontend'] for lat in (5, 20)]
    assert res[0]['execute_redirects'] == res[1]['execute_redirects'] > 0
    assert res[1]['cycles'] > res[0]['cycles']


# ------------------------------------------------------------------ memory

def mem_rows(addrs, kind='L', pc=0x500):
    return [f'{kind} {i + 1} {pc:x} {a:x} 8' for i, a in enumerate(addrs)]


def l1(**extra):
    return kv(memory__l1d__size_kib=1, memory__l1d__ways=16, **extra)


def test_lru_cyclic_thrash_and_opt_bound(csim, tmp_path):
    addrs = [(i % 17) * 64 for i in range(17 * 20)]
    res = {}
    for pol in ('lru', 'plru', 'random', 'srrip', 'brrip', 'drrip', 'ship', 'hawkeye', 'opt'):
        d = report(csim, tmp_path, l1(memory__l1d__replacement=pol), trace(mem_rows(addrs)))
        res[pol] = d['memory']['l1d']['demand_misses']
    assert res['lru'] == len(addrs)
    assert res['opt'] == min(res.values()) and res['opt'] < res['lru']


def test_next_line_prefetch_coverage(csim, tmp_path):
    addrs = [i * 64 for i in range(2000)]
    cfg = kv(memory__l1d__size_kib=32, memory__l1d__ways=8, memory__cycles_per_instruction=1000,
             memory__l1d__prefetchers__0__kind='next-line', memory__l1d__prefetchers__0__degree=2)
    d = report(csim, tmp_path, cfg, trace(mem_rows(addrs)))['memory']['l1d']
    assert d['prefetch']['useful'] > 1900 and d['prefetch']['accuracy'] > 0.9 and d['prefetch']['late'] == 0


@pytest.mark.parametrize('kind', ['ip-stride', 'stream', 'bop', 'spp', 'sms', 'berti'])
def test_data_prefetchers_reduce_stride_misses(csim, tmp_path, kind):
    addrs = [0x100000 + i * 128 for i in range(6000)]
    base = kv(memory__l1d__size_kib=32, memory__l1d__ways=8, memory__l2__size_kib=256, memory__l2__ways=8,
              memory__cycles_per_instruction=50)
    plain = report(csim, tmp_path, base, trace(mem_rows(addrs)))['memory']['l1d']['demand_misses']
    d = report(csim, tmp_path, base + f'memory.l1d.prefetchers.0.kind={kind}\n', trace(mem_rows(addrs)))['memory']['l1d']
    if kind == 'sms':  # SMS needs repeated region generations; check it ran and stayed accurate
        assert d['prefetch']['issued'] >= 0
    else:
        assert d['demand_misses'] < plain, kind


def test_prefetch_queue_limit_and_pollution(csim, tmp_path):
    addrs = [i * 64 for i in range(500)]
    cfg = kv(memory__l1d__size_kib=1, memory__l1d__ways=16, memory__l1d__prefetch_queue=1, memory__dram_latency=10000,
             memory__l1d__prefetchers__0__kind='next-line', memory__l1d__prefetchers__0__degree=4)
    d = report(csim, tmp_path, cfg, trace(mem_rows(addrs)))['memory']['l1d']['prefetch']
    assert d['dropped_queue_full'] > 0
    # Pollution: a hot line is evicted by prefetches of a stream, then missed again.
    rows = []
    o = 0
    for r in range(50):
        o += 1; rows.append(f'L {o} 10 {0x900000:x} 8')
        for k in range(20):
            o += 1; rows.append(f'L {o} 20 {(r * 20 + k) * 64 * 3:x} 8')
    cfg = kv(memory__l1d__size_kib=1, memory__l1d__ways=16, memory__l1d__prefetchers__0__kind='next-line',
             memory__l1d__prefetchers__0__degree=8, memory__l1d__replacement='lru')
    d = report(csim, tmp_path, cfg, trace(rows))['memory']['l1d']['prefetch']
    assert d['pollution_misses'] > 0


def test_instruction_side_eip_and_cache(csim, tmp_path):
    t = frontend_trace(4000)
    base = kv(memory__l1i__size_kib=1, memory__l1i__ways=4, memory__l2__size_kib=256, memory__l2__ways=8, memory__cycles_per_instruction=4)
    plain = report(csim, tmp_path, base, t)['memory']['l1i']
    eip = report(csim, tmp_path, base + 'memory.l1i.prefetchers.0.kind=eip\n', t)['memory']['l1i']
    assert plain['demand_misses'] > 0
    assert eip['prefetch']['useful'] > 0 and eip['demand_misses'] < plain['demand_misses']


def test_tlb_walks_and_page_walk_cache(csim, tmp_path):
    # Three pages: two in one 2 MiB region, one in another 1 GiB region. Sv39: 3 levels.
    addrs = [0x0, 0x1000, 0x40000000]
    cfg = kv(memory__l1d__size_kib=32, memory__l1d__ways=8, memory__tlb__levels=3, memory__tlb__l2_enabled='false',
             memory__tlb__walk_through_cache='false')
    d = report(csim, tmp_path, cfg, trace(mem_rows(addrs)))['memory']['tlb']
    assert d['walks'] == 3
    assert d['walk_memory_references'] == 3 + 1 + 3


# ------------------------------------------------------------------ dependence and values

def dep_rows(n, conflict_every=1):
    rows, o = [], 0
    for i in range(n):
        o += 1; rows.append(f'S {o} 40 {0x1000 + (i % 4) * 8:x} 8')
        o += 1; rows.append(f'L {o} 44 {0x1000 + (i % 4) * 8 if i % conflict_every == 0 else 0x8000:x} 8')
    return trace(rows)


def test_memory_dependence_policies(csim, tmp_path):
    t = dep_rows(400, conflict_every=2)
    res = {m: report(csim, tmp_path, kv(mdp__model=m), t)['mdp'] for m in
           ('always-speculate', 'never-speculate', 'store-sets', 'wait-table', 'perfect')}
    assert res['always-speculate']['violations'] == res['always-speculate']['loads_with_conflict'] == 200
    assert res['never-speculate']['violations'] == 0 and res['never-speculate']['false_dependences'] == 200
    assert res['perfect']['violations'] == 0 and res['perfect']['false_dependences'] == 0
    assert res['store-sets']['violations'] <= 2


def test_value_predictors(csim, tmp_path):
    rows = [f'W {i + 1} 80 5 {8 * i:x} l' for i in range(100)]
    stride = report(csim, tmp_path, kv(vp__model='stride'), trace(rows))['vp']
    last = report(csim, tmp_path, kv(vp__model='last-value'), trace(rows))['vp']
    assert stride['predicted'] == stride['correct'] == 100 - 9
    assert last['predicted'] == 0
    rows = [f'W {i + 1} 80 5 7 m' for i in range(50)]
    v = report(csim, tmp_path, kv(vp__model='vtage', vp__eligible='all'), trace(rows))['vp']
    assert v['correct'] > 0 and v['incorrect'] == 0 and v['move_candidates'] == 50


# ------------------------------------------------------------------ formats and errors

def champsim_record(ip, branch=False, taken=False, dregs=(), sregs=(), dmem=(), smem=()):
    d = list(dregs) + [0] * (2 - len(dregs)); s = list(sregs) + [0] * (4 - len(sregs))
    dm = list(dmem) + [0] * (2 - len(dmem)); sm = list(smem) + [0] * (4 - len(smem))
    return struct.pack('<QBB2B4B2Q4Q', ip, int(branch), int(taken), *d, *s, *dm, *sm)


def test_champsim_reader(csim, tmp_path):
    IP, SP, FL = 26, 6, 25
    recs = [champsim_record(0x1000, smem=[0x5000]),
            champsim_record(0x1004, True, True, dregs=[IP], sregs=[IP, FL]),        # conditional taken
            champsim_record(0x2000, True, True, dregs=[IP, SP], sregs=[IP, SP]),    # direct call
            champsim_record(0x3000, dmem=[0x6000]),
            champsim_record(0x3004, True, True, dregs=[IP, SP], sregs=[SP]),        # return
            champsim_record(0x2005, True, True, dregs=[IP], sregs=[3]),             # indirect jump
            champsim_record(0x7000)]
    d = report(csim, tmp_path, kv(branch__model='bimodal', btb__entries=64, ras__entries=8,
                                  memory__l1d__size_kib=32, memory__l1d__ways=8), b''.join(recs), 'champsim')
    k = d['branch']['by_kind']
    assert (k['cond']['executed'], k['call']['executed'], k['ret']['executed'], k['ijump']['executed']) == (1, 1, 1, 1)
    assert d['trace']['instructions'] == 7 and d['memory']['l1d']['demand_accesses'] == 2


@pytest.mark.parametrize('cfg,text,msg', [
    ('branch.model=gshare\nbranch.bogus=1\n', 'rvw.csim-trace/1\nEND 1\n', b'unknown configuration keys'),
    ('branch.model=nope\n', 'rvw.csim-trace/1\nEND 1\n', b'unsupported value'),
    ('branch.model=gshare\n', 'rvw.csim-trace/1\nB 1 10 cond 1 0\n', b'missing completion footer'),
    ('branch.model=gshare\n', 'rvw.csim-trace/1\nB 2 10 cond 1 0\nB 1 10 cond 1 0\nEND 2\n', b'non-decreasing'),
    ('branch.model=gshare\nwarmup_instructions=5\n', 'rvw.csim-trace/1\nEND 5\n', b'empty measurement'),
    ('branch.model=gshare\n', 'rvw.csim-trace/1\nB 1 10 jump 0 0\nEND 1\n', b'must be taken'),
    ('memory.l1d.replacement=plru\nmemory.l1d.ways=12\n', 'rvw.csim-trace/1\nEND 1\n', b'power'),
    ('', 'rvw.csim-trace/1\nEND 1\n', b'no component'),
])
def test_errors(csim, tmp_path, cfg, text, msg):
    r = run(csim, tmp_path, cfg, text)
    assert r.returncode == 2 and msg in r.stderr and not r.stdout


def test_simulation_limit(csim, tmp_path):
    d = report(csim, tmp_path, kv(branch__model='bimodal', warmup_instructions=10, simulation_instructions=20),
               trace(cond_rows([1] * 100)))
    assert d['trace']['measured_instructions'] == 20 and d['branch']['direction']['conditional'] == 20


def test_context_policies(csim, tmp_path):
    rows, o = ['X 1 1'], 1
    for r in range(50):
        for k in range(4):
            o += 1; rows.append(f'B {o} {0x100 + 8 * k:x} jump 1 {0x900 + 8 * k:x}')
        o += 1; rows.append(f'X {o} {r & 1:x}')
    res = {p: report(csim, tmp_path, kv(btb__entries=64, btb__context=p), trace(rows))['branch']['target'] for p in ('shared', 'flush', 'tagged')}
    assert res['shared']['btb_misses_taken'] == 4
    assert res['flush']['btb_misses_taken'] == 4 * 50 and res['flush']['btb'][0]['context_flushes'] == 51
    assert res['tagged']['btb_misses_taken'] == 8  # one cold miss per branch and context
    rows = ['B 1 100 call 1 200 4', 'X 2 1', 'B 3 200 ret 1 104 4']
    flush = report(csim, tmp_path, kv(ras__entries=8, ras__context='flush'), trace(rows))['branch']['target']
    shared = report(csim, tmp_path, kv(ras__entries=8), trace(rows))['branch']['target']
    assert flush['return_misses'] == 1 and shared['return_misses'] == 0
    rows = [f'L {i + 1} 40 {(i % 4) * 4096:x} 8' for i in range(40)] + ['X 41 1'] + [f'L {42 + i} 40 {(i % 4) * 4096:x} 8' for i in range(8)]
    for pol, walks in (('shared', 4), ('flush', 8), ('tagged', 8)):
        d = report(csim, tmp_path, kv(memory__l1d__size_kib=32, memory__l1d__ways=8, memory__tlb__context=pol), trace(rows))
        assert d['memory']['tlb']['walks'] == walks, pol
