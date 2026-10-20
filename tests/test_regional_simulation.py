"""Artifact-free R1a regional domain, durable queue and API acceptance fixtures."""
import asyncio
from copy import deepcopy
import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend.app.regional_jobs import create_regional_router, regional_readiness
from backend.app.regional_simulation import (REGION_IDS, RegionalScenarioConfig,
    combine_regions, engine_config, region_seed, regional_inputs, regional_snapshot,
    regional_summary, simulate_regional)
from backend.app.schemas import RouteResponse
from backend.app.simulation import SimulationConfig, meters, validate_result
from backend.app.simulation_jobs import JobStore, atomic_json, create_router, file_lock
from backend.app.simulation_worker import run_claimed
from scripts.m3_fixture_travel import fixture_identities


def config(**overrides):
    raw = {'seed': 'regional-fixture/v1', 'horizonSeconds': 30, 'maxWaitSeconds': 300,
        'regions': [{'regionId': region, 'fleetSize': 4, 'carCount': 2,
            'bookingCount': 6, 'onlineFraction': 1.} for region in REGION_IDS]}
    return RegionalScenarioConfig.model_validate({**raw, **overrides})


class RegionalTravel:
    """Explicit synthetic fixture; never exposed as a runtime routing fallback."""
    def __init__(self, region, mode):
        self.region, self.mode = region, mode
        self.calls = []
        self.offset = 105. if region == REGION_IDS[0] else 106.

    def check(self, points):
        assert all(self.offset <= point[0] <= self.offset+.02 for point in points)

    async def route(self, start, end):
        self.check([start, end])
        self.calls.append(('route', self.region, self.mode))
        return RouteResponse(coordinates=[start, end], distance=meters(start, end),
            duration=20. if self.mode == 'CAR' else 10.,
            duration_source='Synthetic two-region fixture; not OSRM',
            snap_points=[{'location': start, 'distance': 0}, {'location': end, 'distance': 0}])

    async def table(self, positions, pickup):
        self.check([*positions, pickup])
        self.calls.append(('table', self.region, self.mode))
        return [0. if list(position) == list(pickup) else 5. for position in positions]


def prepared(cfg):
    output = {}
    for allocation in cfg.regions:
        region = allocation.regionId
        offset = 105. if region == REGION_IDS[0] else 106.
        vehicles, bookings = regional_inputs(cfg, allocation,
            [(offset, 21.), (offset+.01, 21.), (offset+.02, 21.01)])
        identities = {mode: {**identity, 'regionId': region}
                      for mode, identity in fixture_identities().items()}
        modes = {vehicle.vehicleType for vehicle in vehicles}
        output[region] = {'vehicles': vehicles, 'bookings': bookings,
            'travels': {mode: RegionalTravel(region, mode) for mode in modes},
            'identities': {mode: identities[mode] for mode in modes}}
    return output


def run(cfg=None, run_id='fixture-regional-run', **kwargs):
    cfg = cfg or config()
    return asyncio.run(simulate_regional(cfg, prepared(cfg), run_id, **kwargs))


def fixture_executor():
    async def execute(cfg, run_id, cancelled, progress, save):
        assert isinstance(cfg, RegionalScenarioConfig)
        save({'schemaVersion': 'fixture-regional-input/v1', 'runId': run_id})
        return await simulate_regional(cfg, prepared(cfg), run_id, cancelled, progress)
    return execute


def test_region_order_is_canonical_with_stable_subseeds_and_semantic_result():
    cfg = config()
    permuted = config(regions=list(reversed(cfg.model_dump()['regions'])))
    assert cfg == permuted
    assert region_seed(cfg.seed, REGION_IDS[0]) != region_seed(cfg.seed, REGION_IDS[1])
    assert cfg.model_dump() == permuted.model_dump()
    assert run(cfg) == run(permuted) == run(cfg)


