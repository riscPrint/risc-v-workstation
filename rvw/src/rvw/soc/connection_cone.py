"""Overapproximate modules outside a connection's hierarchy before synthesis.

Only explicit ANSI module ports are supported. Unrelated outputs are free
formal signals, so this removes constraints. It cannot make a transfer proof easier to satisfy.
"""
import re
from pathlib import Path


def abstract_modules(db, declaration, files, out):
    keep = {db.top}
    for key in ('source', 'destination', 'mode', 'enable'):
        if key not in declaration:
            continue
        signal = db.resolve_one(declaration[key])
        component = db.component(signal.component_id)
        # A boundary port survives in an empty module. Internal observations
        # require the original body. All ancestors retain their wiring.
        if signal.direction is None or (key != 'source' and signal.direction != 'in'):
            keep.add(component['module'])
        parent = component['parent_id']
        while parent is not None:
            component = db.component(parent)
            keep.add(component['module'])
            parent = component['parent_id']
    targets, abstracted = [], []
    pattern = re.compile(r'(?ms)^module\s+(\w+)\s*(\([^;]*?\);)(.*?)^endmodule\b')
    for i, path in enumerate(files):
        def replace(match):
            name, header, body = match.groups()
            if name in keep:
                return match.group(0)
            if not re.search(r'\b(input|output|inout)\b', header):
                raise ValueError('connection cone needs ANSI module ports: ' + name)
            abstracted.append(name)
            outputs = []
            for field in header.removeprefix('(').removesuffix(');').split(','):
                port = re.fullmatch(r'\s*(input|output|inout)\s+(?:(?:wire|reg|logic)\s+)?(?:signed\s+)?(\[[^]]+\])?\s*(\w+)\s*', field)
                if port is None or port[1] == 'inout':
                    raise ValueError('connection cone needs explicit ANSI input/output ports: ' + name)
                if port[1] == 'output':
                    outputs.append((port[2] or '',port[3]))
            free = '\n'.join(f'(* anyseq *) reg {width} rvw_abstract_{i}; assign {port} = rvw_abstract_{i};'
                             for i, (width, port) in enumerate(outputs))
            return 'module ' + name + ' ' + header + '\n' + free + '\nendmodule'
        text = pattern.sub(replace, Path(path).read_text())
        target = Path(out)/f'cone-{i}.v'
        target.write_text(text)
        targets.append(str(target))
    return targets, sorted(set(abstracted))
