"""V5 API contract and router-free persisted replay over explicit domain fixtures."""
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.connected_jobs import create_connected_router
from backend.app.connected_simulation import ConnectedScenarioConfig, connected_inputs, load_zones, simulate_connected
from backend.app.simulation_jobs import JobStore
from scripts.m3_fixture_travel import fixture_identities
from test_connected_domain import ConnectedFixtureTravel, fixture_anchors


async def ready(*_):
    return {}, {}


def app(store, readiness=ready):
    application = FastAPI()
    application.include_router(create_connected_router(store, readiness=readiness))
    return TestClient(application)


def complete(store, config, run_id):
    zones = load_zones()
    vehicles, demand, vmeta, bmeta = connected_inputs(config, fixture_anchors(), zones)
    identities = {mode: {**identity, 'regionId': 'nvmr-connected'} for mode, identity in fixture_identities().items()}
    result = asyncio.run(simulate_connected(config, vehicles, demand,
        {mode: ConnectedFixtureTravel(mode) for mode in identities}, identities, run_id, zones, vmeta, bmeta))
    assert store.claim()['id'] == run_id
    store.finish(run_id, result)
    return result


def test_v5_snapshot_selected_routes_and_reopened_replay_need_no_osrm(tmp_path):
    store = JobStore(tmp_path)
    client = app(store)
    config = ConnectedScenarioConfig(fleetSize=100, carCount=40, bookingCount=20,
        distribution={'nearestNeighborSampleSize': 0})
    created = client.post('/api/v5/simulation/jobs', json=config.model_dump(mode='json'))
    assert created.status_code == 202
    run_id = created.json()['id']
    prefix = '/api/v5/simulation/jobs/'+run_id
    assert client.get(prefix+'/snapshot').status_code == 409
    result = complete(store, config, run_id)
    # New API/store objects demonstrate replay depends only on persisted output.
    client = app(JobStore(tmp_path))
    summary = client.get(prefix+'/result?summary=true').json()
    assert summary['schemaVersion'] == 'gsm-nvmr-connected-result/v1'
    assert 'routes' not in summary
    projected = client.get(prefix+'/snapshot?timeSeconds=0').json()
    assert projected['counts']['total'] == len(projected['vehicles']) == 100
    assert all('isMoving' in v and 'coordinates' not in v for v in projected['vehicles'])
    assignment = result['assignments'][0]
    now = assignment['pickupAtSeconds']+.1
    vehicle = client.get(prefix+'/vehicles/'+assignment['vehicleId'], params={'timeSeconds': now})
    assert vehicle.status_code == 200
    detail = client.get(prefix+'/bookings/'+assignment['bookingId']).json()
    assert detail['schemaVersion'] == 'gsm-simulation-booking-detail/v1'
    assert detail['regionId'] == 'nvmr-connected'
    route = client.get(prefix+'/routes/'+detail['tripLeg']['routeRef']).json()
    assert route['schemaVersion'] == 'gsm-simulation-route/v1'
    assert route['routingIdentity'] == result['routingIdentities'][assignment['vehicleType']]
    assert len(route['coordinates']) >= 2 and 'cumulativeMeters' not in route
    assert client.get(prefix+'/vehicles/missing').status_code == 404
    assert client.get(prefix+'/routes/missing').status_code == 404
    assert client.get(prefix+'/snapshot?timeSeconds=-1').status_code == 422
    assert client.get(prefix+'/snapshot?timeSeconds=nan').status_code == 422


def test_v5_unready_graph_refuses_job_before_persistence(tmp_path):
    store = JobStore(tmp_path)
    async def unavailable(*_):
        raise HTTPException(503, {'code': 'CONNECTED_NOT_READY', 'message': 'Explicit unready fixture'})
    response = app(store, unavailable).post('/api/v5/simulation/jobs',
        json=ConnectedScenarioConfig(fleetSize=1, carCount=1).model_dump(mode='json'))
    assert response.status_code == 503
    assert not store.statuses()
