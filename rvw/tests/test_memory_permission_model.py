import hashlib
import json
import sqlite3
from pathlib import Path
import pytest
from rvw.memory.permission_model import load
from rvw.memory.tilelink_bind import monitor, generate
from test_memory_tilelink_bind import fixture

pytestmark = pytest.mark.fast


def test_generated_permission_projection_matches_the_exhausted_model():
    projection=load()
    source=Path(__file__).resolve().parents[2]/'SpinalChecks/coherence/model.py'
    assert projection['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert projection['model_states']==141 and projection['model_edges']==218
    assert projection['scope'].startswith('permission projection only')
    assert [2, 2] not in projection['states']
    text=monitor(1, 1, 16, 64, 0, 16, False, projection=projection)
    assert 'projection_previous=0' in text and 'Generated finite permission projection' in text


def test_incomplete_model_cannot_supply_a_generated_monitor(monkeypatch):
    import rvw.memory.permission_model as model
    monkeypatch.setattr(model.runpy, 'run_path', lambda path: {'explore': lambda: ({'verdict': 'inconclusive'}, {})})
    with pytest.raises(ValueError, match='exhausted'):
        model.load()


def test_real_c6_simple_type_uses_declared_family_and_exact_members(tmp_path):
    db, profile, config, _, _ = fixture(tmp_path)
    config['bus_family']='spinal-tilelink'
    with sqlite3.connect(db) as connection:
        connection.execute('ALTER TABLE bundles ADD COLUMN path TEXT')
        connection.execute('ALTER TABLE signals ADD COLUMN spinal_path TEXT')
        for c, client in enumerate(config['clients']):
            path=f'client{c}_bus'
            connection.execute("UPDATE bundles SET class_name='Bus', path=? WHERE id=?", (path, c+1))
            for n, channel in enumerate('abcde'):
                connection.execute('INSERT INTO bundles VALUES (?,1,?,?)', (10+c*5+n, 'Channel'+channel.upper(), path+'.'+channel+'.payload'))
            for name, identity in client['signals'].items():
                channel, field=name.split('_', 1)
                suffix='.'+field if field in ('valid', 'ready') else '.payload.'+field
                connection.execute('UPDATE signals SET spinal_path=? WHERE id=?', (path+'.'+channel+suffix, identity))
    profile.write_text(json.dumps(config))
    result=generate(db, profile, tmp_path/'typed')
    assert result['bus_type_evidence']==['declared-family-and-channel-structure']*2
    assert result['permission_model']['model_states']==141
    signals=config['clients'][0]['signals']
    signals['b_valid'], signals['c_valid']=signals['c_valid'], signals['b_valid']
    profile.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='typed Bus member'):
        generate(db, profile, tmp_path/'wrong-member')
    config.pop('bus_family')
    profile.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='declared family'):
        generate(db, profile, tmp_path/'undeclared')
    config['bus_family']='spinal-tilelink'
    profile.write_text(json.dumps(config))
    with sqlite3.connect(db) as connection:
        connection.execute("DELETE FROM bundles WHERE class_name='ChannelE'")
    with pytest.raises(ValueError, match='channel structure'):
        generate(db, profile, tmp_path/'missing-channel')
