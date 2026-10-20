"""NVMR v3 correctness/worker fixtures, independent from live OSRM evidence."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend.app.simulation import (BookingInput, IdleGrid, SimulationConfig, VehicleInput,
    generate_inputs, simulate, snapshot, validate_result)
from backend.app.simulation_jobs import JobStore, atomic_json, create_router, file_lock
from backend.app.simulation_worker import run_claimed
from scripts.m3_fixture_travel import RecordedTravel, fixture_identities, load_fixture
from test_a3 import FixtureTravel, road


def vehicle(id='GSM-01', mode='CAR', position=(0., 0.), **kw):
    return VehicleInput(id=id, vehicleType=mode, position=position, **kw)


def booking(id='B1', time=0, pickup=(2., 0.), dropoff=(3., 0.), mode='CAR'):
    return BookingInput(id=id, serviceType=mode, requestTimeSeconds=time, pickup=pickup, dropoff=dropoff)


def run(initial=None, demand=None, travels=None, wait=300, **kw):
    initial = [vehicle()] if initial is None else initial
    demand = [booking()] if demand is None else demand
    cfg = SimulationConfig(fleetSize=len(initial), carCount=sum(v.vehicleType == 'CAR' for v in initial),
        bookingCount=len(demand), maxWaitSeconds=wait, horizonSeconds=60, **kw)
    return asyncio.run(simulate(cfg, initial, demand, travels or {'CAR': FixtureTravel()}, fixture_identities(), 'test-run'))


def test_frozen_legacy_golden_matches_before_and_after_engine():
    golden = json.loads((Path(__file__).parent/'fixtures/m3/legacy-golden.json').read_text())
    initial = [vehicle(position=(float(i), 0.), id=f'GSM-{i+1:02}') for i in range(2)]
    ds = [booking(), booking('B2', 5), booking('B3', pickup=(3., 0.), dropoff=(4., 0.))]
    travel = FixtureTravel(lambda p, t: 0 if tuple(p) == tuple(t) else 10)
    result = run(initial, ds, {'CAR': travel}, wait=50, initialCandidates=2, maxCandidates=2)
    keys = ('bookingId', 'vehicleId', 'assignedAtSeconds', 'pickupAtSeconds', 'dropoffAtSeconds',
            'estimatedPickupEtaSeconds', 'tableEtaSeconds')
    assert [{k: a[k] for k in keys} for a in result['assignments']] == [{k: a[k] for k in keys} for a in golden['assignments']]
    for old, new in zip(golden['assignments'], result['assignments']):
        assert (old['pickupRoute'] is None) == (new['pickupRouteRef'] is None)
        assert old['tripRoute']['coordinates'] == result['routes'][new['tripRouteRef']]['coordinates']
    # Legacy sorts simultaneous events for serialization; v3 execution order is explicit.
    normalize = lambda events: sorted((e['timestampSeconds'], e['type'], e['bookingId'], e['vehicleId']) for e in events)
    assert normalize(result['events']) == normalize(golden['events'])


def test_inclusive_deadline_release_stationary_and_fifo_no_double_assignment():
    result = run(demand=[booking(), booking('B2', pickup=(3., 0.), dropoff=(4., 0.))], wait=50,
        travels={'CAR': FixtureTravel(lambda p, t: 0 if tuple(p) == tuple(t) else 10)})
    a, b = result['assignments']
    assert a['dropoffAtSeconds'] == b['assignedAtSeconds'] == b['pickupAtSeconds'] == 50
    assert b['pickupRouteRef'] is None
    assert [e['type'] for e in result['events'] if e['timestampSeconds'] == 50][0] == 'TRIP_COMPLETED'
    assert result['counts']['completed'] == 2
    assert validate_result(result)


def test_mixed_modes_and_online_accounting_at_lifecycle_checkpoints():
    result = run([vehicle('car'), vehicle('moto', 'MOTORBIKE'), vehicle('off', online=False)],
        [booking(), booking('B2', mode='MOTORBIKE')], {'CAR': FixtureTravel(), 'MOTORBIKE': FixtureTravel(lambda *_: 5)})
    assert [a['vehicleId'] for a in result['assignments']] == ['car', 'moto']
    for t in (0, 5, 10, 20, 50, 100):
        s = snapshot(result, t)
        c = s['counts']
        assert c['total'] == 3 == c['online']+c['offline']
        assert c['online'] == c['idle']+c['assigned']+c['onTrip'] == 2
        assert c['moving'] <= c['assigned']+c['onTrip']
        assert not any('coordinates' in v for v in s['vehicles'])
        assert s == snapshot(result, t)


def test_explicit_schedule_busy_offline_deferred_and_online_at_deadline():
    initial = [vehicle('A', schedule=((5, False), (60, True)))]
    result = run(initial, [booking(), booking('B2', 10)], wait=50)
    assert len(result['assignments']) == 1  # release at 50 offline; online 60 cannot reach pickup by 60
    assert snapshot(result, 51)['counts']['offline'] == 1
    assert snapshot(result, 60)['counts']['idle'] == 1
    online = run([vehicle(online=False, schedule=((20, True),))],
        [booking(pickup=(0., 0.))], wait=20,
        travels={'CAR': FixtureTravel(lambda p, t: 0 if tuple(p) == tuple(t) else 10)})
    assert online['assignments'][0]['pickupAtSeconds'] == 20
    assert online['assignments'][0]['pickupRouteRef'] is None


def test_spatial_expansion_uses_eta_and_budget_reason_is_not_no_route():
    class Search(FixtureTravel):
        async def table(self, positions, pickup):
            return [None if p[0] == 0 else 5 for p in positions]
    initial = [vehicle('A', position=(0., 0.)), vehicle('B', position=(.01, 0.))]
    full = run(initial, [booking(pickup=(.001, 0.))], {'CAR': Search()}, initialCandidates=1, maxCandidates=2)
    assert full['assignments'][0]['vehicleId'] == 'B'
    assert full['metrics']['tableCandidates'] == 2
    capped = run(initial, [booking(pickup=(.001, 0.))], {'CAR': Search()}, initialCandidates=1, maxCandidates=1)
    assert not capped['assignments']
    assert capped['events'][-1]['payload']['failureReason'] == 'SEARCH_BUDGET_EXHAUSTED'


def test_eta_choice_not_distance_and_full_route_deadline_confirmation():
    travel = FixtureTravel(lambda p, _: 20 if p[0] == 1 else 10)
    r = run([vehicle('A'), vehicle('B', position=(1., 0.))], travels={'CAR': travel})
    assert r['assignments'][0]['vehicleId'] == 'A'
    class Slow(FixtureTravel):
        async def route(self, a, b):
            return road(a, b, 200)
    assert run(travels={'CAR': Slow()}, wait=20)['counts']['unserved'] == 1


def test_table_disconnected_batch_expands_but_infrastructure_error_fails():
    class Disconnected(FixtureTravel):
        async def table(self, positions, target):
            if positions[0][0] == 0:
                raise HTTPException(422, {'code': 'NOTABLE'})
            return [5]*len(positions)
    r = run([vehicle('A'), vehicle('B', position=(.01, 0.))], [booking(pickup=(.001, 0.))],
        {'CAR': Disconnected()}, initialCandidates=1, maxCandidates=2)
    assert r['assignments'][0]['vehicleId'] == 'B'
    class Outage(FixtureTravel):
        async def table(self, *_):
            raise HTTPException(503, {'code': 'ROUTER_TIMEOUT'})
    with pytest.raises(HTTPException) as exc:
        run(travels={'CAR': Outage()})
    assert exc.value.detail['code'] == 'ROUTER_TIMEOUT'


def test_invalid_route_preserves_reason_and_no_cross_mode_fallback():
    class NoRoute(FixtureTravel):
        async def route(self, *_):
            raise HTTPException(422, {'code': 'NOROUTE'})
    result = run([vehicle(), vehicle('moto', 'MOTORBIKE')], [booking(), booking('B2', mode='MOTORBIKE')],
        {'CAR': FixtureTravel(), 'MOTORBIKE': NoRoute()})
    assert result['counts']['completed'] == 1
    assert next(e for e in result['events'] if e['type'] == 'BOOKING_UNSERVED')['payload']['failureReason'] == 'NOROUTE'


@pytest.mark.parametrize('bad', [{'fleetSize': 5001}, {'carCount': 101}, {'maxWaitSeconds': -1},
    {'onlineFraction': True}, {'fleetSize': True}, {'routerUrl': 'http://public'},
    {'onlineSchedule': [{'timeSeconds': 901, 'onlineFraction': .5}]},
    {'onlineSchedule': [{'timeSeconds': 1, 'onlineFraction': .5}, {'timeSeconds': 1, 'onlineFraction': .8}]}])
def test_strict_v3_inputs_do_not_relax_legacy_contracts(bad):
    with pytest.raises(ValidationError):
        SimulationConfig(**bad)


def test_5000_repeated_anchor_inputs_exact_mix_and_schedule_determinism():
    cfg = SimulationConfig(fleetSize=5000, carCount=2000, bookingCount=0, onlineFraction=.5,
        onlineSchedule=({'timeSeconds': 30, 'onlineFraction': .8},))
    first = generate_inputs(cfg, load_fixture()['anchors'][:2])
    assert first == generate_inputs(cfg, load_fixture()['anchors'][:2])
    vehicles, _ = first
    assert len(vehicles) == 5000 and sum(v.vehicleType == 'CAR' for v in vehicles) == 2000
    assert sum(v.online for v in vehicles) == 2500
    assert sum(v.schedule[0][1] for v in vehicles) == 4000


def test_recorded_runs_repeat_and_linear_audit_rejects_mutations():
    cfg = SimulationConfig(fleetSize=100, carCount=40, bookingCount=30)
    initial, demand = generate_inputs(cfg, load_fixture()['anchors'])
    def execute():
        return asyncio.run(simulate(cfg, initial, demand, {m: RecordedTravel(m) for m in ('CAR', 'MOTORBIKE')}, fixture_identities(), 'same'))
    result = execute()
    assert result == execute()
    broken = deepcopy(result)
    broken['counts']['completed'] += 1
    with pytest.raises(ValueError, match='conservation'):
        validate_result(broken)
    broken = deepcopy(result)
    broken['timelines'][broken['assignments'][0]['vehicleId']][0]['state'] = 'OFFLINE'
    with pytest.raises(ValueError, match='non-idle'):
        validate_result(broken)


def test_grid_indexes_only_idle_mode_and_bounded_query():
    grid = IdleGrid(.005)
    for i in range(100):
        grid.add(f'C{i:03}', 'CAR', (1., 1.))
    grid.add('M', 'MOTORBIKE', (1., 1.))
    assert grid.shortlist('CAR', (1., 1.), 2) == ['C000', 'C001']
    grid.remove('C000')
    assert grid.shortlist('CAR', (1., 1.), 2) == ['C001', 'C002']
    assert grid.shortlist('MOTORBIKE', (1., 1.), 20) == ['M']


def test_queue_bound_cancel_terminal_result_and_input_immutability(tmp_path):
    store = JobStore(tmp_path, capacity=1)
    status = store.create(SimulationConfig())
    immutable = (store.path(status['id'])/'input.json').read_bytes()
    with pytest.raises(HTTPException) as exc:
        store.create(SimulationConfig())
    assert exc.value.detail['code'] == 'JOB_QUEUE_FULL'
    store.claim()
    store.cancel(status['id'])
    assert store.finish(status['id'], result={'runId': status['id']})['status'] == 'CANCELLED'
    assert immutable == (store.path(status['id'])/'input.json').read_bytes()
    assert not (store.path(status['id'])/'result.json').exists()
    with pytest.raises(HTTPException) as exc:
        store.result(status['id'])
    assert exc.value.detail['code'] == 'RESULT_NOT_FINAL'
    assert store.create(SimulationConfig())['status'] == 'QUEUED'


def test_worker_failure_and_restart_interruption_never_publish_partial(tmp_path):
    store = JobStore(tmp_path)
    queued = store.create(SimulationConfig())
    running = store.claim()
    async def broken(*_):
        raise RuntimeError('fixture crash')
    assert asyncio.run(run_claimed(store, running, broken))['status'] == 'FAILED'
    assert not (store.path(queued['id'])/'result.json').exists()
    other = store.create(SimulationConfig())
    store.claim()
    with file_lock(tmp_path/'.worker.lock', blocking=False):
        store.interrupt_abandoned()
    assert store.read(other['id'])['status'] == 'INTERRUPTED'


def test_worker_cancel_after_compute_cannot_resurrect_result(tmp_path):
    store = JobStore(tmp_path)
    status = store.create(SimulationConfig())
    running = store.claim()
    async def late(config, id, cancelled, progress, prepared):
        await progress(.5)
        store.cancel(id)
        return {'runId': id}
    assert asyncio.run(run_claimed(store, running, late))['status'] == 'CANCELLED'
    assert not (store.path(status['id'])/'result.json').exists()


def test_job_api_projection_summary_routes_and_stale_result_isolation(tmp_path):
    store = JobStore(tmp_path)
    app = FastAPI()
    app.include_router(create_router(store))
    with TestClient(app) as client:
        response = client.post('/api/v3/simulation/jobs', json={'fleetSize': 1, 'carCount': 1, 'bookingCount': 1})
        assert response.status_code == 202
        id = response.json()['id']
        assert client.get(f'/api/v3/simulation/jobs/{id}/result').status_code == 409
        store.claim()
        result = run()
        result['runId'] = id
        for route in result['routes'].values():
            route['runId'] = id
        store.finish(id, result=result)
        summary = client.get(f'/api/v3/simulation/jobs/{id}/result?summary=true').json()
        assert summary['runId'] == id and 'routes' not in summary and 'events' not in summary
        snap = client.get(f'/api/v3/simulation/jobs/{id}/snapshot?timeSeconds=5').json()
        assert snap['runId'] == id and snap['counts']['moving'] == 1
        ref = snap['vehicles'][0]['routeRef']
        route = client.get(f'/api/v3/simulation/jobs/{id}/routes/{ref}').json()
        assert route['routingIdentity'] == snap['routingIdentities']['CAR']
        assert 'cumulativeMeters' not in route
        assert client.get(f'/api/v3/simulation/jobs/{id}/routes/missing').status_code == 404
        cancelled = client.post('/api/v3/simulation/jobs', json={}).json()['id']
        client.post(f'/api/v3/simulation/jobs/{cancelled}/cancel')
        assert client.get(f'/api/v3/simulation/jobs/{cancelled}/snapshot').status_code == 409
        assert client.get('/api/v3/simulation/jobs/invalid').status_code == 404


def test_worker_process_ownership_lock_is_cross_process_and_released(tmp_path):
    script = 'from backend.app.simulation_jobs import file_lock; import sys;\nwith file_lock(sys.argv[1],blocking=False): print("owned")'
    lock = str(tmp_path/'.worker.lock')
    with file_lock(lock, blocking=False):
        blocked = subprocess.run([sys.executable, '-c', script, lock], capture_output=True, text=True)
        assert blocked.returncode != 0
    acquired = subprocess.run([sys.executable, '-c', script, lock], capture_output=True, text=True)
    assert acquired.returncode == 0 and 'owned' in acquired.stdout


def test_worker_rejects_tampered_immutable_config(tmp_path):
    store = JobStore(tmp_path)
    status = store.create(SimulationConfig())
    path = store.path(status['id'])/'input.json'
    manifest = json.loads(path.read_text())
    manifest['config']['seed'] = 'tampered'
    atomic_json(path, manifest)
    assert asyncio.run(run_claimed(store, store.claim()))['status'] == 'FAILED'
    assert 'modified' in store.read(status['id'])['error']['message']
