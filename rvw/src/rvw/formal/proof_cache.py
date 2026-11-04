"""Exact prepared-input reuse. No cone approximation or remote trust inference."""
import hashlib
import json
import shutil
import tempfile
import sys
from pathlib import Path

from rvw.common.capture import canonical_json


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(out, script, snapshot):
    """Use complete elaborated models, assumptions, tools, environment and runner code.

    Only the owned output directory prefix is normalized. Source paths, source
    locations and every model byte otherwise remain part of the dependency rule.
    """
    def normalized(data):
        return data.replace(str(out).encode(), b'<rvw-out>')
    artifacts = {item['path']: hashlib.sha256(normalized((out / item['path']).read_bytes())).hexdigest()
                 for item in snapshot.artifacts}
    tools = snapshot.tools
    # checks includes the executable, launchers and detected native release payloads.
    dependencies = sorted((str(item.resolved), item.sha256) for item, _ in tools.checks)
    code = {p.name: digest(p) for p in Path(__file__).parent.glob('*.py')}
    common_code = {p.name: digest(p) for p in (Path(__file__).parent.parent / 'common').glob('*.py')}
    return {'schema': 'rvw.formal-proof-key/1', 'artifacts': artifacts,
            'script': normalized(script.encode()).decode(),
            'files': [(f['kind'], f['sha256']) for f in snapshot.files],
            'tools': dependencies, 'versions': tools.identities,
            'environment': snapshot.capture.record().get('env', {}),
            'formal_code': code, 'common_code': common_code,
            'python': {'version': sys.version, 'sha256': digest(sys.executable)}}


def key_for(identity):
    return hashlib.sha256(canonical_json(identity)).hexdigest()


def restore(root, identity, out):
    entry = Path(root) / key_for(identity)
    try:
        record = json.loads((entry / 'entry.json').read_text())
        if record['identity'] != json.loads(canonical_json(identity)):
            return False
        if not {'sby/model/design_prep.il', 'sby/logfile.txt', 'provenance.json'} <= record['files'].keys():
            return False
        for name, sha in record['files'].items():
            p = Path(name)
            if p.is_absolute() or '..' in p.parts or digest(entry / name) != sha:
                return False
        result = json.loads((entry / 'provenance.json').read_text())
        if not eligible(result):
            return False
        shutil.copytree(entry / 'sby', out / 'sby')
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def eligible(result):
    return (result.get('status') == 'pass' and result.get('assertions', 0) > 0
            and result.get('reachability', {}).get('status') == 'reachable'
            and not result.get('cause')
            and not result.get('input_snapshot', {}).get('problems'))


def publish(root, identity, out, result):
    if not eligible(result):
        return
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / key_for(identity)
    # A concurrent writer can win. Its complete immutable entry remains valid.
    if target.exists():
        return
    with tempfile.TemporaryDirectory(prefix='.proof-', dir=root) as directory:
        entry = Path(directory) / 'entry'
        entry.mkdir()
        shutil.copytree(out / 'sby', entry / 'sby')
        (entry / 'provenance.json').write_text(json.dumps(result))
        files = {p.relative_to(entry).as_posix(): digest(p) for p in entry.rglob('*') if p.is_file()}
        (entry / 'entry.json').write_bytes(canonical_json({'identity': identity, 'files': files}))
        try:
            entry.rename(target)
        except FileExistsError:
            pass