def test_global_fleet_limit_and_explicit_mode_allocation():
    cfg = config(regions=[{'regionId': REGION_IDS[0], 'fleetSize': 2500, 'carCount': 1000},
                         {'regionId': REGION_IDS[1], 'fleetSize': 2500, 'carCount': 1000}])
    assert cfg.globalTotals == {'fleetSize': 5000, 'carCount': 2000, 'motorbikeCount': 3000, 'bookingCount': 20}
    assert all(allocation.motorbikeCount == 1500 for allocation in cfg.regions)
    raw = cfg.model_dump()
    raw['regions'][0]['fleetSize'] += 1
    raw['regions'][0]['motorbikeCount'] += 1
    with pytest.raises(ValidationError, match='totals'):
        RegionalScenarioConfig.model_validate(raw)


@pytest.mark.parametrize('change', [
    {'regions': []}, {'schemaVersion': 'gsm-simulation-result/v1'},
    {'initialCandidates': 100, 'maxCandidates': 2},
    {'regions': [{'regionId': REGION_IDS[0], 'fleetSize': 2, 'carCount': 1}]*2},
    {'regions': [{'regionId': 'unknown', 'fleetSize': 2, 'carCount': 1},
                 {'regionId': REGION_IDS[1], 'fleetSize': 2, 'carCount': 1}]},
    {'regions': [{'regionId': region, 'fleetSize': 2, 'carCount': 1, 'motorbikeCount': 2} for region in REGION_IDS]},
    {'regions': [{'regionId': region, 'fleetSize': True, 'carCount': 1} for region in REGION_IDS]},
    {'regions': [{'regionId': region, 'fleetSize': 2, 'carCount': 1, 'onlineFraction': True} for region in REGION_IDS]},
    {'regions': [{'regionId': region, 'fleetSize': 2, 'carCount': 1,
                 'onlineSchedule': [{'timeSeconds': 31, 'onlineFraction': .5}]} for region in REGION_IDS]},
    {'regions': [{'regionId': region, 'fleetSize': 2, 'carCount': 1, 'bookingCount': 11000} for region in REGION_IDS]},
    {'globalTotals': {'fleetSize': 8}}, {'routerUrl': 'https://public-router.invalid'},
])
def test_invalid_contracts_fail_before_execution(change):
    with pytest.raises(ValidationError):
        config(**change)


def test_historical_public_v3_remains_hanoi_only():
    with pytest.raises(ValidationError):
        SimulationConfig(regionId='nvmr-bac-ninh-core')
    cfg = config()
    adapted = engine_config(cfg, next(r for r in cfg.regions if r.regionId == REGION_IDS[1]))
    assert adapted.regionId == REGION_IDS[1]
    assert SimulationConfig().regionId == REGION_IDS[0]


def test_two_region_dispatch_mode_and_graph_isolation_unique_ids():
    cfg = config()
    inputs = prepared(cfg)
    result = asyncio.run(simulate_regional(cfg, inputs, 'same-run'))
    vehicles = [vehicle for region in result['regions'] for vehicle in region['vehicles']]
    bookings = [booking for region in result['regions'] for booking in region['bookings']]
    assert len({v['id'] for v in vehicles}) == cfg.fleetSize
    assert len({b['id'] for b in bookings}) == cfg.bookingCount
    assert result['counts']['completed'] == cfg.bookingCount
    assert result['counts']['requested'] == result['counts']['completed']+result['counts']['unserved']
    for region in result['regions']:
        assert validate_result(region)
        for assignment in region['assignments']:
            assert assignment['bookingId'].startswith(region['regionId']+':')
            assert assignment['vehicleId'].startswith(region['regionId']+':')
            route = region['routes'][assignment['tripRouteRef']]
            assert route['regionId'] == route['routingIdentity']['regionId'] == region['regionId']
            assert route['routingIdentity']['vehicleType'] == assignment['vehicleType']
        assert all(call[1] == region['regionId'] and call[2] == mode
            for mode, travel in inputs[region['regionId']]['travels'].items() for call in travel.calls)


