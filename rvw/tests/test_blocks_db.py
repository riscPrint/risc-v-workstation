"""The diagram entry reads stored artifacts without sbt or a core checkout."""
import gzip
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('suffix', ['.json', '.json.gz'])
def test_blocks_entry_exports_stored_diagram(cluster_db, tmp_path, suffix):
    out = tmp_path / ('diagram space' + suffix)
    env = dict(os.environ, PATH='/usr/bin:/bin', SPINAL_BOOM='/absent/core')
    run = subprocess.run([str(ROOT / 'SpinalBlocks/export.sh'), str(cluster_db), str(out)],
                         env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    with sqlite3.connect(cluster_db) as db:
        expected = gzip.decompress(db.execute(
            "SELECT content FROM artifacts WHERE name='blocks.json'").fetchone()[0])
    actual = gzip.decompress(out.read_bytes()) if suffix.endswith('.gz') else out.read_bytes()
    assert json.loads(actual) == json.loads(expected)


def test_blocks_entry_refuses_missing_artifact(cluster_db, tmp_path):
    database = tmp_path / 'no-blocks.db'
    shutil.copyfile(cluster_db, database)
    with sqlite3.connect(database) as db:
        db.execute("DELETE FROM artifacts WHERE name='blocks.json'")
    out = tmp_path / 'diagram.json'
    run = subprocess.run([str(ROOT / 'SpinalBlocks/export.sh'), str(database), str(out)],
                         capture_output=True, text=True)
    assert run.returncode != 0
    assert not out.exists()
