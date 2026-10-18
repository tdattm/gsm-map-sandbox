"""R1a regional envelope over the unchanged v3 intra-region scientific engine.

Regions execute sequentially for bounded router/cache memory. Their simulation
clocks all start at zero; execution wall time never offsets simulated time.
"""
import hashlib
import math
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .simulation import (SimulationConfig, OnlineSchedulePoint, generate_inputs,
                         simulate, snapshot, validate_result)

REGION_IDS = ('nvmr-hanoi-core', 'nvmr-bac-ninh-core')
SCHEMA = 'gsm-nvmr-regional-scenario/v1'
RESULT_SCHEMA = 'gsm-nvmr-regional-result/v1'


class RegionalAllocation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    regionId: Literal['nvmr-hanoi-core', 'nvmr-bac-ninh-core']
    fleetSize: int = Field(ge=1, le=5000, strict=True)
    carCount: int = Field(ge=0, le=5000, strict=True)
    motorbikeCount: int | None = Field(default=None, ge=0, le=5000, strict=True)
    bookingCount: int = Field(default=10, ge=0, le=20000, strict=True)
    onlineFraction: float = Field(default=.8, ge=0, le=1, strict=True, allow_inf_nan=False)
    onlineSchedule: tuple[OnlineSchedulePoint, ...] = ()

    @model_validator(mode='after')
    def allocation(self):
        expected = self.fleetSize-self.carCount
        if expected < 0 or self.motorbikeCount not in (None, expected):
            raise ValueError('Regional CAR + MOTORBIKE must equal regional fleet size')
        object.__setattr__(self, 'motorbikeCount', expected)
        return self


class RegionalScenarioConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    schemaVersion: Literal['gsm-nvmr-regional-scenario/v1'] = SCHEMA
    seed: str = Field(default='nvmr-r1a-synthetic', min_length=1, max_length=80)
    horizonSeconds: int = Field(default=900, ge=1, le=86400, strict=True)
    maxWaitSeconds: int = Field(default=300, ge=0, le=3600, strict=True)
    workload: Literal['low', 'typical', 'burst'] = 'typical'
    initialCandidates: int = Field(default=16, ge=1, le=128, strict=True)
    maxCandidates: int = Field(default=128, ge=1, le=512, strict=True)
    gridCellDegrees: float = Field(default=.005, gt=0, le=.1, allow_inf_nan=False)
    regions: tuple[RegionalAllocation, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode='after')
    def regional_bounds(self):
        if sorted(r.regionId for r in self.regions) != sorted(REGION_IDS):
            raise ValueError('R1a requires exactly Hanoi Core and Bac Ninh Core pilot')
        if self.fleetSize > 5000 or self.bookingCount > 20000:
            raise ValueError('Scenario totals exceed 5000 vehicles or 20000 bookings')
        object.__setattr__(self, 'regions', tuple(sorted(self.regions, key=lambda r: r.regionId)))
        for allocation in self.regions:
            engine_config(self, allocation)  # Same strict schedule/shortlist bounds as v3.
        return self

    @property
    def fleetSize(self):
        return sum(r.fleetSize for r in self.regions)

    @property
    def bookingCount(self):
        return sum(r.bookingCount for r in self.regions)

    @property
    def onlineSchedule(self):
        # Admission uses the maximum number of transitions one vehicle may have,
        # not the sum across regions executed sequentially.
        return max((r.onlineSchedule for r in self.regions), key=len, default=())

    @property
    def globalTotals(self):
        return {'fleetSize': self.fleetSize, 'carCount': sum(r.carCount for r in self.regions),
                'motorbikeCount': sum(r.motorbikeCount for r in self.regions),
                'bookingCount': self.bookingCount}


class _RegionalEngineConfig(SimulationConfig):
    """Internal validated adapter; public SimulationConfig remains Hanoi-only."""
    regionId: Literal['nvmr-hanoi-core', 'nvmr-bac-ninh-core']


def region_seed(master_seed, region_id):
    return hashlib.sha256(f'nvmr-regional-seed/v1:{master_seed}:{region_id}'.encode()).hexdigest()


def engine_config(config, allocation):
    return _RegionalEngineConfig(regionId=allocation.regionId,
        seed=region_seed(config.seed, allocation.regionId), fleetSize=allocation.fleetSize,
        carCount=allocation.carCount, bookingCount=allocation.bookingCount,
        onlineFraction=allocation.onlineFraction, onlineSchedule=allocation.onlineSchedule,
        **{key: getattr(config, key) for key in ('horizonSeconds', 'maxWaitSeconds', 'workload',
            'initialCandidates', 'maxCandidates', 'gridCellDegrees')})


def regional_inputs(config, allocation, anchors):
    vehicles, bookings = generate_inputs(engine_config(config, allocation), anchors)
    prefix = allocation.regionId+':'
    return ([v.model_copy(update={'id': prefix+v.id}) for v in vehicles],
            [b.model_copy(update={'id': prefix+b.id}) for b in bookings])


def active_modes(allocation):
    return (["CAR"] if allocation.carCount else []) + (["MOTORBIKE"] if allocation.motorbikeCount else [])