def test_shared_clock_snapshot_fleet_conservation_and_no_geometry_duplication():
    result = run()
    times = [0, 5, 15, 30, 100, result['simulationDurationSeconds'], 100000]
    for time in times:
        projected = regional_snapshot(result, time)
        assert all(region['simulationTimeSeconds'] == projected['simulationTimeSeconds'] for region in projected['regions'])
        counts = projected['counts']
        assert counts['total'] == counts['offline']+counts['online'] == 8
        assert counts['online'] == counts['idle']+counts['assigned']+counts['onTrip']
        assert counts['moving'] <= counts['assigned']+counts['onTrip']
        for key in counts:
            assert counts[key] == sum(region['counts'][key] for region in projected['regions'])
        assert all('regionId' in vehicle and 'coordinates' not in vehicle for vehicle in projected['vehicles'])
    assert len({region['simulationDurationSeconds'] for region in result['regions']}) == 1
    with pytest.raises(ValueError):
        regional_snapshot(result, float('nan'))


def test_weighted_wait_and_utilization_use_combined_numerators_denominators():
    cfg = config(regions=[{'regionId': REGION_IDS[0], 'fleetSize': 1, 'carCount': 1,
                          'bookingCount': 1, 'onlineFraction': 1.},
                         {'regionId': REGION_IDS[1], 'fleetSize': 5, 'carCount': 0,
                          'bookingCount': 9, 'onlineFraction': .6}])
    result = run(cfg)
    assignments = [assignment for region in result['regions'] for assignment in region['assignments']]
    requests = {booking['id']: booking['requestTimeSeconds'] for region in result['regions'] for booking in region['bookings']}
    wait = sum(assignment['pickupAtSeconds']-requests[assignment['bookingId']] for assignment in assignments)
    assert result['kpis']['pickupWait']['meanSeconds'] == pytest.approx(wait/len(assignments))
    utilization = result['kpis']['utilization']
    assert utilization['busyFractionOfOnline'] == pytest.approx(utilization['busyVehicleSeconds']/utilization['onlineVehicleSeconds'])
    assert utilization['fleetVehicleSeconds'] == cfg.fleetSize*result['simulationDurationSeconds']
    assert utilization['busyVehicleSeconds'] == sum(region['kpis']['utilization']['busyVehicleSeconds'] for region in result['regions'])
    for key in ('requested', 'assigned', 'completed', 'unserved'):
        assert result['counts'][key] == sum(result['kpis']['byMode'][mode]['counts'][key] for mode in ('CAR', 'MOTORBIKE'))
    assert result['kpis']['byMode']['CAR']['fleetSize'] == 1
    assert result['kpis']['byMode']['MOTORBIKE']['fleetSize'] == 5
    empty_mode = next(region for region in result['regions'] if region['regionId'] == REGION_IDS[0])['kpis']['byMode']['MOTORBIKE']
    assert empty_mode['utilization']['busyFractionOfFleet'] is None


