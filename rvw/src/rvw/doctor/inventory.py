"""Shared optional tool inventory. Presence is not runtime qualification."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
from string import Template


def load():
    return json.loads(Path(__file__).with_name('tools.json').read_text())


def flags(profile):
    data = load()
    if profile not in data['profiles']:
        raise ValueError('unknown profile: ' + profile)
    return ['--with-' + flag for flag in data['profiles'][profile]]


def probe_path(probe):
    """Honor an explicit selector. Do not hide invalid selectors with PATH fallback."""
    if probe['kind'] == 'module':
        return probe['module'] if importlib.util.find_spec(probe['module']) else None
    variables = {**os.environ, 'RVW_HOME': os.environ.get('RVW_HOME', str(Path(__file__).resolve().parents[4]))}
    candidates = probe.get('candidates', [])
    if probe.get('env') and probe['env'] in os.environ:
        candidates = [os.environ[probe['env']]]
    elif probe.get('root_env') and probe['root_env'] in os.environ:
        candidates = [str(Path(os.environ[probe['root_env']]) / probe['relative'])]
    if probe.get('relative_executable') and probe.get('env') not in os.environ:
        executable = shutil.which(probe['relative_executable'])
        if executable:
            candidates = [*candidates, str(Path(executable).resolve().parent / probe['relative'])]
    for candidate in candidates:
        value = str(Path(Template(candidate).safe_substitute(variables)).expanduser())
        path = str(Path(value).absolute()) if probe['kind'] == 'file' and Path(value).is_file() else shutil.which(value) if probe['kind'] == 'executable' else None
        if path:
            return path
    return None


def report():
    records = []
    for tool in load()['tools']:
        paths = {probe['name']: probe_path(probe) for probe in tool['probes']}
        present = bool(paths) and all(paths.values())
        records.append(dict(name=tool['name'], area=tool['area'], paths=paths,
                            status='installed' if present else 'missing',
                            install_flag='--with-' + tool['flag'],
                            install_command='scripts/install.sh --with-' + tool['flag'],
                            qualification='presence only; runtime NOT RUN'))
    return records
