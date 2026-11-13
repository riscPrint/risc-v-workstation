"""Reuse conditional engine observations for self-contained regression jobs."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(job, tools):
    """Refuse jobs whose transitive source closure this cache cannot enumerate."""
    sections = {}
    section = None
    for raw in job.read_text().splitlines():
        line = raw.strip()
        if line.startswith('['):
            section = line
            sections[section] = []
        elif line:
            sections[section].append(line)
    files = {}
    for row in sections['[files]']:
        target, source = row.split(maxsplit=1)
        text = Path(source).read_text()
        if re.search(r'`include|\$readmem|\$fopen', text):
            return None
        files[target] = digest(source)
    for command in sections['[script]']:
        words = command.split()
        if words[0] == 'read_verilog':
            if any(w not in ('-formal', '-sv', *files) for w in words[1:]):
                return None
        elif not (re.fullmatch(r'prep -top [A-Za-z_][A-Za-z0-9_]*', command)
                  or command in ('async2sync', 'dffunmap')):
            return None
    return dict(schema='rvw.formal-regress-cache/1', files=files,
                options=sections['[options]'], engines=sections['[engines]'], script=sections['[script]'],
                tools=sorted((str(item.resolved), item.sha256) for item, _ in tools.checks),
                environment={k: v.replace(str(tools.directory), '<tool-bindings>')
                             for k, v in tools.env.items()},
                code={str(p.relative_to(Path(__file__).parents[1])): digest(p)
                      for folder in ('formal', 'common')
                      for p in (Path(__file__).parents[1] / folder).glob('*.py')})


def key_for(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def restore(root, value, directory):
    if value is None:
        return None
    entry = Path(root) / key_for(value)
    try:
        record = json.loads((entry / 'entry.json').read_text())
        if record['identity'] != json.loads(json.dumps(value)):
            return None
        for name, checksum in record['files'].items():
            if Path(name).is_absolute() or '..' in Path(name).parts or digest(entry / name) != checksum:
                return None
        observation = json.loads((entry / 'observation.json').read_text())
        if observation['formal_status'] not in ('proven', 'bounded-pass'):
            return None
        if not {'observation.json', 'sby/model/design_prep.il', 'sby/logfile.txt', 'run.log'} <= record['files'].keys():
            return None
        tools_directory = directory / 'sby'
        shutil.copytree(entry / 'sby', tools_directory)
        shutil.copyfile(entry / 'run.log', directory / 'run.log')
        if isinstance(observation.get('activation'), dict):
            if not {'activation-sby/model/design_prep.il', 'activation-sby/logfile.txt', 'activation.log'} <= record['files'].keys():
                return None
            shutil.copytree(entry / 'activation-sby', directory / 'activation-sby')
            shutil.copyfile(entry / 'activation.log', directory / 'activation.log')
        return observation
    except (OSError, ValueError, KeyError, TypeError):
        return None


def publish(root, value, directory, observation):
    if value is None or observation['formal_status'] not in ('proven', 'bounded-pass'):
        return
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / key_for(value)
    if target.exists():
        return
    with tempfile.TemporaryDirectory(prefix='.regress-', dir=root) as temporary:
        entry = Path(temporary) / 'entry'
        entry.mkdir()
        shutil.copytree(directory / 'sby', entry / 'sby')
        shutil.copyfile(directory / 'run.log', entry / 'run.log')
        if (directory / 'activation-sby').exists():
            shutil.copytree(directory / 'activation-sby', entry / 'activation-sby')
            shutil.copyfile(directory / 'activation.log', entry / 'activation.log')
        (entry / 'observation.json').write_text(json.dumps(observation))
        files = {p.relative_to(entry).as_posix(): digest(p) for p in entry.rglob('*') if p.is_file()}
        (entry / 'entry.json').write_text(json.dumps(dict(identity=value, files=files)))
        try:
            entry.rename(target)
        except FileExistsError:
            pass
