"""Lower module-target checker bindings before finite SVA expansion."""
import re


def expand(source):
    from .temporal import Unsupported
    # Keep offsets stable while locating declarations outside comments/strings.
    text = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: ' ' * len(m[0]), source, flags=re.S)
    edits = []
    checkers = set()
    for match in re.finditer(r'\bchecker\s+(\w+)\s*(\([^;]*\))\s*;(.*?)\bendchecker\b', text, re.S):
        if match[1] in checkers:
            raise Unsupported('duplicate_checker', match[1])
        checkers.add(match[1])
        # Use explicit ANSI input ports. Default checker event arguments and
        # output arguments need separate scheduling/type support.
        if not re.match(r'\(\s*input\b', match[2]) or re.search(r'\b(output|inout|event|untyped)\b', match[2]):
            raise Unsupported('checker_ports', match[1])
        original = source[match.start():match.end()]
        original = re.sub(r'^checker\b', 'module', original)
        original = re.sub(r'\bendchecker$', 'endmodule', original)
        edits.append((match.start(), match.end(), original))
    modules = {}
    for match in re.finditer(r'\bmodule\s+(\w+)\b.*?\bendmodule\b', text, re.S):
        if match[1] in modules:
            raise Unsupported('duplicate_module', match[1])
        modules[match[1]] = match
    instances = set()
    for match in re.finditer(r'\bbind\s+(\w+)\s+(\w+)\s+(\w+)\s*(\([^;]*\))\s*;', text, re.S):
        target, checker, instance = match[1], match[2], match[3]
        if target not in modules or checker not in checkers:
            raise Unsupported('bind_target', target + ':' + checker)
        if (target, instance) in instances:
            raise Unsupported('duplicate_bind', instance)
        instances.add((target, instance))
        if not re.match(r'\(\s*\.\w+\s*\(', match[4]):
            raise Unsupported('bind_ports', instance)
        point = modules[target].end() - len('endmodule')
        edits.append((point, point, f'\n{checker} {instance}{match[4]};\n'))
        edits.append((match.start(), match.end(), ''))
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    if re.search(r'\b(checker|endchecker|bind)\b', re.sub(r'//[^\n]*|/\*.*?\*/', '', source, flags=re.S)):
        raise Unsupported('checker_or_bind', 'only explicit module-target named-port bindings supported')
    return source
