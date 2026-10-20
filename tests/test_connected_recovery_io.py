"""Bounded Windows file-lock recovery; no GIS artifacts or routers required."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from backend.app import connected_jobs, simulation_jobs
from backend.app.connected_simulation import ConnectedScenarioConfig
from backend.app.simulation_jobs import JobStore, atomic_json
from backend.app.simulation_worker import run_claimed


def pending_job(tmp_path):
    store = JobStore(tmp_path)
    store.create(ConnectedScenarioConfig(fleetSize=1, carCount=1, bookingCount=0))
    return store, store.claim()


def result_for(status):
    return {'runId': status['id'], 'events': [], 'simulationDurationSeconds': 1,
            'counts': {'requested': 0, 'completed': 0}, 'routingIdentities': {}}


def test_atomic_replace_recovers_transient_lock_without_partial_publication(tmp_path, monkeypatch):
    target = tmp_path/'status.json'
    atomic_json(target, {'status': 'RUNNING'})
    original = simulation_jobs.os.replace
    attempts, delays = [], []
    monkeypatch.setattr('time.sleep', delays.append)

    def replacing(source, destination):
        attempts.append(Path(source))
        assert json.loads(target.read_text()) == {'status': 'RUNNING'}
        assert json.loads(Path(source).read_text()) == {'status': 'COMPLETED'}
        if len(attempts) <= 3:
            raise PermissionError('transient Windows reader lock')
        return original(source, destination)

    monkeypatch.setattr(simulation_jobs.os, 'replace', replacing)
    atomic_json(target, {'status': 'COMPLETED'})
    assert len(attempts) == 4 and len(set(attempts)) == 1
    assert delays == [.005]*3
    assert json.loads(target.read_text()) == {'status': 'COMPLETED'}
    assert not list(tmp_path.glob('.*.tmp'))


def test_atomic_replace_terminal_lock_is_bounded_and_preserves_previous_bytes(tmp_path, monkeypatch):
    target = tmp_path/'status.json'
    atomic_json(target, {'status': 'RUNNING'})
    previous = target.read_bytes()
    attempts, delays = [], []
    monkeypatch.setattr('time.sleep', delays.append)

    def denied(*args):
        attempts.append(args)
        raise PermissionError('persistent reader lock')

    monkeypatch.setattr(simulation_jobs.os, 'replace', denied)
    with pytest.raises(PermissionError, match='persistent reader lock'):
        atomic_json(target, {'status': 'COMPLETED'})
    assert len(attempts) == 20 and delays == [.005]*19
    assert target.read_bytes() == previous
    assert not list(tmp_path.glob('.*.tmp'))


def test_atomic_replace_does_not_retry_unrelated_os_errors(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr('time.sleep', lambda _: pytest.fail('Unrelated I/O must not retry'))

    def broken(*args):
        calls.append(args)
        raise OSError('disk unavailable')

    monkeypatch.setattr(simulation_jobs.os, 'replace', broken)
    with pytest.raises(OSError, match='disk unavailable'):
        atomic_json(tmp_path/'result.json', {'ok': True})
    assert len(calls) == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('blocked_reads', [3, 20])
def test_status_read_lock_recovers_or_exhausts_without_mutation(tmp_path, monkeypatch, blocked_reads):
    store, status = pending_job(tmp_path)
    target = store.path(status['id'])/'status.json'
    previous = target.read_bytes()
    original = Path.read_text
    attempts, delays = [], []
    monkeypatch.setattr('time.sleep', delays.append)

    def read(path, *args, **kwargs):
        if path == target:
            attempts.append(path)
            if len(attempts) <= blocked_reads:
                raise PermissionError('reader denied')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read)
    if blocked_reads == 20:
        with pytest.raises(PermissionError, match='reader denied'):
            store.read(status['id'])
        assert len(attempts) == 20 and delays == [.005]*19
    else:
        assert store.read(status['id']) == status
        assert len(attempts) == 4 and delays == [.005]*3
    assert target.read_bytes() == previous


def test_missing_job_remains_immediate_404(tmp_path, monkeypatch):
    monkeypatch.setattr('time.sleep', lambda _: pytest.fail('Missing jobs must not retry'))
    with pytest.raises(HTTPException) as exc:
        JobStore(tmp_path).read('a'*32)
    assert exc.value.status_code == 404
    assert exc.value.detail['code'] == 'JOB_NOT_FOUND'


@pytest.mark.parametrize('blocked_name', ['event-log.json', 'result.json'])
def test_worker_cannot_publish_completion_after_terminal_result_io_failure(tmp_path, monkeypatch, blocked_name):
    store, status = pending_job(tmp_path)
    original = simulation_jobs.os.replace
    attempts = []
    monkeypatch.setattr('time.sleep', lambda _: None)

    def replacing(source, destination):
        if Path(destination).name == blocked_name:
            attempts.append(destination)
            raise PermissionError('publication denied')
        return original(source, destination)

    monkeypatch.setattr(simulation_jobs.os, 'replace', replacing)

    async def execute(*_):
        return result_for(status)

    outcome = asyncio.run(run_claimed(store, status, execute))
    assert outcome['status'] == 'FAILED'
    assert outcome['error']['code'] == 'SIMULATION_FAILED'
    assert len(attempts) == 20
    assert not (store.path(status['id'])/'result.json').exists()
    assert not list(store.path(status['id']).glob('.*.tmp'))
    with pytest.raises(HTTPException) as exc:
        store.result(status['id'])
    assert exc.value.status_code == 409


def test_failed_completion_status_stays_unpublished_and_recovers_as_interrupted(tmp_path, monkeypatch):
    store, status = pending_job(tmp_path)
    original = simulation_jobs.os.replace
    monkeypatch.setattr('time.sleep', lambda _: None)

    def replacing(source, destination):
        if Path(destination).name == 'status.json':
            raise PermissionError('status publication denied')
        return original(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(simulation_jobs.os, 'replace', replacing)
        with pytest.raises(PermissionError):
            store.finish(status['id'], result=result_for(status))
    assert store.read(status['id'])['status'] == 'RUNNING'
    assert json.loads((store.path(status['id'])/'result.json').read_text()) == result_for(status)
    with pytest.raises(HTTPException):
        store.result(status['id'])
    # Recovery requires the same worker lease as the real worker main loop.
    with simulation_jobs.file_lock(tmp_path/'.worker.lock', blocking=False):
        store.interrupt_abandoned()
    assert store.read(status['id'])['status'] == 'INTERRUPTED'
    assert not list(store.path(status['id']).glob('.*.tmp'))


@pytest.mark.parametrize(('configured', 'expected'), [(5, 20), (30, 30)])
def test_connected_http_timeout_floor_retains_explicit_longer_configuration(monkeypatch, configured, expected):
    captured = {}

    async def readiness(*args, **kwargs):
        return {}, {}

    class ReachedClient(Exception):
        pass

    def client(**kwargs):
        captured.update(kwargs)
        raise ReachedClient

    monkeypatch.setattr(connected_jobs, 'Settings', lambda: SimpleNamespace(osrm_timeout_seconds=configured))
    monkeypatch.setattr(connected_jobs, 'require_simulation_headroom', lambda _: None)
    monkeypatch.setattr(connected_jobs, 'connected_readiness', readiness)
    monkeypatch.setattr(connected_jobs, 'load_zones', lambda: [])
    monkeypatch.setattr(connected_jobs, 'read_anchor_catalog', lambda _: ({}, {}))
    monkeypatch.setattr(connected_jobs, 'connected_inputs', lambda *args: ([], [], {}, {}))
    monkeypatch.setattr(connected_jobs.httpx, 'AsyncClient', client)
    with pytest.raises(ReachedClient):
        asyncio.run(connected_jobs.execute_connected_live(object(), 'fixture-run'))
    assert captured['timeout'] == expected
    assert captured['trust_env'] is False
    assert captured['limits'].max_connections == 2


@pytest.mark.parametrize(('configured', 'expected'), [(3, 20), (30, 30)])
def test_connected_context_timeout_floor_is_local_and_preserves_mode_identity(monkeypatch, configured, expected):
    from backend.app import connected_context as module
    settings = SimpleNamespace(osrm_timeout_seconds=configured)
    monkeypatch.setattr(module, 'Settings', lambda: settings)
    car, motorbike = module.connected_context('CAR'), module.connected_context('MOTORBIKE')
    assert car.osrm_timeout_seconds == motorbike.osrm_timeout_seconds == expected
    assert settings.osrm_timeout_seconds == configured
    assert car.vehicle_type == 'CAR' and motorbike.vehicle_type == 'MOTORBIKE'
    assert car.profile == 'car' and motorbike.profile == 'motorbike'
    assert car.routing_dir != motorbike.routing_dir
    assert car.osrm_base_url != motorbike.osrm_base_url