def test_common_clock_holds_short_region_schedule_and_defers_busy_offline():
    cfg = config(horizonSeconds=10, regions=[
        {'regionId': REGION_IDS[0], 'fleetSize': 1, 'carCount': 1, 'bookingCount': 1,
         'onlineFraction': 1., 'onlineSchedule': [{'timeSeconds': 10, 'onlineFraction': 0.}]},
        {'regionId': REGION_IDS[1], 'fleetSize': 1, 'carCount': 1, 'bookingCount': 0,
         'onlineFraction': 0., 'onlineSchedule': [{'timeSeconds': 8, 'onlineFraction': 1.}]}])
    inputs = prepared(cfg)
    hanoi = inputs[REGION_IDS[0]]
    booking = hanoi['bookings'][0].model_copy(update={'requestTimeSeconds': 9.})
    hanoi['bookings'] = [booking]
    hanoi['vehicles'] = [hanoi['vehicles'][0].model_copy(update={'position': booking.pickup})]
    result = asyncio.run(simulate_regional(cfg, inputs, 'clock-fixture'))
    assert result['simulationDurationSeconds'] == 29
    short = next(region for region in result['regions'] if region['regionId'] == REGION_IDS[1])
    assert short['kpis']['utilization']['onlineVehicleSeconds'] == 21
    assert result['kpis']['utilization']['busyVehicleSeconds'] == 20
    assert result['kpis']['utilization']['onlineVehicleSeconds'] == 50
    assert regional_snapshot(result, 15)['counts'] == {
        'total': 2, 'offline': 0, 'online': 2, 'idle': 1, 'assigned': 0, 'onTrip': 1, 'moving': 1}
    assert regional_snapshot(result, 29)['counts']['offline'] == 1
    for region in result['regions']:
        merged = [event for event in result['events'] if event['regionId'] == region['regionId']]
        assert [event['id'] for event in merged] == [region['regionId']+':'+event['id'] for event in region['events']]
    from scripts.validate_regional_api import audit_aggregates
    audit_aggregates(result)


@pytest.mark.parametrize('target', ['scenarioMean', 'modeUtilization', 'regionalWait', 'globalTotals', 'regionRun', 'regionConfig'])
def test_independent_acceptance_audit_rejects_aggregate_tampering(target):
    from scripts.validate_regional_api import audit_aggregates
    result = run()
    audit_aggregates(result)
    if target == 'scenarioMean':
        result['kpis']['pickupWait']['meanSeconds'] += 1
    elif target == 'modeUtilization':
        result['kpis']['byMode']['CAR']['utilization']['onlineVehicleSeconds'] += 1
    elif target == 'regionalWait':
        result['regions'][0]['kpis']['pickupWait']['sumSeconds'] += 1
    elif target == 'globalTotals':
        result['globalTotals']['carCount'] += 1
    elif target == 'regionRun':
        result['regions'][0]['runId'] = 'foreign-run'
    else:
        result['regions'][0]['config']['seed'] = 'changed-seed'
    with pytest.raises(ValueError, match='independent|immutable scenario'):
        audit_aggregates(result)


def test_no_route_is_explicit_unserved_in_correct_mode_without_fallback():
    cfg = config()
    inputs = prepared(cfg)
    class NoRoute(RegionalTravel):
        async def route(self, *_):
            raise HTTPException(422, {'code': 'NOROUTE'})
    inputs[REGION_IDS[1]]['travels']['MOTORBIKE'] = NoRoute(REGION_IDS[1], 'MOTORBIKE')
    result = asyncio.run(simulate_regional(cfg, inputs, 'same-run'))
    region = next(region for region in result['regions'] if region['regionId'] == REGION_IDS[1])
    moto = {booking['id'] for booking in region['bookings'] if booking['serviceType'] == 'MOTORBIKE'}
    assert moto
    assert not any(assignment['bookingId'] in moto for assignment in region['assignments'])
    assert {event['payload']['failureReason'] for event in region['events']
        if event['type'] == 'BOOKING_UNSERVED' and event['bookingId'] in moto} == {'NOROUTE'}


def test_combination_rejects_partial_or_misidentified_results():
    result = run()
    with pytest.raises(ValueError, match='Both'):
        combine_regions(config(), result['regions'][:1], result['runId'])
    broken = deepcopy(result['regions'])
    broken[0]['runId'] = 'other'
    with pytest.raises(ValueError):
        combine_regions(config(), broken, result['runId'])
    broken = deepcopy(result['regions'])
    broken[0]['routingIdentities']['CAR']['regionId'] = REGION_IDS[0]
    with pytest.raises(ValueError):
        combine_regions(config(), broken, result['runId'])


