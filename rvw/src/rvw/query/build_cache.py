"""Content-keyed whole-design reuse for native HDL database builds."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(sources, top, options):
    """Hash inputs and selected tool files before choosing a cached elaboration."""
    from .hdl import _slang_plugin
    from . import hdl_ghdl
    config = dict(options)
    config.pop('timeout', None)
    frontend = config.get('frontend', 'yosys')
    paths = {Path(s).absolute() for s in sources}
    directories = []
    if frontend == 'slang':
        directories = [*(p.parent for p in paths), *(Path(p).absolute() for p in config.get('include_dirs', ()))]
    if frontend == 'chisel':
        roots = config.get('source_roots') or [str(p.parent) for p in paths]
        paths.update(p for root in roots for p in Path(root).absolute().rglob('*.scala'))
    for directory in directories:
        # The slang capture includes whole source/include directories.
        paths.update(p for p in directory.rglob('*') if p.is_file() and '.git' not in p.parts)
    selected = shutil.which(config.get('yosys', 'yosys'))
    if selected is None:
        raise ValueError('Yosys executable not found')
    tool = type('Tool', (), {'resolved': str(Path(selected).resolve())})()
    paths.add(Path(selected).resolve())
    if frontend == 'slang':
        paths.add(_slang_plugin(tool, config.get('slang')))
    if frontend == 'ghdl':
        paths.add(hdl_ghdl.plugin_path(tool, config.get('ghdl_plugin')))
        selected_ghdl = shutil.which('ghdl')
        if selected_ghdl is None:
            raise ValueError('GHDL executable not found')
        paths.add(Path(selected_ghdl).resolve())
        config['GHDL_PREFIX'] = os.environ.get('GHDL_PREFIX')
    if frontend == 'chisel':
        selected_firtool = shutil.which(config.get('firtool') or os.environ.get('RVW_FIRTOOL') or 'firtool')
        if selected_firtool is None:
            raise ValueError('firtool executable not found')
        paths.add(Path(selected_firtool).resolve())
    # Invalidate when the translator, schema or diagram writer changes.
    paths.update(Path(__file__).parent.glob('*.py'))
    paths.add(Path(__file__).with_name('schema.sql'))
    records = [(str(p), str(p.resolve()), digest(p)) for p in sorted(paths)]
    payload = {'schema': 'rvw.hdl-cache-key/1', 'sources': [str(Path(s).absolute()) for s in sources],
               'top': top, 'options': config, 'files': records}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def cached_build(builder, sources, top, out, cache_dir, options):
    cache = Path(cache_dir).absolute()
    out = Path(out).absolute()
    if any(cache == p.parent or p.parent in cache.parents for p in map(lambda s: Path(s).absolute(), sources)):
        raise ValueError('cache directory must be outside source directories')
    key = identity(sources, top, options)
    cache.mkdir(parents=True, exist_ok=True)
    entry, receipt = cache / (key + '.db'), cache / (key + '.json')
    hit = False
    try:
        record = json.loads(receipt.read_text())
        hit = entry.is_file() and digest(entry) == record['sha256']
    except (OSError, ValueError, KeyError):
        pass
    if hit:
        out.parent.mkdir(parents=True, exist_ok=True)
        publish(entry, out)
        result = {'db': str(out), 'top': top, 'frontend': __import__('rvw.query.hdl', fromlist=['FRONTENDS']).FRONTENDS[options.get('frontend', 'yosys')]}
    else:
        result = builder(sources, top, out, **options)
        # Source edits during a build must not publish a cache entry under the old key.
        if identity(sources, top, options) == key:
            publish(out, entry)
            receipt.write_text(json.dumps({'key': key, 'sha256': digest(entry)}))
    result['cache'] = {'key': key, 'status': 'hit' if hit else 'rebuilt', 'scope': 'whole-design'}
    return result


def publish(source, target):
    fd, name = tempfile.mkstemp(prefix=target.name + '.', dir=target.parent)
    os.close(fd)
    try:
        shutil.copyfile(source, name)
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)
