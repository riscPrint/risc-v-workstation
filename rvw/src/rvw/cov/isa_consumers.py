"""Probe configured ISA consumers without asserting ISA compliance."""
import json
import re
from pathlib import Path
import tomllib
from rvw.common.proc import run_group
from . import captured

REQUIRED = ('compiler', 'dut', 'reference', 'act', 'coverage')


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', value):
        return None
    parts = tuple(map(int, value.split('.')))
    return parts if len(parts) == 3 else (*parts, 0)


def read_probe(probe, root):
    kind = probe['kind']
    if kind in ('json', 'toml'):
        path = Path(root) / probe['path']
        text = captured.read_text(path)
        data = json.loads(text) if kind == 'json' else tomllib.loads(text)
        for key in probe.get('key', []):
            data = data[key]
        return data
    argv = probe['argv']
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
        raise ValueError('probe argv must be a nonempty string array')
    tool = captured.tool(argv[0])
    if kind not in ('gcc', 'command'):
        raise ValueError('unsupported ISA probe kind')
    args = ['-dM', '-E', '-x', 'c', '-'] if kind == 'gcc' else []
    result = run_group([str(tool.path), *argv[1:], *args], cwd=root,
                       capture=True, input='', timeout=10, env=captured.environment())
    if result.timed_out or result.returncode:
        raise ValueError('ISA probe failed or timed out')
    if kind == 'command':
        data = json.loads(result.stdout)
        if data.get('schema') != 'rvw.isa-consumer/1':
            raise ValueError('expected rvw.isa-consumer/1')
        return data
    macros = dict(re.findall(r'^#define (__riscv\w*) (\d+)\s*$', result.stdout, re.M))
    if '__riscv_xlen' not in macros:
        raise ValueError('compiler did not report RISC-V target macros')
    versions = {}
    for key, value in macros.items():
        if re.fullmatch(r'__riscv_(?:[iemafdqc]|z[a-z0-9]+|s[a-z0-9]+)', key):
            number = int(value)
            versions[key[8:]] = f'{number // 1000000}.{number // 1000 % 1000}'
            if number % 1000:
                versions[key[8:]] += f'.{number % 1000}'
    return {'xlen': int(macros['__riscv_xlen']), 'extensions': versions, 'options': {}}


def check(data, root):
    from .isa import extensions
    xlen, _ = extensions(data['isa'])
    probes = data.get('probes', {})
    if set(probes) - set(REQUIRED):
        raise ValueError('unknown ISA consumer probe')
    reports, unknown = {}, []
    for consumer in REQUIRED:
        if consumer not in probes:
            unknown.append(consumer)
            continue
        got = read_probe(probes[consumer], root)
        if got.get('xlen') != xlen:
            raise ValueError(f'{consumer}: XLEN contradicts manifest')
        versions = got.get('extensions')
        if not isinstance(versions, dict):
            raise ValueError(f'{consumer}: probe must report extension versions')
        declared_names = set(data['extensions'])
        # GCC exposes Zmmul when M is selected. M includes that subset.
        implied = {'zmmul'} if 'm' in declared_names else set()
        if declared_names - set(versions) or set(versions) - declared_names - implied:
            raise ValueError(f'{consumer}: extensions contradict manifest')
        unverified = []
        for name, item in data['extensions'].items():
            declared, measured = item['version'], versions[name]
            if measured is not None and (not isinstance(measured, str) or not measured):
                raise ValueError(f'{consumer}: invalid extension version')
            if version(declared) is None or version(measured) is None:
                unverified.append(name)
            elif version(measured) != version(declared):
                raise ValueError(f'{consumer}: {name} version contradicts manifest')
        options = got.get('options', {})
        if not isinstance(options, dict):
            raise ValueError(f'{consumer}: invalid options')
        missing_options = []
        for name, value in data['options'].items():
            if name == 'version_evidence':
                continue
            if name not in options:
                missing_options.append(name)
            elif options[name] != value:
                raise ValueError(f'{consumer}: {name} option contradicts manifest')
        reports[consumer] = {'observed': got, 'unverified_versions': unverified,
                             'unverified_options': missing_options}
        if unverified or missing_options:
            unknown.append(consumer)
    return reports, unknown