def test_scenario_cancellation_between_regions_and_progress_never_completes():
    cfg = config()
    values = []
    async def progress(value):
        values.append(value)
    async def cancelled():
        return bool(values and values[-1] >= .49)
    with pytest.raises(HTTPException) as exc:
        run(cfg, cancelled=cancelled, progress=progress)
    assert exc.value.status_code == 499
    assert max(values) < 1


def test_shared_store_worker_persistence_reopen_and_explicit_retry(tmp_path):
    store = JobStore(tmp_path)
    queued = store.create(config())
    status = asyncio.run(run_claimed(store, store.claim(), fixture_executor()))
    assert status['status'] == 'COMPLETED'
    reopened = JobStore(tmp_path).result(queued['id'])
    assert reopened['schemaVersion'] == 'gsm-nvmr-regional-result/v1'
    assert all(region['runId'] == queued['id'] for region in reopened['regions'])
    assert json.loads((store.path(queued['id'])/'prepared-input.json').read_text())['runId'] == queued['id']
    retry = store.create(config())
    assert retry['id'] != queued['id']
    assert retry['inputHash'] == queued['inputHash']
    assert store.result(queued['id']) == reopened


def test_infrastructure_failure_in_second_region_cannot_publish_partial(tmp_path):
    store = JobStore(tmp_path)
    queued = store.create(config())
    async def failing(cfg, run_id, cancelled, progress, save):
        inputs = prepared(cfg)
        class Outage(RegionalTravel):
            async def route(self, *_):
                raise HTTPException(503, {'code': 'ROUTER_TIMEOUT', 'regionId': REGION_IDS[0]})
        # Sorted Bac Ninh executes first, then Hanoi fails.
        inputs[REGION_IDS[0]]['travels']['CAR'] = Outage(REGION_IDS[0], 'CAR')
        return await simulate_regional(cfg, inputs, run_id, cancelled, progress)
    status = asyncio.run(run_claimed(store, store.claim(), failing))
    assert status['status'] == 'FAILED' and status['error']['code'] == 'ROUTER_TIMEOUT'
    assert not (store.path(queued['id'])/'result.json').exists()
    with pytest.raises(HTTPException, match='409'):
        store.result(queued['id'])


def test_cancel_queued_running_late_completion_and_interruption(tmp_path):
    store = JobStore(tmp_path)
    queued = store.create(config())
    assert store.cancel(queued['id'])['status'] == 'CANCELLED'
    assert store.claim() is None
    running = store.create(config())
    claimed = store.claim()
    async def late(cfg, run_id, cancelled, progress, save):
        computed = await fixture_executor()(cfg, run_id, cancelled, progress, save)
        store.cancel(run_id)
        return computed
    assert asyncio.run(run_claimed(store, claimed, late))['status'] == 'CANCELLED'
    assert not (store.path(running['id'])/'result.json').exists()
    interrupted = store.create(config())
    store.claim()
    with file_lock(tmp_path/'.worker.lock', blocking=False):
        store.interrupt_abandoned()
    assert store.read(interrupted['id'])['status'] == 'INTERRUPTED'
    retry = store.create(config())
    assert asyncio.run(run_claimed(store, store.claim(), fixture_executor()))['status'] == 'COMPLETED'
    assert store.read(interrupted['id'])['status'] == 'INTERRUPTED'
    assert retry['id'] != interrupted['id']


def test_worker_rejects_regional_manifest_tampering(tmp_path):
    store = JobStore(tmp_path)
    queued = store.create(config())
    path = store.path(queued['id'])/'input.json'
    manifest = json.loads(path.read_text())
    manifest['config']['regions'][0]['bookingCount'] += 1
    atomic_json(path, manifest)
    outcome = asyncio.run(run_claimed(store, store.claim(), fixture_executor()))
    assert outcome['status'] == 'FAILED' and 'modified' in outcome['error']['message']