def regional_kpis(region, duration):
    request_times = {b['id']: b['requestTimeSeconds'] for b in region['bookings']}
    waits = [a['pickupAtSeconds']-request_times[a['bookingId']] for a in region['assignments']]
    busy, online = 0., 0.
    for timeline in region['timelines'].values():
        for i, state in enumerate(timeline):
            end = timeline[i+1]['time'] if i+1 < len(timeline) else duration
            elapsed = max(0., min(duration, end)-state['time'])
            if state['state'] != 'OFFLINE':
                online += elapsed
            if state['state'] in ('ASSIGNED', 'ON_TRIP'):
                busy += elapsed
    return {'pickupWait': {'sumSeconds': sum(waits), 'count': len(waits),
            'meanSeconds': sum(waits)/len(waits) if waits else None,
            'maximumSeconds': max(waits) if waits else None},
        'utilization': {'busyVehicleSeconds': busy, 'onlineVehicleSeconds': online,
            'fleetVehicleSeconds': len(region['vehicles'])*duration,
            'busyFractionOfOnline': busy/online if online else None,
            'busyFractionOfFleet': busy/(len(region['vehicles'])*duration) if region['vehicles'] and duration else None}}


def combine_regions(config, results, run_id):
    if sorted(r['regionId'] for r in results) != sorted(REGION_IDS):
        raise ValueError('Both complete regions are required before publication')
    results = sorted(results, key=lambda r: r['regionId'])
    duration = max(r['simulationDurationSeconds'] for r in results)
    ids, booking_ids, route_refs = set(), set(), set()
    allocations = {allocation.regionId: allocation for allocation in config.regions}
    for region in results:
        validate_result(region)
        if region['runId'] != run_id:
            raise ValueError('Regional run identity mismatch')
        if _RegionalEngineConfig.model_validate(region['config']) != engine_config(config, allocations[region['regionId']]):
            raise ValueError('Regional result configuration differs from scenario allocation')
        prefix = region['regionId']+':'
        for key, seen in (('vehicles', ids), ('bookings', booking_ids)):
            for item in region[key]:
                if not item['id'].startswith(prefix) or item['id'] in seen:
                    raise ValueError('Cross-region or duplicate global identity')
                seen.add(item['id'])
        if route_refs.intersection(region['routes']):
            raise ValueError('Route reference collision across regions')
        route_refs.update(region['routes'])
        if any(identity['regionId'] != region['regionId'] or identity['vehicleType'] != mode
               for mode, identity in region['routingIdentities'].items()):
            raise ValueError('Cross-region routing identity')
        for ref, route in region['routes'].items():
            mode = route['routingIdentity']['vehicleType']
            if (route['runId'] != run_id or route['regionId'] != region['regionId'] or route['routeRef'] != ref
                or route['routingIdentity'] != region['routingIdentities'].get(mode)):
                raise ValueError('Cross-region or stale immutable route reference')
        # Hold the final checkpoint for shorter regions on the common clock.
        # No events or states are fabricated and final booking accounting is unchanged.
        region['simulationDurationSeconds'] = duration
        region['kpis'] = regional_kpis(region, duration)
        region['kpis']['byMode'] = {}
        for mode in ('CAR', 'MOTORBIKE'):
            mode_vehicles = [vehicle for vehicle in region['vehicles'] if vehicle['vehicleType'] == mode]
            mode_bookings = [booking for booking in region['bookings'] if booking['serviceType'] == mode]
            mode_assignments = [assignment for assignment in region['assignments'] if assignment['vehicleType'] == mode]
            subset = {**region, 'vehicles': mode_vehicles, 'bookings': mode_bookings, 'assignments': mode_assignments,
                'timelines': {vehicle['id']: region['timelines'][vehicle['id']] for vehicle in mode_vehicles}}
            region['kpis']['byMode'][mode] = {**regional_kpis(subset, duration), 'fleetSize': len(mode_vehicles),
                'counts': {'requested': len(mode_bookings), 'assigned': len(mode_assignments),
                    'completed': len(mode_assignments), 'unserved': len(mode_bookings)-len(mode_assignments)}}
    counts = {key: sum(r['counts'][key] for r in results) for key in results[0]['counts']}
    events = [{**event, 'id': region['regionId']+':'+event['id'], 'regionId': region['regionId']}
              for region in results for event in region['events']]
    # Stable same-time regional order; preserve engine append order within a region.
    events.sort(key=lambda event: (event['timestampSeconds'], event['regionId'], event['id']))
    wait_sum = sum(r['kpis']['pickupWait']['sumSeconds'] for r in results)
    wait_count = sum(r['kpis']['pickupWait']['count'] for r in results)
    busy = sum(r['kpis']['utilization']['busyVehicleSeconds'] for r in results)
    online = sum(r['kpis']['utilization']['onlineVehicleSeconds'] for r in results)
    fleet_seconds = config.fleetSize*duration
    by_mode = {}
    for mode in ('CAR', 'MOTORBIKE'):
        values = [region['kpis']['byMode'][mode] for region in results]
        wait_seconds = sum(value['pickupWait']['sumSeconds'] for value in values)
        wait_n = sum(value['pickupWait']['count'] for value in values)
        busy_seconds = sum(value['utilization']['busyVehicleSeconds'] for value in values)
        online_seconds = sum(value['utilization']['onlineVehicleSeconds'] for value in values)
        mode_fleet_seconds = sum(value['utilization']['fleetVehicleSeconds'] for value in values)
        by_mode[mode] = {'fleetSize': sum(value['fleetSize'] for value in values),
            'counts': {key: sum(value['counts'][key] for value in values) for key in values[0]['counts']},
            'pickupWait': {'sumSeconds': wait_seconds, 'count': wait_n,
                'meanSeconds': wait_seconds/wait_n if wait_n else None,
                'maximumSeconds': max((value['pickupWait']['maximumSeconds'] for value in values
                    if value['pickupWait']['maximumSeconds'] is not None), default=None)},
            'utilization': {'busyVehicleSeconds': busy_seconds, 'onlineVehicleSeconds': online_seconds,
                'fleetVehicleSeconds': mode_fleet_seconds,
                'busyFractionOfOnline': busy_seconds/online_seconds if online_seconds else None,
                'busyFractionOfFleet': busy_seconds/mode_fleet_seconds if mode_fleet_seconds else None}}
    return {'schemaVersion': RESULT_SCHEMA, 'simulationModelVersion': 'heap-grid-regional/v1',
        'runId': run_id, 'config': config.model_dump(mode='json'), 'globalTotals': config.globalTotals,
        'simulationDurationSeconds': duration, 'regions': results, 'counts': counts, 'events': events,
        'routingIdentities': {r['regionId']: r['routingIdentities'] for r in results},
        'kpis': {'byMode': by_mode, 'pickupWait': {'sumSeconds': wait_sum, 'count': wait_count,
            'meanSeconds': wait_sum/wait_count if wait_count else None,
            'maximumSeconds': max((r['kpis']['pickupWait']['maximumSeconds'] for r in results
                if r['kpis']['pickupWait']['maximumSeconds'] is not None), default=None)},
            'utilization': {'busyVehicleSeconds': busy, 'onlineVehicleSeconds': online,
                'fleetVehicleSeconds': fleet_seconds, 'busyFractionOfOnline': busy/online if online else None,
                'busyFractionOfFleet': busy/fleet_seconds if fleet_seconds else None}},
        'metrics': {'execution': 'sequential regions; shared simulation time origin',
            'eventsProcessed': sum(r['metrics']['eventsProcessed'] for r in results)},
        'assumptions': {'synthetic': True, 'demandVersion': 'm3-demand/v1',
            'regionalSeedVersion': 'nvmr-regional-seed/v1', 'dispatch': 'same region and mode only',
            'clock': 'Shared zero origin; shorter regions hold final state on common duration',
            'travel': 'Local OSRM static model, synthetic fleet/demand; no live traffic or GSM operations'}}


