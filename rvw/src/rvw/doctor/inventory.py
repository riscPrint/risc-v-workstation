"""Shared optional tool inventory. Presence is not runtime qualification."""
import importlib.util
import json
import os
from pathlib import Path
import shutil


def load():
    return json.loads(Path(__file__).with_name('tools.json').read_text())


def flags(profile):
    data = load()
    if profile not in data['profiles']:
        raise ValueError('unknown profile: ' + profile)
    return ['--with-' + flag for flag in data['profiles'][profile]]


def report():
    records = []
    modules = {'cocotb': 'cocotb', 'pyuvm': 'pyuvm', 'wellen': 'pywellen'}
    for tool in load()['tools']:
        paths = {}
        for exe in tool['executables']:
            # Directory and plugin variables cannot stand in for executables.
            overrides = {'gem5.opt': 'RVW_GEM5', 'sail_riscv_sim': 'RVW_SAIL',
                         'spinaltrace-cli': 'SPINALTRACE_CLI', 'c++': 'CXX'}
            value = os.environ.get(overrides.get(exe, ''), exe)
            paths[exe] = shutil.which(value)
        if tool['name'] in modules:
            present = importlib.util.find_spec(modules[tool['name']]) is not None
        elif tool['name'] == 'native OoO':
            present = Path(os.environ.get('RVW_OOO_NATIVE', '/nonexistent')).is_file()
        else:
            present = bool(paths) and all(paths.values())
        records.append(dict(name=tool['name'], area=tool['area'], paths=paths,
                            status='installed' if present else 'missing',
                            install_flag='--with-' + tool['flag'],
                            install_command='scripts/install.sh --with-' + tool['flag'],
                            qualification='presence only; runtime NOT RUN'))
    return records
