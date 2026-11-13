"""Bounded Boolean cell equations for a flattened, technology-mapped netlist."""
from hashlib import sha256


def query(module, top, depth, property_name=None):
    if depth < 1:
        raise ValueError('depth must be positive')
    cells = module.get('cells', {})
    clocks = {tuple(c['connections']['C']) for c in cells.values() if c['type'] == '$_DFF_P_'}
    if len(clocks) > 1 or any(len(c) != 1 or not isinstance(c[0], int) for c in clocks):
        raise ValueError('cell query needs one nonconstant rising-edge clock')
    drivers = {}
    for c in cells.values():
        for port,direction in c.get('port_directions', {}).items():
            if direction in ('output', 'inout'):
                for bit in c['connections'][port]:
                    if isinstance(bit,int): drivers[bit] = drivers.get(bit,0)+1
    if any(n > 1 for n in drivers.values()):
        raise ValueError('cell query rejects multiple drivers')
    bits = {b for c in cells.values() for v in c['connections'].values() for b in v if isinstance(b, int)}
    lines = [f'(declare-fun b{b}_{t} () Bool)' for t in range(depth) for b in sorted(bits)]
    bindings = {}; failures = []; logic = []
    def value(bit, t):
        if bit in ('0', '1'):
            return 'true' if bit == '1' else 'false'
        if not isinstance(bit, int):
            raise ValueError('unknown constant bit')
        return f'b{bit}_{t}'
    def add(label, term, kind, t, **extra):
        lines.append(f'(assert (! {term} :named {label}))')
        bindings[label] = dict(kind=kind, sample=t, signals=[], **extra)
    for i,(name,cell) in enumerate(sorted(cells.items())):
        kind = cell['type']; con = cell['connections']
        if kind == '$scopeinfo': continue
        cell_id = sha256((top+'\0'+name).encode()).hexdigest()
        if kind not in ('$assert', '$assume', '$cover'):
            logic.append(dict(id=cell_id, name=name, type=kind, source=cell.get('attributes', {}).get('src')))
        for t in range(depth):
            def pin(port, at=t):
                if len(con[port]) != 1:
                    raise ValueError('expected bit-level cell: '+name)
                return value(con[port][0], at)
            if kind in ('$assert', '$assume', '$cover'):
                term = f'(and {pin("EN")} (not {pin("A")}))'
                if kind == '$assert' and property_name in (None, name): failures.append(term)
                if kind == '$assume': add(f'assumption_{i}_{t}', f'(not {term})', 'assumption', t, cell=name)
                continue
            if kind == '$_DFF_P_':
                if t == 0: continue
                term = f'(= {pin("Q")} {pin("D", t-1)})'
            elif kind == '$anyseq':
                continue
            elif kind == '$anyconst':
                for j,b in enumerate(con['Y']):
                    if t: add(f'cell_{i}_{j}_{t}', f'(= {value(b,t)} {value(b,0)})', 'cell', t, cell=name, cell_id=cell_id)
                continue
            elif kind == '$initstate':
                term = f'(= {pin("Y")} {"true" if t == 0 else "false"})'
            else:
                if kind == '$_NOT_': expr = f'(not {pin("A")})'
                elif kind in ('$_AND_', '$_OR_', '$_XOR_', '$_XNOR_', '$_NAND_', '$_NOR_'):
                    op = {'$_AND_':'and','$_OR_':'or','$_XOR_':'xor','$_XNOR_':'xor','$_NAND_':'and','$_NOR_':'or'}[kind]
                    expr = f'({op} {pin("A")} {pin("B")})'
                    if kind in ('$_XNOR_', '$_NAND_', '$_NOR_'): expr = f'(not {expr})'
                elif kind == '$_MUX_': expr = f'(ite {pin("S")} {pin("B")} {pin("A")})'
                else: raise ValueError('unsupported Boolean cell: '+kind)
                term = f'(= {pin("Y")} {expr})'
            add(f'cell_{i}_{t}', term, 'cell', t, cell=name, cell_id=cell_id)
    if not failures:
        raise ValueError('selected assertion missing')
    for i,net in enumerate(module.get('netnames', {}).values()):
        initial = net.get('attributes', {}).get('init')
        if initial:
            for j,(bit, val) in enumerate(zip(net['bits'], reversed(initial))):
                if val in '01': add(f'init_{i}_{j}', f'(= {value(bit,0)} {"true" if val == "1" else "false"})', 'initial_state', 0)
    add('failure', '(or ' + ' '.join(failures) + ')', 'any_assertion_failure', None)
    return '\n'.join(lines), dict(schema='rvw.smt-bindings/1', property_id=f'{top}:{property_name or "all_assertions"}',
        constraints=bindings, depth=depth, top=top, activation_queries=[], logic=logic,
        vacuity_queries=vacuity_queries(module, depth, property_name), coverage_scope='All mapped Boolean cells in the captured bounded model. Includes generated reset and formal helpers. Not unbounded coverage.')