def test_shared_queue_bound_applies_across_v3_and_v4(tmp_path):
    store = JobStore(tmp_path, capacity=1)
    v3 = store.create(SimulationConfig())
    with pytest.raises(HTTPException) as exc:
        store.create(config())
    assert exc.value.status_code == 429
    store.cancel(v3['id'])
    assert store.create(config())['status'] == 'QUEUED'


def api(store, readiness=None):
    async def fixture_readiness(*_):
        return {}, {}
    app = FastAPI()
    app.include_router(create_router(store))
    app.include_router(create_regional_router(store, readiness=readiness or fixture_readiness))
    return TestClient(app)


def test_api_create_list_summary_snapshot_details_and_namespace_isolation(tmp_path):
    store = JobStore(tmp_path)
    base = '/api/v4/simulation/jobs'
    with api(store) as client:
        created = client.post(base, json=config().model_dump(mode='json'))
        assert created.status_code == 202
        id = created.json()['id']
        assert client.get(base).json()['jobs'][0]['id'] == id
        assert client.get(f'{base}/{id}/result').status_code == 409
        assert client.get(f'/api/v3/simulation/jobs/{id}').status_code == 404
        assert client.post(f'/api/v3/simulation/jobs/{id}/cancel').status_code == 404
        assert asyncio.run(run_claimed(store, store.claim(), fixture_executor()))['status'] == 'COMPLETED'
        raw = store.result(id)
        summary = client.get(f'{base}/{id}/result?summary=true').json()
        assert summary == regional_summary(raw)
        assert summary['globalTotals']['fleetSize'] == 8
        assert 'events' not in summary and all('routes' not in region for region in summary['regions'])
        projection = client.get(f'{base}/{id}/snapshot?timeSeconds=5').json()
        assert projection['counts']['total'] == 8
        assert client.get(f'{base}/{id}/snapshot?timeSeconds=nan').status_code == 422
        for region in raw['regions']:
            assignment = region['assignments'][0]
            booking = client.get(f'{base}/{id}/bookings/{assignment["bookingId"]}').json()
            assert booking['regionId'] == region['regionId']
            route = client.get(f'{base}/{id}/routes/{assignment["tripRouteRef"]}').json()
            assert route['runId'] == id and route['regionId'] == booking['regionId']
            assert 'cumulativeMeters' not in route
            vehicle = client.get(f'{base}/{id}/vehicles/{assignment["vehicleId"]}?timeSeconds={assignment["pickupAtSeconds"]}').json()
            assert vehicle['regionId'] == region['regionId']
            assert vehicle['booking']['bookingId'] == assignment['bookingId']
        assert client.get(f'{base}/{id}/routes/foreign-route').status_code == 404
        assert client.get(f'{base}/{id}/vehicles/foreign-vehicle').status_code == 404
        assert client.get(f'{base}/{id}/bookings/foreign-booking').status_code == 404
        assert client.get(f'/api/v3/simulation/jobs/{id}/result').status_code == 404
        legacy = store.create(SimulationConfig())
        assert client.get(f'{base}/{legacy["id"]}').status_code == 404
        assert client.post(f'{base}/{legacy["id"]}/cancel').status_code == 404
        assert len(client.get(base).json()['jobs']) == 1


def test_api_preflight_refuses_all_partial_readiness_without_creating_job(tmp_path):
    store = JobStore(tmp_path)
    async def not_ready(*_):
        raise HTTPException(503, {'code': 'REGIONAL_NOT_READY', 'regions': [
            {'regionId': REGION_IDS[1], 'vehicleType': 'MOTORBIKE', 'code': 'MODE_NOT_READY'}]})
    with api(store, not_ready) as client:
        response = client.post('/api/v4/simulation/jobs', json=config().model_dump(mode='json'))
        assert response.status_code == 503
        assert response.json()['detail']['regions'][0]['regionId'] == REGION_IDS[1]
        assert store.statuses() == []


