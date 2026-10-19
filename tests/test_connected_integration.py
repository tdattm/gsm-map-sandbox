"""Shared worker/store compatibility boundary, without local GIS dependencies."""
import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from backend.app.connected_jobs import create_connected_router
from backend.app.connected_simulation import ConnectedScenarioConfig
from backend.app.regional_jobs import create_regional_router
from backend.app.simulation import SimulationConfig
from backend.app.simulation_jobs import JobStore, atomic_json, create_router, file_lock
from backend.app.simulation_worker import run_claimed


def small_config():
    return ConnectedScenarioConfig(fleetSize=1, carCount=1, bookingCount=0)


def minimal_fixture_result(run_id):
    # Publication/lifecycle fixture only; not accepted scientific or routing evidence.
    return {'runId': run_id, 'events': [], 'simulationDurationSeconds': 1,
        'counts': {'requested': 0, 'completed': 0}, 'routingIdentities': {}}


def test_worker_selects_v5_config_and_new_manifest_version(tmp_path):
    store = JobStore(tmp_path)
    created = store.create(small_config())
    manifest = json.loads((store.path(created['id'])/'input.json').read_text())
    assert manifest['schemaVersion'] == 'gsm-nvmr-connected-job/v1'
    assert manifest['engineVersion'] == 'heap-grid-connected/v1'
    async def execute(config, run_id, cancelled, progress, save):
        assert isinstance(config, ConnectedScenarioConfig)
        save({'runId': run_id, 'fixtureOnly': True})
        return minimal_fixture_result(run_id)
    result = asyncio.run(run_claimed(store, store.claim(), execute))
    assert result['status'] == 'COMPLETED'
    assert JobStore(tmp_path).result(created['id'])['runId'] == created['id']
    assert (store.path(created['id'])/'prepared-input.json').is_file()


def test_v5_cancellation_cannot_be_resurrected_by_late_executor(tmp_path):
    store = JobStore(tmp_path)
    created = store.create(small_config())
    async def execute(config, run_id, cancelled, progress, save):
        store.cancel(run_id)
        assert await cancelled()
        return minimal_fixture_result(run_id)
    assert asyncio.run(run_claimed(store, store.claim(), execute))['status'] == 'CANCELLED'
    assert not (store.path(created['id'])/'result.json').exists()
    with pytest.raises(HTTPException) as error:
        store.result(created['id'])
    assert error.value.status_code == 409


def test_v5_failure_and_crash_recovery_never_publish_success(tmp_path):
    store = JobStore(tmp_path)
    created = store.create(small_config())
    async def execute(*_):
        raise HTTPException(503, {'code': 'CONNECTED_ROUTER_OUTAGE'})
    failed = asyncio.run(run_claimed(store, store.claim(), execute))
    assert failed['status'] == 'FAILED' and failed['error']['code'] == 'CONNECTED_ROUTER_OUTAGE'
    assert not (store.path(created['id'])/'result.json').exists()
    abandoned = store.create(small_config())
    store.claim()
    with file_lock(tmp_path/'.worker.lock', blocking=False):
        store.interrupt_abandoned()
    assert store.read(abandoned['id'])['status'] == 'INTERRUPTED'


def test_v5_immutable_input_tampering_rejected_before_executor(tmp_path):
    store = JobStore(tmp_path)
    created = store.create(small_config())
    path = store.path(created['id'])/'input.json'
    raw = json.loads(path.read_text())
    raw['config']['seed'] = 'tampered'
    atomic_json(path, raw)
    async def never(*_):
        raise AssertionError('Executor must not run')
    failed = asyncio.run(run_claimed(store, store.claim(), never))
    assert failed['status'] == 'FAILED' and 'modified' in failed['error']['message']


def test_v5_ids_are_inaccessible_to_v3_v4_and_queue_is_shared(tmp_path):
    store = JobStore(tmp_path, capacity=1)
    v5 = store.create(small_config())
    async def ready(*_):
        return {}, {}
    app = FastAPI()
    app.include_router(create_router(store))
    app.include_router(create_regional_router(store, readiness=ready))
    app.include_router(create_connected_router(store, readiness=ready))
    with TestClient(app) as client:
        for version in (3, 4):
            base = f'/api/v{version}/simulation/jobs/{v5["id"]}'
            for suffix in ('', '/result', '/snapshot'):
                assert client.get(base+suffix).status_code == 404
            assert client.post(base+'/cancel').status_code == 404
        assert client.get('/api/v5/simulation/jobs').json()['jobs'][0]['id'] == v5['id']
        with pytest.raises(HTTPException) as error:
            store.create(SimulationConfig())
        assert error.value.status_code == 429
        client.post(f'/api/v5/simulation/jobs/{v5["id"]}/cancel')
        v3 = store.create(SimulationConfig())
        assert client.get(f'/api/v5/simulation/jobs/{v3["id"]}').status_code == 404