def export(result, out, capture, timeout, depth=None, property_name=None):
    import json
    from pathlib import Path
    from rvw.common.proc import run_group
    root = Path(result).resolve()
    if root.is_dir(): root /= 'result.json'
    original = json.loads(capture.file(root).copy.read_text())
    if original.get('schema') != 'rvw.formal/1' or not original.get('assertions'):
        raise ValueError('expected captured formal result with assertions')
    model = capture.file(root.parent/'sby/model/design.il').copy
    yosys = capture.tool('yosys')
    path = out/'cells.json'
    script = f'read_rtlil {json.dumps(str(model))}; flatten; async2sync; memory_map; chformal -lower; dffunmap; techmap; opt_clean; write_json {json.dumps(str(path))}'
    proc = run_group([str(yosys.path), '-Q', '-T', '-p', script], capture=True, timeout=timeout)
    (out/'cell-export.log').write_text((proc.stdout or '')+(proc.stderr or ''))
    if proc.returncode: raise ValueError('cell export failed')
    modules = json.loads(path.read_text())['modules']
    tops = [n for n,m in modules.items() if int(m.get('attributes',{}).get('top','0'),2)]
    if len(tops) != 1: raise ValueError('expected one flattened top')
    text, bindings = query(modules[tops[0]], tops[0], depth or original['depth'], property_name)
    query_path, mapping = out/'bounded-cells.smt2', out/'cell-bindings.json'
    query_path.write_text(text); mapping.write_text(json.dumps(bindings,indent=2))
    return query_path, mapping, bindings


def vacuity_queries(module, depth, property_name):
    """Replace each combinational assertion leaf in the specification only."""
    drivers = {}
    for c in module['cells'].values():
        if c['type'] in ('$_NOT_', '$_AND_', '$_OR_', '$_XOR_', '$_MUX_'):
            drivers[c['connections']['Y'][0]] = c
    def tree(bit, seen=frozenset()):
        if bit in seen: raise ValueError('combinational loop in property')
        c = drivers.get(bit)
        if c is None: return bit
        ports = ('A',) if c['type']=='$_NOT_' else ('S','B','A') if c['type']=='$_MUX_' else ('A','B')
        op = {'$_NOT_':'not','$_AND_':'and','$_OR_':'or','$_XOR_':'xor','$_MUX_':'ite'}[c['type']]
        return (op, *(tree(c['connections'][p][0],seen|{bit}) for p in ports))
    def leaves(t):
        if not isinstance(t,tuple): return {t} if isinstance(t,int) else set()
        return set().union(*(leaves(x) for x in t[1:]))
    def render(t, at, leaf, replacement):
        if isinstance(t,tuple): return '('+t[0]+' '+' '.join(render(x,at,leaf,replacement) for x in t[1:])+')'
        if t == leaf: return replacement
        return f'b{t}_{at}' if isinstance(t,int) else 'true' if t=='1' else 'false'
    queries=[]
    for name,c in module['cells'].items():
        if c['type']!='$assert' or property_name not in (None,name): continue
        term=tree(c['connections']['A'][0]); en=c['connections']['EN'][0]
        atoms=sorted(leaves(term))
        if len(atoms)>64: continue
        for atom in atoms:
            replacements=[]
            for value in ('false','true'):
                terms=[]
                for at in range(depth):
                    enable=f'b{en}_{at}' if isinstance(en,int) else 'true' if en=='1' else 'false'
                    terms.append(f'(and {enable} (not {render(term,at,atom,value)}))')
                replacements.append('(or '+' '.join(terms)+')')
            queries.append(dict(property_id=name,atom_bit=atom,replacements=replacements))
    return queries