def test_readiness_checks_every_requested_region_mode_and_scopes_error(monkeypatch):
    import backend.app.regional_jobs as module
    calls = []
    def resolve(registry, region_id, mode):
        calls.append((region_id, mode))
        return {'regionId': region_id, 'mode': mode}
    async def readiness(context):
        return {'ready': context['regionId'] == REGION_IDS[0], 'readinessReason': 'fixture not prepared'}
    def identity(context):
        return {'regionId': context['regionId'], 'vehicleType': context['mode']}
    monkeypatch.setattr(module, 'resolve_mode', resolve)
    monkeypatch.setattr(module, 'public_region_status', readiness)
    monkeypatch.setattr(module, 'routing_identity', identity)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(regional_readiness(config(), registry=object()))
    assert len(calls) == 4
    assert exc.value.detail['code'] == 'REGIONAL_NOT_READY'
    assert {failure['vehicleType'] for failure in exc.value.detail['regions']} == {'CAR', 'MOTORBIKE'}
    assert all(failure['regionId'] == REGION_IDS[1] for failure in exc.value.detail['regions'])
    assert f'{REGION_IDS[1]}/MOTORBIKE' in exc.value.detail['message']


def test_global_resource_admission_uses_combined_workload_and_unchanged_floor():
    from backend.app.simulation_resources import GIB, resource_decision
    cfg = config(regions=[{'regionId': region, 'fleetSize': 600, 'carCount': 300, 'bookingCount': 600}
                          for region in REGION_IDS])
    current = {'availablePhysicalBytes': int(.7*GIB), 'systemCommitAvailableBytes': 3*GIB}
    assert all(resource_decision(engine_config(cfg, allocation), current)['allowed'] for allocation in cfg.regions)
    global_decision = resource_decision(cfg, current)
    assert not global_decision['allowed']
    assert global_decision['workloadClass'] == 'routine'
    assert global_decision['minimumAvailableGiB'] == .75


def test_readiness_hashing_does_not_block_event_loop(monkeypatch):
    import time
    import backend.app.regional_jobs as module
    monkeypatch.setattr(module, 'resolve_mode', lambda registry, region, mode: (region, mode))
    async def ready(_):
        return {'ready': True}
    def identity(context):
        time.sleep(.03)
        return {'regionId': context[0], 'vehicleType': context[1]}
    monkeypatch.setattr(module, 'public_region_status', ready)
    monkeypatch.setattr(module, 'routing_identity', identity)
    async def execute():
        ticks = 0
        task = asyncio.create_task(regional_readiness(config(), registry=object()))
        while not task.done():
            ticks += 1
            await asyncio.sleep(.005)
        await task
        return ticks
    assert asyncio.run(execute()) >= 10


@pytest.mark.parametrize('explicit', [None, '1;150'])
def test_local_travel_default_radius_unchanged_and_explicit_radius_preserved(explicit):
    from types import SimpleNamespace
    import httpx
    from backend.app.booking import LocalTravel
    settings = SimpleNamespace(osrm_base_url='http://local-fixture', max_snap_meters=150)
    seen = []
    def handler(request):
        seen.append(request.url.params['radiuses'])
        return httpx.Response(200, json={'code': 'Ok'})
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            travel = LocalTravel(settings, None, meters, client)
            await travel.service('table', [(106., 21.), (106.01, 21.)],
                                 {} if explicit is None else {'radiuses': explicit})
    asyncio.run(execute())
    assert seen == [explicit if explicit is not None else '150;150']