async def simulate_regional(config, prepared_regions, run_id, cancelled=None, progress=None):
    """Fixture/injected execution with explicit separate inputs/travels per region."""
    results = []
    for index, allocation in enumerate(config.regions):
        if cancelled and await cancelled():
            raise HTTPException(499, {'code': 'JOB_CANCELLED', 'message': 'Regional scenario cancelled'})
        prepared = prepared_regions[allocation.regionId]
        async def report(value):
            if progress:
                await progress((index+value)/len(config.regions))
        result = await simulate(engine_config(config, allocation), prepared['vehicles'], prepared['bookings'],
            prepared['travels'], prepared['identities'], run_id, cancelled, report)
        result['provenance'] = prepared.get('provenance', {'syntheticFixture': True})
        results.append(result)
    return combine_regions(config, results, run_id)


def regional_snapshot(result, time_seconds):
    if not math.isfinite(time_seconds) or time_seconds < 0:
        raise ValueError('Expected nonnegative finite simulation time')
    now = min(time_seconds, result['simulationDurationSeconds'])
    regions = [snapshot(region, now) for region in result['regions']]
    counts = {key: sum(region['counts'][key] for region in regions) for key in regions[0]['counts']}
    return {'schemaVersion': 'gsm-nvmr-regional-snapshot/v1', 'runId': result['runId'],
        'sequenceNumber': math.floor(now*1000000), 'simulationTimeSeconds': now,
        'counts': counts, 'regions': regions,
        'vehicles': [{**vehicle, 'regionId': region['regionId']} for region in regions for vehicle in region['vehicles']],
        'routingIdentities': result['routingIdentities']}


def regional_summary(result):
    keys = ('schemaVersion', 'runId', 'config', 'globalTotals', 'simulationDurationSeconds',
            'counts', 'routingIdentities', 'kpis', 'metrics', 'assumptions', 'simulationModelVersion')
    output = {key: result[key] for key in keys}
    output['regions'] = [{key: region[key] for key in ('schemaVersion', 'runId', 'regionId', 'config',
        'simulationDurationSeconds', 'counts', 'routingIdentities', 'kpis', 'metrics', 'provenance', 'assumptions')}
        for region in result['regions']]
    return output
