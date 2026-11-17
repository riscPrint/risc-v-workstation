import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_fetch', ROOT / 'scripts/fetch-native.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def record(archive):
    return dict(tool='fixture', version='1', host='fixture', status='verified_metadata',
                url=archive.as_uri(), sha256=hashlib.sha256(archive.read_bytes()).hexdigest())


def test_manifest_declares_unknowns():
    rows=json.loads((ROOT/'scripts/native-manifest.json').read_text())['archives']
    assert len({(r['tool'],r['host']) for r in rows})==len(rows)
    assert any(r['status']=='unverified' for r in rows)
    assert any(r['tool']=='Sail' and r['status']=='verified_metadata' for r in rows)
    for row in rows:
        if row['status']=='unverified':
            assert row['url'] is None and row['sha256'] is None


def test_fetch_verifies_before_install(tmp_path):
    archive=tmp_path/'input.tgz'
    with tarfile.open(archive,'w:gz') as tar:
        item=tarfile.TarInfo('bin/fixture');item.size=2;tar.addfile(item,io.BytesIO(b'ok'))
    row=record(archive);prefix=tmp_path/'prefix'
    target=fetch.install(row,prefix,dry=True)
    assert not prefix.exists()
    fetch.install(row,prefix)
    assert (target/'bin/fixture').read_bytes()==b'ok'
    fetch.install(row,prefix,check=True)
    row['sha256']='0'*64
    with pytest.raises(ValueError,match='checksum'):
        fetch.install(row,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_refuse_unknown_and_repo_prefix(tmp_path):
    with pytest.raises(ValueError,match='unverified'):
        fetch.install(dict(status='unverified'),tmp_path/'prefix',dry=True)
    with pytest.raises(ValueError,match='outside'):
        fetch.install({},ROOT/'.tools/native',dry=True)


def test_refuse_archive_traversal(tmp_path):
    archive=tmp_path/'bad.tgz'
    with tarfile.open(archive,'w:gz') as tar:
        item=tarfile.TarInfo('../escaped');item.size=1;tar.addfile(item,io.BytesIO(b'x'))
    with pytest.raises(ValueError,match='unsafe'):
        fetch.install(record(archive),tmp_path/'prefix')
    assert not (tmp_path/'prefix').exists()


def test_installed_payload_mutation_is_rejected(tmp_path):
    archive = tmp_path / 'input.tgz'
    with tarfile.open(archive, 'w:gz') as tar:
        item = tarfile.TarInfo('bin/fixture')
        item.size = 2
        tar.addfile(item, io.BytesIO(b'ok'))
    row = record(archive)
    target = fetch.install(row, tmp_path / 'prefix')
    (target / 'bin/fixture').write_bytes(b'changed')
    with pytest.raises(ValueError, match='payload identity'):
        fetch.install(row, tmp_path / 'prefix', check=True)
