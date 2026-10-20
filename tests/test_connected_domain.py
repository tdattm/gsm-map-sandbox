"""Artifact-free connected-world correctness; fixture travel is never runtime fallback."""
import asyncio
from copy import deepcopy
import json

from fastapi import HTTPException
from pydantic import ValidationError
import pytest

from backend.app.connected_simulation import (ConnectedScenarioConfig, DistributionConfig, ZONE_IDS,
    connected_inputs, connected_snapshot, integer_allocation, load_zones, simulate_connected,
    stratified_positions, validate_connected_result, zone_at)
from backend.app.schemas import RouteResponse
from backend.app.simulation import BookingInput, VehicleInput, meters
from scripts.m3_fixture_travel import fixture_identities


def fixture_anchors(zones=None, per_zone=100):
    zones = zones or load_zones()
    points = []
    for zone in zones:
        w, s, e, n = zone['bbox']
        for i in range(per_zone):
            # Explicit synthetic road-anchor fixture, not generated runtime roads.
            points.append((w+(e-w)*(.1+.8*(i % 50)/50), s+(n-s)*(.1+.8*(i//50)/max(1, per_zone//50))))
    return {'CAR': points, 'MOTORBIKE': points}


class ConnectedFixtureTravel:
    """Transparent domain-only evidence; time/distance are synthetic."""
    def __init__(self, mode='CAR', blocked=False):
        self.mode, self.blocked = mode, blocked
        self.counts = {'table': 0, 'route': 0, 'tableCandidates': 0}

    async def table(self, positions, pickup):
        self.counts['table'] += 1
        self.counts['tableCandidates'] += len(positions)
        return [None if self.blocked else (0. if tuple(p) == tuple(pickup) else 5.) for p in positions]

    async def route(self, start, end):
        self.counts['route'] += 1
        if self.blocked:
            raise HTTPException(422, {'code': 'NOROUTE'})
        return RouteResponse(coordinates=[start, end], distance=meters(start, end), duration=5.,
            duration_source=f'Synthetic {self.mode} connected domain fixture; NOT OSRM',
            snap_points=[{'location': start, 'distance': 0}, {'location': end, 'distance': 0}])


def run(config=None, **kwargs):
    config = config or ConnectedScenarioConfig(fleetSize=100, carCount=40, bookingCount=20,
        distribution={'nearestNeighborSampleSize': 8})
    zones = load_zones()
    vehicles, bookings, vmeta, bmeta = connected_inputs(config, fixture_anchors(), zones)
    identities = {mode: {**identity, 'regionId': 'nvmr-connected'} for mode, identity in fixture_identities().items()}
    return asyncio.run(simulate_connected(config, vehicles, bookings,
        {mode: ConnectedFixtureTravel(mode) for mode in identities}, identities, 'connected-fixture', zones, vmeta, bmeta, **kwargs))


def test_default_five_thousand_exact_zone_mode_allocation():
    config = ConnectedScenarioConfig()
    assert [a.carCount+a.motorbikeCount for a in config.fleetAllocations] == [4000, 250, 250, 250, 250]
    assert [a.carCount for a in config.fleetAllocations] == [1600, 100, 100, 100, 100]
    assert sum(a.motorbikeCount for a in config.fleetAllocations) == 3000


@pytest.mark.parametrize('total', [1, 17, 100, 500, 1000, 5000])
def test_integer_allocation_conserves_arbitrary_mode_totals(total):
    result = integer_allocation(total, dict(zip(ZONE_IDS, [16, 1, 1, 1, 1])))
    assert sum(result.values()) == total
    assert result == integer_allocation(total, dict(zip(ZONE_IDS, [16, 1, 1, 1, 1])))


def test_custom_allocations_and_invalid_bounds():
    allocations = [{'zoneId': z, 'carCount': i, 'motorbikeCount': 4-i} for i, z in enumerate(ZONE_IDS)]
    config = ConnectedScenarioConfig(fleetSize=20, carCount=10, fleetAllocations=allocations)
    assert sum(a.carCount+a.motorbikeCount for a in config.fleetAllocations) == 20
    for changes in ({'fleetSize': 5001}, {'carCount': 21, 'fleetSize': 20},
                    {'demandWeights': {'hanoi': 1}}, {'demandWeights': dict.fromkeys(ZONE_IDS, -1)},
                    {'fleetSize': 21, 'fleetAllocations': allocations},
                    {'fleetAllocations': allocations[:-1]+allocations[:1]}):
        with pytest.raises(ValidationError):
            ConnectedScenarioConfig(**changes)


def test_independent_demand_and_fleet_streams_and_stable_ids():
    zones, anchors = load_zones(), fixture_anchors()
    small = ConnectedScenarioConfig(fleetSize=100, carCount=40, bookingCount=20)
    custom = small.model_dump()
    custom.update(fleetSize=50, carCount=20, fleetAllocations=None)
    larger = ConnectedScenarioConfig.model_validate(custom)
    a = connected_inputs(small, anchors, zones)
    b = connected_inputs(larger, anchors, zones)
    assert a[1] == b[1]  # Potential demand does not depend on vehicle counts or locations.
    assert len({v.id for v in a[0]}) == 100
    assert len({v.position for v in a[0]}) == 100
    assert a == connected_inputs(small, anchors, zones)
    assert {zone: sum(meta['pickupZoneId'] == zone for meta in a[3].values()) for zone in ZONE_IDS} == dict.fromkeys(ZONE_IDS, 4)


def test_stratified_sampling_spreads_cells_and_refuses_missing_anchors():
    points = [(105.+i*.05, 21.+j*.05) for i in range(10) for j in range(10)]
    cfg = DistributionConfig(cellDegrees=.025)
    result = stratified_positions(points, 100, cfg, 'seed', 'fixture')
    assert len(set(result)) == 100
    with pytest.raises(ValueError, match='Insufficient'):
        stratified_positions(points, 101, cfg, 'seed', 'fixture')
    with pytest.raises(ValueError, match='Insufficient'):
        stratified_positions([], 1, cfg, 'seed', 'fixture')


def test_global_lifecycle_mode_isolation_kpis_reconcile_and_replay_without_router():
    result = run()
    assert result == run()
    assert validate_connected_result(result)
    kpis = result['kpis']
    for metric in ('sumSeconds', 'count'):
        assert sum(zone['pickupWait'][metric] for zone in kpis['byZone'].values()) == pytest.approx(kpis['global']['pickupWait'][metric])
    for metric in ('busyVehicleSeconds', 'onlineVehicleSeconds', 'fleetVehicleSeconds'):
        assert sum(zone['utilization'][metric] for zone in kpis['byZone'].values()) == pytest.approx(kpis['global']['utilization'][metric])
    for t in [0, 3, 50, 5000]:
        projected = connected_snapshot(json.loads(json.dumps(result)), t)
        assert len(projected['vehicles']) == 100
        assert sum(zone['total'] for zone in projected['zoneCounts'].values()) == 100
        assert sum(v['isMoving'] for v in projected['vehicles']) == projected['counts']['moving']
        assert projected['counts']['online']+projected['counts']['offline'] == 100
        assert all('homeZoneId' in v and 'currentZoneId' in v for v in projected['vehicles'])
    corrupted = deepcopy(result)
    corrupted['kpis']['global']['pickupWait']['count'] += 1
    with pytest.raises(ValueError, match='reconcile'):
        validate_connected_result(corrupted)


def test_cross_zone_dispatch_uses_one_pool_and_cross_zone_trip():
    zones = load_zones()
    hanoi, bac = zones[0]['probe'], zones[1]['probe']
    dropoff = [bac[0]+.001, bac[1]+.001]
    config = ConnectedScenarioConfig(fleetSize=1, carCount=1, bookingCount=1,
        demandCarFraction=1., maxWaitSeconds=10, onlineFraction=1.)
    vehicle = VehicleInput(id='global-car', vehicleType='CAR', position=hanoi)
    booking = BookingInput(id='cross', serviceType='CAR', requestTimeSeconds=0, pickup=bac, dropoff=dropoff)
    identities = {'CAR': {**fixture_identities()['CAR'], 'regionId': 'nvmr-connected'}}
    # Explicit custom input metadata and config allocation match the one Hanoi vehicle.
    result = asyncio.run(simulate_connected(config, [vehicle], [booking], {'CAR': ConnectedFixtureTravel()}, identities,
        'cross-fixture', zones, {'global-car': {'homeZoneId': 'hanoi'}},
        {'cross': {'pickupZoneId': 'bac-ninh', 'dropoffZoneId': 'bac-ninh'}}))
    assert result['counts']['completed'] == 1
    assert result['assignments'][0]['vehicleId'] == 'global-car'
    assert result['metrics']['crossZoneDispatches'] == 1
    assert connected_snapshot(result, 11)['vehicles'][0]['currentZoneId'] == 'bac-ninh'
    # Independent expected arithmetic: one 5s pickup, one5s trip, one online
    # vehicle for900s. Demand attribution differs from vehicle home attribution.
    assert result['kpis']['global']['pickupWait'] == {'sumSeconds': 5., 'count': 1, 'meanSeconds': 5., 'maximumSeconds': 5.}
    assert result['kpis']['global']['utilization']['busyVehicleSeconds'] == 10.
    assert result['kpis']['global']['utilization']['onlineVehicleSeconds'] == 900.
    assert result['kpis']['global']['utilization']['busyFractionOfOnline'] == 10/900
    assert result['kpis']['byZone']['hanoi']['utilization']['busyVehicleSeconds'] == 10.
    assert result['kpis']['byZone']['hanoi']['pickupWait']['count'] == 0
    assert result['kpis']['byZone']['bac-ninh']['pickupWait']['sumSeconds'] == 5.
    assert result['kpis']['byZone']['bac-ninh']['utilization']['busyVehicleSeconds'] == 0.
    assert result['bookings'][0]['snappedPickupZoneId'] == 'bac-ninh'
    assert result['bookings'][0]['snappedPickup'] == bac
    assert result['bookings'][0]['snapCrossedTechnicalZone'] is False


def test_cancellation_and_no_route_are_not_successful_travel():
    async def cancelled():
        return True
    with pytest.raises(HTTPException) as error:
        run(cancelled=cancelled)
    assert error.value.status_code == 499
    config = ConnectedScenarioConfig(fleetSize=100, carCount=40, bookingCount=20,
        distribution={'nearestNeighborSampleSize': 0})
    zones = load_zones()
    vehicles, demand, vmeta, bmeta = connected_inputs(config, fixture_anchors(), zones)
    identities = {mode: {**identity, 'regionId': 'nvmr-connected'} for mode, identity in fixture_identities().items()}
    result = asyncio.run(simulate_connected(config, vehicles, demand,
        {mode: ConnectedFixtureTravel(mode, blocked=True) for mode in identities}, identities,
        'blocked-fixture', zones, vmeta, bmeta))
    assert result['counts']['completed'] == 0
    assert result['counts']['unserved'] == 20
    assert not result['routes']
    assert all(event['payload']['failureReason'] == 'NOROUTE' for event in result['events'] if event['type'] == 'BOOKING_UNSERVED')


def test_technical_zones_nonoverlap_and_unknown_corridor_attribution():
    zones = load_zones()
    for zone in zones:
        assert zone_at(zone['probe'], zones) == zone['id']
        assert zone['boundaryKind'] == 'technical-operating-zone'
    assert zone_at([104.5, 20.5], zones) == 'outside-operating-zones'