@pytest.mark.parametrize('violate_radius', [False, True])
def test_regional_table_pins_vehicle_sources_and_preserves_null_and_continuity(violate_radius):
    from types import SimpleNamespace
    import httpx
    from backend.app.simulation_worker import InstrumentedTravel, RegionalInstrumentedTravel
    settings = SimpleNamespace(osrm_base_url='http://local-fixture', max_snap_meters=150,
        operating_bbox=(106., 21., 106.1, 21.3), region=SimpleNamespace(display_bbox=(106., 21., 106.1, 21.3)))
    positions = [(106.068406, 21.184321), (106.050403, 21.194829)]
    pickup = (106.051936, 21.177334)
    original = deepcopy(positions)
    seen = []
    def handler(request):
        radii = request.url.params['radiuses']
        seen.append(radii)
        pinned = radii == '1;1;150'
        shift = not pinned or violate_radius
        first = (106.067787, 21.184043) if shift else positions[0]
        return httpx.Response(200, json={'code': 'Ok', 'durations': [[None if pinned else 386.], [154.2]],
            'sources': [{'location': first, 'distance': meters(first, positions[0])},
                        {'location': positions[1], 'distance': 0}],
            'destinations': [{'location': pickup, 'distance': 0}]})
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # Legacy adapter retains the default query and the one-meter guard.
            with pytest.raises(HTTPException) as legacy:
                await InstrumentedTravel(settings, client).table(positions, pickup)
            assert legacy.value.status_code == 502
            travel = RegionalInstrumentedTravel(settings, client)
            if violate_radius:
                with pytest.raises(HTTPException) as refused:
                    await travel.table(positions, pickup)
                assert refused.value.status_code == 502
            else:
                assert await travel.table(positions, pickup) == [None, 154.2]
                assert await travel.table(positions, pickup) == [None, 154.2]
                assert travel.telemetry()['requests']['tableCacheHits'] == 1
    asyncio.run(execute())
    assert seen == ['150;150;150', '1;1;150']
    assert positions == original


@pytest.mark.parametrize('changed', [False, True])
def test_live_executor_adapter_is_sequential_and_rechecks_all_graphs(monkeypatch, changed):
    import backend.app.regional_jobs as module
    import backend.app.simulation_worker as worker
    cfg = config()
    inputs = prepared(cfg)
    contexts = {region: {mode: {'regionId': region, 'mode': mode} for mode in values['travels']}
                for region, values in inputs.items()}
    identities = {region: values['identities'] for region, values in inputs.items()}
    async def ready(*args, **kwargs):
        return contexts, deepcopy(identities)
    def identity(context):
        value = deepcopy(identities[context['regionId']][context['mode']])
        if changed:
            value['graphManifestSha256'] = 'changed'
        return value
    def catalog(context):
        offset = 105. if context['regionId'] == REGION_IDS[0] else 106.
        return {'candidates': [{'coordinate': [offset, 21.]}, {'coordinate': [offset+.01, 21.]},
                {'coordinate': [offset+.02, 21.01]}], 'datasetFingerprint': 'fixture', 'provenance': {'fixture': True}}
    construction_order = []
    class Travel(RegionalTravel):
        def __init__(self, context, client):
            super().__init__(context['regionId'], context['mode'])
            construction_order.append(context['regionId'])
        async def nearest(self, point):
            self.check([point])
            return point
        def telemetry(self):
            return {'fixtureRequests': len(self.calls)}
    monkeypatch.setattr(module, 'regional_readiness', ready)
    monkeypatch.setattr(module, 'routing_identity', identity)
    monkeypatch.setattr(module, 'candidate_catalog', catalog)
    monkeypatch.setattr(worker, 'RegionalInstrumentedTravel', Travel)
    saved = []
    if changed:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(module.execute_regional_live(cfg, 'fixture', prepared=saved.append))
        assert exc.value.detail['code'] == 'ROUTING_IDENTITY_CHANGED'
        assert not saved[-1]['complete']
    else:
        result = asyncio.run(module.execute_regional_live(cfg, 'fixture', prepared=saved.append))
        assert result['counts']['completed'] == cfg.bookingCount
        assert saved[-1]['complete']
        assert result['metrics']['preparationMilliseconds'] >= 0
        assert construction_order == sorted(construction_order)
