import hashlib
import json
import zipfile

import pytest

from backend.app.connected_analytics import fleet_state_buckets, STATES
from backend.app.replay_bundle import bundle_file, verify_bundle
from scripts.connected_replay import restore


def test_weighted_buckets_integrate_all_transitions_and_equal_time_changes():
    raw = {'runId': 'integral', 'config': {'fleetSize': 2}, 'simulationDurationSeconds': 20,
           'vehicles': [{'id': 'a'}, {'id': 'b'}], 'timelines': {
               'a': [{'time': 0, 'state': 'IDLE'}, {'time': 3, 'state': 'ASSIGNED'},
                     {'time': 3, 'state': 'ON_TRIP'}, {'time': 19, 'state': 'IDLE'}],
               'b': [{'time': 0, 'state': 'OFFLINE'}, {'time': 10, 'state': 'IDLE'}]}}
    original = json.dumps(raw)
    series = fleet_state_buckets(raw, limit=2)
    assert series['points'][0] == {'timeSeconds': 0, 'endSeconds': 10, 'OFFLINE': 1., 'IDLE': .3, 'ASSIGNED': 0., 'ON_TRIP': .7}
    assert series['points'][1]['IDLE'] == 1.1
    assert series['points'][1]['ON_TRIP'] == .9
    integrals = {s: sum(p[s] * (p['endSeconds'] - p['timeSeconds']) for p in series['points']) for s in STATES}
    assert integrals == {'OFFLINE': 10., 'IDLE': 14., 'ASSIGNED': 0., 'ON_TRIP': 16.}
    assert all(sum(p[s] for s in STATES) == pytest.approx(2) for p in series['points'])
    assert json.dumps(raw) == original


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/outside', 'a\\outside'])
def test_bundle_paths_cannot_escape(tmp_path, name):
    with pytest.raises(ValueError):
        bundle_file(tmp_path, name)


def test_restore_refuses_overwrite_and_unsafe_archive(tmp_path):
    target = tmp_path/'existing'; target.mkdir()
    with pytest.raises(ValueError, match='already exists'):
        restore(tmp_path/'none.zip', target)
    archive = tmp_path/'bad.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('../outside', 'bad')
    with pytest.raises(ValueError, match='Unsafe'):
        restore(archive, tmp_path/'new')
    assert not (tmp_path/'outside').exists()


def test_bundle_verification_detects_tamper(tmp_path):
    job = 'a'*32
    path = tmp_path/'jobs'/job/'status.json'; path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'id': job, 'status': 'COMPLETED'}))
    manifest = {'schemaVersion': 'gsm-connected-research-bundle/v1', 'jobId': job,
                'files': {f'jobs/{job}/status.json': {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}}
    for name in ['input.json', 'prepared-input.json', 'event-log.json', 'result.json']:
        extra = path.parent/name; extra.write_text('{}')
        manifest['files'][f'jobs/{job}/{name}'] = {'bytes': extra.stat().st_size, 'sha256': hashlib.sha256(extra.read_bytes()).hexdigest()}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    assert verify_bundle(tmp_path)['jobId'] == job
    path.write_text('tampered')
    with pytest.raises(ValueError, match='checksum'):
        verify_bundle(tmp_path)


def test_replay_factory_blocks_every_write_before_routing(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('GSM_REPLAY_BUNDLE', str(tmp_path))
    monkeypatch.setattr('scripts.connected_replay.verify_bundle', lambda _: {})
    monkeypatch.setattr('scripts.connected_replay.portable_map_status', lambda _: {})
    from scripts.connected_replay import create_app
    client = TestClient(create_app())
    for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        response = client.request(method, '/api/v5/simulation/jobs', json={})
        assert response.status_code == 405
        assert response.json()['error']['code'] == 'REPLAY_READ_ONLY'
    assert client.get('/api/v5/simulation/jobs').json() == {'jobs': []}
    assert not (tmp_path/'jobs').exists()
