"""Translate older SBY bounded arguments for the qualified rIC3 1.5 CLI."""
import inspect
from pathlib import Path
import sys
import shlex


def translate(args):
    result, i = [], 0
    while i < len(args):
        if args[i] == '--bmc-max-k':
            result.extend(['--end', args[i + 1]])
            i += 2
        elif args[i:i + 2] == ['-v', '0']:
            i += 2
        else:
            result.append(args[i])
            i += 1
    return result


def wrapper(directory, executable):
    path = Path(directory) / 'ric3-sby-compat'
    code = ('import os, sys\n' + inspect.getsource(translate) +
            '\nos.execv(' + repr(executable) + ', [' + repr(executable) + '] + translate(sys.argv[1:]))\n')
    path.write_text('#!/bin/sh\nunset PYTHONEXECUTABLE PYTHONHOME PYTHONPATH\nexec ' +
                    shlex.quote(sys.executable) + ' -E -c ' + shlex.quote(code) + ' "$@"\n')
    path.chmod(0o755)
    return path.resolve()
