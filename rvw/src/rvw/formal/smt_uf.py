"""Typed UF substitution in Yosys SMT2 without discarding witness metadata."""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re

OPERATORS = ('bvmul', 'bvudiv', 'bvsdiv')
TOKEN = re.compile(r'\s+|;[^\n]*|\|[^|]*\||"(?:[^"]|"")*"|[()]|[^\s();]+')


@dataclass
class Node:
    atom: str | None
    items: list
    start: int
    end: int


def parse(text):
    stack = [([], 0)]
    for match in TOKEN.finditer(text):
        token = match[0]
        if token.isspace() or token.startswith(';'):
            continue
        if token == '(':
            stack.append(([], match.start()))
        elif token == ')':
            if len(stack) == 1:
                raise ValueError('unbalanced SMT2')
            items, start = stack.pop()
            stack[-1][0].append(Node(None, items, start, match.end()))
        else:
            stack[-1][0].append(Node(token, [], match.start(), match.end()))
    if len(stack) != 1:
        raise ValueError('unbalanced SMT2')
    return stack[0][0]


def head(node):
    return node.items[0].atom if node.items else None


def sort(node):
    if head(node) == '_' and len(node.items) == 3 and node.items[1].atom == 'BitVec':
        width = int(node.items[2].atom)
        if width < 1:
            raise ValueError('invalid bit-vector width')
        return ('bv', width)
    if head(node) == 'Array' and len(node.items) == 3:
        return ('array', sort(node.items[1]), sort(node.items[2]))
    return ('other', node.atom)


def expression_sort(node, env, returns):
    if node.atom is not None:
        if node.atom.startswith('#b'):
            return ('bv', len(node.atom) - 2)
        if node.atom.startswith('#x'):
            return ('bv', 4 * (len(node.atom) - 2))
        return env.get(node.atom)
    h = head(node)
    args = node.items[1:]
    if h in returns:
        return returns[h]
    if h == '_' and len(args) == 2 and args[0].atom.startswith('bv'):
        return ('bv', int(args[1].atom))
    if h == 'let':
        local = {b.items[0].atom: expression_sort(b.items[1], env, returns) for b in args[0].items}
        return expression_sort(args[1], {**env, **local}, returns)
    if h == 'ite':
        a, b = (expression_sort(v, env, returns) for v in args[1:])
        return a if a == b else None
    if h == 'concat':
        types = [expression_sort(v, env, returns) for v in args]
        return ('bv', sum(t[1] for t in types)) if all(t and t[0] == 'bv' for t in types) else None
    if h == 'select':
        array = expression_sort(args[0], env, returns)
        return array[2] if array and array[0] == 'array' else None
    if h == 'store':
        return expression_sort(args[0], env, returns)
    if h in {'bvnot', 'bvneg', 'bvadd', 'bvsub', 'bvmul', 'bvudiv', 'bvsdiv', 'bvurem',
             'bvsrem', 'bvsmod', 'bvand', 'bvor', 'bvxor', 'bvnand', 'bvnor', 'bvxnor',
             'bvshl', 'bvlshr', 'bvashr'}:
        return expression_sort(args[0], env, returns)
    if node.items and head(node.items[0]) == '_':
        op = node.items[0].items
        source = expression_sort(args[0], env, returns)
        if not source or source[0] != 'bv':
            return None
        name = op[1].atom
        if name == 'extract':
            hi, lo = int(op[2].atom), int(op[3].atom)
            if not 0 <= lo <= hi < source[1]:
                raise ValueError('invalid extraction')
            return ('bv', hi - lo + 1)
        if name in ('zero_extend', 'sign_extend'):
            return ('bv', source[1] + int(op[2].atom))
        if name in ('rotate_left', 'rotate_right'):
            return source
        if name == 'repeat':
            return ('bv', source[1] * int(op[2].atom))
    return None


def transform(text, operators=OPERATORS):
    if len(set(operators)) != len(operators) or not set(operators) <= set(OPERATORS):
        raise ValueError('operators must be unique supported SMT2 operator names')
    forms = parse(text)
    returns = {}
    for form in forms:
        if head(form) in ('define-fun', 'declare-fun'):
            returns[form.items[1].atom] = sort(form.items[3])
    declared = {f.items[1].atom for f in forms if head(f) in ('declare-sort', 'define-sort', 'declare-fun', 'define-fun')}
    replacements, functions = [], {}
    def walk(node, env):
        h = head(node)
        if h == 'let':
            bindings, body = node.items[1:]
            local = {b.items[0].atom: expression_sort(b.items[1], env, returns) for b in bindings.items}
            for binding in bindings.items:
                walk(binding.items[1], env)
            walk(body, {**env, **local})
            return
        if h in operators:
            if len(node.items) != 3:
                raise ValueError('unexpected arithmetic arity')
            a, b = (expression_sort(v, env, returns) for v in node.items[1:])
            if not a or a[0] != 'bv' or a != b:
                raise ValueError('cannot establish arithmetic operand widths')
            width = a[1]
            name = f'rvw_uf_{h}_{width}'
            if name in declared or '|' + name + '|' in declared:
                raise ValueError('UF name collision')
            record = functions.setdefault((h, width), {'operator': h, 'width': width, 'function': name, 'occurrences': 0})
            record['occurrences'] += 1
            token = node.items[0]
            replacements.append((token.start, token.end, name))
        for child in node.items:
            if child.atom is None:
                walk(child, env)
    for form in forms:
        if head(form) == 'define-fun':
            env = {arg.items[0].atom: sort(arg.items[1]) for arg in form.items[2].items}
            walk(form.items[4], env)
        elif head(form) == 'assert':
            walk(form.items[1], {})
    output = text
    for start, end, name in sorted(replacements, reverse=True):
        output = output[:start] + name + output[end:]
    widths = sorted({v['width'] for v in functions.values()})
    for width in widths:
        alias = f'rvw_uf_bits_{width}'
        if alias in declared or '|' + alias + '|' in declared:
            raise ValueError('UF sort name collision')
    # Named bit-vector sorts also work with SMTBMC's state unrolling path.
    declarations = ''.join(f'(define-sort rvw_uf_bits_{w} () (_ BitVec {w}))\n' for w in widths)
    declarations += ''.join(f'(declare-fun {v["function"]} (rvw_uf_bits_{v["width"]} rvw_uf_bits_{v["width"]}) rvw_uf_bits_{v["width"]})\n'
                            for _, v in sorted(functions.items()))
    if declarations:
        first = next((f.start for f in forms if head(f) not in ('set-logic', 'set-option', 'set-info')), len(text))
        output = output[:first] + declarations + output[first:]
    return output, list(functions.values())


def rewrite_file(path, operators):
    path = Path(path)
    metadata = path.with_suffix(path.suffix + '.rvw-uf.json')
    original = path.read_bytes()
    digest = sha256(original).hexdigest()
    if metadata.exists() and json.loads(metadata.read_text())['transformed_sha256'] == digest:
        return
    text, functions = transform(original.decode(), operators)
    transformed = text.encode()
    path.write_bytes(transformed)
    metadata.write_text(json.dumps({'schema': 'rvw.formal-smt-uf/1', 'functions': functions,
        'operators': list(operators), 'transformer_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'original_sha256': digest, 'transformed_sha256': sha256(transformed).hexdigest()}, indent=2) + '\n')
