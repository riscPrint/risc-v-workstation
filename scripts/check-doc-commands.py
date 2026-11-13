#!/usr/bin/env python3
"""Extract documented commands and check CLI syntax without running handlers."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parents[1]


def documents(root=ROOT):
    names = {'README.md', 'AGENTS.md', 'docs/BRING_YOUR_OWN_CORE.md',
             'docs/AGENT_SETUP.md', 'docs/AGENT_ARCH.md', 'docs/INTEGRATION_GUIDE.md', 'docs/ACT4.md'}
    import subprocess
    names.update(n for n in subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines()
                 if n.endswith('/README.md'))
    return [root / n for n in sorted(names) if (root / n).is_file()]


def extract(path):
    lines = path.read_text().splitlines()
    fenced = False
    language = ''
    i = 0
    while i < len(lines):
        line = lines[i]
        number = i + 1
        if line.lstrip().startswith('```'):
            fenced = not fenced
            language = line.strip()[3:]
            i += 1
            continue
        if fenced and language in ('', 'sh', 'bash', 'shell', 'console'):
            while line.rstrip().endswith('\\') and i + 1 < len(lines):
                i += 1
                line = line.rstrip()[:-1] + ' ' + lines[i].strip()
            candidates = [line]
        else:
            candidates = re.findall(r'`([^`\n]+)`', line)
        for candidate in candidates:
            # Preserve shell separators, but never execute shell expansions.
            try:
                lexer = shlex.shlex(candidate, posix=True, punctuation_chars=';&|>')
                lexer.whitespace_split = True
                tokens = list(lexer)
            except ValueError:
                continue
            for start, token in enumerate(tokens):
                if (start == 0 or tokens[start - 1] in ('&&', ';', '|')) and (token == 'rvw' or token.startswith(('scripts/', 'RiscvSim/'))):
                    argv = tokens[start:]
                    for end, value in enumerate(argv):
                        if value in ('&&', ';', '|', '>', '>>', '2>&1'):
                            argv = argv[:end]
                            break
                    yield dict(file=str(path.relative_to(ROOT)), line=number,
                               kind='command' if fenced else 'inline', argv=argv)
        i += 1


def symbolic_values(argv, parser):
    """Use a legal typed value for shell variables, without expanding the shell."""
    node = parser
    actions = []
    for token in argv:
        for action in node._actions:
            if isinstance(action, argparse._SubParsersAction) and token in action.choices:
                node = action.choices[token]
                break
        actions.extend(node._actions)
    result = list(argv)
    for i, token in enumerate(result):
        if '$' not in token or i == 0:
            continue
        action = next((a for a in actions if result[i - 1] in a.option_strings), None)
        if action and action.choices:
            result[i] = str(next(iter(action.choices)))
        elif action and action.type in (int, float):
            result[i] = '1'
    return result


def validate_fragment(argv, parser):
    """Check named paths and flags in prose; required operands belong to examples."""
    node = parser
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == '--':
            return None
        if re.search(r'[|/\[\]<>]|\.\.\.', token):
            return None
        children = next((a.choices for a in node._actions if isinstance(a, argparse._SubParsersAction)), {})
        if token in children:
            node = children[token]
        elif token.startswith('--'):
            option = token.split('=', 1)[0]
            action = node._option_string_actions.get(option)
            if action is None:
                return 'unknown option: ' + option
            if action.nargs != 0 and '=' not in token:
                i += 1
        elif children:
            return 'unknown command: ' + token
        i += 1
    return None


def validate(record, parser):
    argv = record['argv']
    if argv[0] != 'rvw':
        return None  # Script paths are inventoried separately; no native launches.
    if '→' in argv:
        return None
    if record['kind'] == 'inline':
        return validate_fragment(argv[1:], parser)
    if any(re.search(r'\.\.\.|[|\[\]<>]', t) for t in argv):
        return None  # A command name or usage notation is not a runnable example.
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            parser.parse_args(symbolic_values(argv[1:], parser))
    except SystemExit as exc:
        if exc.code:
            return str(exc) + ': ' + ' '.join(argv)
    return None


def main():
    from rvw.cli import build_parser
    parser = build_parser()
    records = [record for path in documents() for record in extract(path)]
    errors = [dict(record, error=error) for record in records if (error := validate(record, parser))]
    print(json.dumps({'commands': len(records), 'records': records, 'errors': errors}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
