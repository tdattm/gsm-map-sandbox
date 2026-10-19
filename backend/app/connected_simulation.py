"""Connected NVMR: one immutable world over the existing global event engine.

Zones describe research operating areas, never dispatch partitions. Geographic
distances below select/describe inputs only; all service evidence comes from the
injected mode-specific travel adapters.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import PROJECT_ROOT
from .regional_simulation import regional_kpis
from .simulation import (BookingInput, SimulationConfig, VehicleInput, meters,
                         simulate, snapshot, validate_result)

SCHEMA = 'gsm-nvmr-connected-scenario/v1'
RESULT_SCHEMA = 'gsm-nvmr-connected-result/v1'
REGION_ID = 'nvmr-connected'
ZONE_IDS = ('hanoi', 'bac-ninh', 'hung-yen', 'phu-tho', 'thai-nguyen')
ZONE_WEIGHTS = dict(zip(ZONE_IDS, (16, 1, 1, 1, 1)))


def integer_allocation(total, weights):
    """Largest remainders with canonical tie order; exact independently per mode."""
    denominator = sum(weights.values())
    if denominator <= 0 or any(not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError('Allocation weights must be finite, nonnegative and nonzero')
    quotas = {key: total*weights[key]/denominator for key in weights}
    result = {key: math.floor(value) for key, value in quotas.items()}
    order = sorted(weights, key=lambda key: (-(quotas[key]-result[key]), ZONE_IDS.index(key)))
    for key in order[:total-sum(result.values())]:
        result[key] += 1
    return result


class FleetAllocation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    zoneId: Literal['hanoi', 'bac-ninh', 'hung-yen', 'phu-tho', 'thai-nguyen']
    carCount: int = Field(ge=0, le=5000, strict=True)
    motorbikeCount: int = Field(ge=0, le=5000, strict=True)


class DistributionConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    cellDegrees: float = Field(default=.025, gt=0, le=.2, allow_inf_nan=False)
    maximumVehiclesPerPosition: int = Field(default=1, ge=1, le=100, strict=True)
    nearestNeighborSampleSize: int = Field(default=128, ge=0, le=512, strict=True)


class ConnectedScenarioConfig(SimulationConfig):
    """New public contract; v3/v4 configurations retain their historical meaning."""
    regionId: Literal['nvmr-connected'] = REGION_ID
    schemaVersion: Literal['gsm-nvmr-connected-scenario/v1'] = SCHEMA
    seed: str = Field(default='connected-nvmr-r1b', min_length=1, max_length=80)
    fleetSize: int = Field(default=5000, ge=1, le=5000, strict=True)
    carCount: int = Field(default=2000, ge=0, le=5000, strict=True)
    fleetAllocations: tuple[FleetAllocation, ...] | None = None
    demandWeights: dict[str, float] = Field(default_factory=lambda: dict.fromkeys(ZONE_IDS, 1.))
    demandCarFraction: float = Field(default=.4, ge=0, le=1, allow_inf_nan=False)
    crossZoneDemandFraction: float = Field(default=.25, ge=0, le=1, allow_inf_nan=False)
    distribution: DistributionConfig = Field(default_factory=DistributionConfig)

    @model_validator(mode='after')
    def connected_bounds(self):
        if set(self.demandWeights) != set(ZONE_IDS):
            raise ValueError('Demand weights must specify all five operating zones')
        integer_allocation(self.bookingCount, self.demandWeights)
        if self.fleetAllocations is None:
            cars = integer_allocation(self.carCount, ZONE_WEIGHTS)
            motos = integer_allocation(self.fleetSize-self.carCount, ZONE_WEIGHTS)
            allocations = tuple(FleetAllocation(zoneId=z, carCount=cars[z], motorbikeCount=motos[z]) for z in ZONE_IDS)
        else:
            allocations = self.fleetAllocations
            if len(allocations) != 5 or {a.zoneId for a in allocations} != set(ZONE_IDS):
                raise ValueError('Fleet allocation requires each operating zone exactly once')
            if (sum(a.carCount for a in allocations) != self.carCount or
                sum(a.motorbikeCount for a in allocations) != self.fleetSize-self.carCount):
                raise ValueError('Zone/mode counts must conserve the global fleet and mode totals')
            allocations = tuple(sorted(allocations, key=lambda a: ZONE_IDS.index(a.zoneId)))
        object.__setattr__(self, 'fleetAllocations', allocations)
        return self


def load_zones(path=None):
    raw = json.loads(Path(path or PROJECT_ROOT/'config/connected-nvmr.json').read_text(encoding='utf-8'))
    zones = raw['operatingZones']
    if {z['id'] for z in zones} != set(ZONE_IDS):
        raise ValueError('Connected configuration must describe the five versioned technical zones')
    for i, zone in enumerate(zones):
        w, s, e, n = zone['bbox']
        if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise ValueError('Invalid technical zone bounds')
        for other in zones[:i]:
            a, b, c, d = other['bbox']
            if max(w, a) < min(e, c) and max(s, b) < min(n, d):
                raise ValueError('Technical operating zones must not overlap')
    return zones


def zone_at(point, zones):
    # Half-open rectangles guarantee one attribution even at shared edges.
    matches = [z['id'] for z in zones if z['bbox'][0] <= point[0] < z['bbox'][2]
               and z['bbox'][1] <= point[1] < z['bbox'][3]]
    if len(matches) > 1:
        raise ValueError('Ambiguous overlapping zone attribution')
    return matches[0] if matches else 'outside-operating-zones'


def _rank(seed, namespace, value):
    return hashlib.sha256(json.dumps([seed, namespace, value], sort_keys=True).encode()).digest()


def stratified_positions(anchors, count, config, seed, namespace, prior_usage=None):
    """Round-robin occupied road cells, unique road vertices before repetitions."""
    cells = defaultdict(list)
    for point in sorted({tuple(p) for p in anchors}):
        if len(point) != 2 or not all(math.isfinite(v) for v in point):
            raise ValueError('Malformed road-derived anchor')
        key = tuple(math.floor(v/config.cellDegrees) for v in point)
        cells[key].append(point)
    usage = Counter(prior_usage or {})
    if count > sum(max(0, config.maximumVehiclesPerPosition-usage[p]) for bucket in cells.values() for p in bucket):
        raise ValueError(f'Insufficient unique road anchors for {namespace}: requested {count}')
    ordered = sorted(cells, key=lambda key: _rank(seed, namespace, key))
    for key in ordered:
        cells[key].sort(key=lambda point: _rank(seed, namespace, point))
    result, offsets = [], Counter()
    while len(result) < count:
        for key in ordered:
            bucket = cells[key]
            if any(usage[p] < config.maximumVehiclesPerPosition for p in bucket):
                while usage[bucket[offsets[key] % len(bucket)]] >= config.maximumVehiclesPerPosition:
                    offsets[key] += 1
                point = bucket[offsets[key] % len(bucket)]
                offsets[key] += 1
                result.append(point)
                usage[point] += 1
                if len(result) == count:
                    break
    return result


def connected_inputs(config, anchors_by_mode, zones):
    """Independent deterministic fleet/demand streams, no fabricated coordinates."""
    pools = {}
    for mode in ('CAR', 'MOTORBIKE'):
        for zone in ZONE_IDS:
            pools[mode, zone] = sorted({tuple(p) for p in anchors_by_mode.get(mode, []) if zone_at(p, zones) == zone})
    vehicles, metadata, used_positions = [], {}, Counter()
    for allocation in config.fleetAllocations:
        for mode, count in (('CAR', allocation.carCount), ('MOTORBIKE', allocation.motorbikeCount)):
            available = [p for p in pools[mode, allocation.zoneId]
                         if used_positions[p] < config.distribution.maximumVehiclesPerPosition]
            positions = stratified_positions(available, count, config.distribution,
                config.seed, f'fleet:{allocation.zoneId}:{mode}', used_positions)
            for index, point in enumerate(positions):
                identity = f'NVMR-{mode}-{allocation.zoneId}-{index+1:05}'
                vehicles.append(VehicleInput(id=identity, vehicleType=mode, position=point,
                    online=index < round(count*config.onlineFraction),
                    schedule=tuple((p.timeSeconds, index < round(count*p.onlineFraction)) for p in config.onlineSchedule)))
                metadata[identity] = {'homeZoneId': allocation.zoneId}
                used_positions[point] += 1
    demand_counts = integer_allocation(config.bookingCount, config.demandWeights)
    bookings, booking_meta = [], {}
    for zone in ZONE_IDS:
        for index in range(demand_counts[zone]):
            identity = f'NVMR-BK-{zone}-{index+1:06}'
            def draw(label):
                return int.from_bytes(_rank(config.seed, f'demand:{identity}:{label}', 0)[:8], 'big')/2**64
            mode = 'CAR' if draw('mode') < config.demandCarFraction else 'MOTORBIKE'
            destination_zone = zone
            if draw('cross-zone') < config.crossZoneDemandFraction:
                choices = [z for z in ZONE_IDS if z != zone and config.demandWeights[z] > 0]
                if choices:
                    destination_zone = choices[min(len(choices)-1, int(draw('destination-zone')*len(choices)))]
            source, destination = pools[mode, zone], pools[mode, destination_zone]
            if not source or not destination:
                raise ValueError(f'No road anchors for demand {mode}: {zone} -> {destination_zone}')
            start = source[min(len(source)-1, int(draw('pickup')*len(source)))]
            if len(destination) == 1 and destination[0] == start:
                raise ValueError('Demand requires two distinct road-derived anchors')
            target = min(len(destination)-1, int(draw('dropoff')*len(destination)))
            if destination[target] == start:
                target = (target+1) % len(destination)
            end = destination[target]
            arrival = draw('arrival')*config.horizonSeconds*(.05 if config.workload == 'burst' else 1)
            bookings.append(BookingInput(id=identity, serviceType=mode, requestTimeSeconds=round(arrival, 3), pickup=start, dropoff=end))
            booking_meta[identity] = {'pickupZoneId': zone, 'dropoffZoneId': destination_zone,
                'potentialPassengerId': identity.replace('BK-', 'PERSON-')}
    return vehicles, sorted(bookings, key=lambda b: (b.requestTimeSeconds, b.id)), metadata, booking_meta


def distribution_quality(vehicles, metadata, config):
    points = [tuple(v.position) for v in vehicles]
    duplicates = Counter(points)
    cells = Counter(tuple(math.floor(x/config.cellDegrees) for x in point) for point in points)
    nn = []
    sample = sorted(range(len(points)), key=lambda i: _rank('distribution-quality/v1', 'sample', vehicles[i].id))[:config.nearestNeighborSampleSize]
    for i in sample:
        distance = min((meters(points[i], p) for j, p in enumerate(points) if j != i), default=None)
        if distance is not None:
            nn.append(distance)
    nn.sort()
    by_zone_mode = Counter((metadata[v.id]['homeZoneId'], v.vehicleType) for v in vehicles)
    return {'vehicleCount': len(vehicles), 'uniqueSnappedPositions': len(duplicates),
        'duplicateVehicles': len(vehicles)-len(duplicates), 'maximumVehiclesPerPosition': max(duplicates.values(), default=0),
        'occupiedCells': len(cells), 'cellDegrees': config.cellDegrees,
        'maximumCellOccupancy': max(cells.values(), default=0),
        'crowdedCells': [{'cell': list(cell), 'count': count} for cell, count in sorted(cells.items()) if count > 50],
        'byZone': {zone: {mode: by_zone_mode[zone, mode] for mode in ('CAR', 'MOTORBIKE')} for zone in ZONE_IDS},
        'nearestNeighborMeters': {'sampleCount': len(nn), 'minimum': nn[0] if nn else None,
            'median': nn[len(nn)//2] if nn else None, 'p95': nn[min(len(nn)-1, int(len(nn)*.95))] if nn else None},
        'limitations': 'Nearest-neighbor sample against all vehicles; geographic distances describe distribution, not routing. Technical operating zones are not administrative boundaries.'}


def connected_kpis(result):
    duration = result['simulationDurationSeconds']
    def subset(vehicles, bookings):
        bids = {b['id'] for b in bookings}
        assignments = [a for a in result['assignments'] if a['bookingId'] in bids]
        raw = {**result, 'vehicles': vehicles, 'bookings': bookings, 'assignments': assignments,
            'timelines': {v['id']: result['timelines'][v['id']] for v in vehicles}}
        return {**regional_kpis(raw, duration), 'fleetSize': len(vehicles),
            'counts': {'requested': len(bookings), 'assigned': len(assignments), 'completed': len(assignments), 'unserved': len(bookings)-len(assignments)}}
    return {'global': subset(result['vehicles'], result['bookings']),
        'byZone': {zone: subset([v for v in result['vehicles'] if v['homeZoneId'] == zone],
            [b for b in result['bookings'] if b['pickupZoneId'] == zone]) for zone in ZONE_IDS},
        'byMode': {mode: subset([v for v in result['vehicles'] if v['vehicleType'] == mode],
            [b for b in result['bookings'] if b['serviceType'] == mode]) for mode in ('CAR', 'MOTORBIKE')},
        'attribution': 'Demand and wait by requested pickup zone; fleet and utilization by immutable vehicle home zone; additive numerators/denominators.'}


async def simulate_connected(config, vehicles, bookings, travels, identities, run_id,
                             zones, vehicle_metadata, booking_metadata, cancelled=None, progress=None):
    result = await simulate(config, vehicles, bookings, travels, identities, run_id, cancelled, progress)
    for vehicle in result['vehicles']:
        vehicle.update(vehicle_metadata[vehicle['id']], currentZoneId=zone_at(vehicle['position'], zones))
    for booking in result['bookings']:
        booking.update(booking_metadata[booking['id']])
    booking_index = {b['id']: b for b in result['bookings']}
    for assignment in result['assignments']:
        trip = result['routes'][assignment['tripRouteRef']]
        booking = booking_index[assignment['bookingId']]
        booking.update(snappedPickup=list(trip['coordinates'][0]), snappedDropoff=list(trip['coordinates'][-1]),
            snappedPickupZoneId=zone_at(trip['coordinates'][0], zones),
            snappedDropoffZoneId=zone_at(trip['coordinates'][-1], zones))
        booking['snapCrossedTechnicalZone'] = (booking['snappedPickupZoneId'] != booking['pickupZoneId'] or
            booking['snappedDropoffZoneId'] != booking['dropoffZoneId'])
    result.update(schemaVersion=RESULT_SCHEMA, simulationModelVersion='heap-grid-connected/v1', operatingZones=zones)
    result['kpis'] = connected_kpis(result)
    result['distributionQuality'] = distribution_quality(vehicles, vehicle_metadata, config.distribution)
    checkpoints = {(vid, t['bookingId']): t for vid, timeline in result['timelines'].items()
                   for t in timeline if t['state'] == 'ASSIGNED'}
    crossings = 0
    for assignment in result['assignments']:
        checkpoint = checkpoints[assignment['vehicleId'], assignment['bookingId']]
        booking = booking_index[assignment['bookingId']]
        assignment['vehicleZoneAtAssignment'] = zone_at(checkpoint['position'], zones)
        assignment['pickupZoneId'] = booking['pickupZoneId']
        crossings += assignment['vehicleZoneAtAssignment'] != assignment['pickupZoneId']
    result['metrics']['crossZoneDispatches'] = crossings
    result['assumptions'].update(dispatchScope='Global mode-specific pool; zones never filter candidates',
        demandVersion='connected-independent-demand/v1', allocationVersion='largest-remainder-per-mode/v1',
        distributionVersion='road-cell-round-robin/v1', administrativeAttribution='Versioned technical operating zones, not official province boundaries',
        bookingZoneAttribution='KPI zone uses requested pickup; assigned bookings also retain snapped endpoint zones and snapCrossedTechnicalZone',
        synthetic=True, m5Interface={'version': 'connected-world-input/v1', 'potentialPassengerId': True,
            'choiceSet': ['NO_BOOK', 'CAR', 'MOTORBIKE'], 'voucherModel': None,
            'controlledRandomness': 'Identity-keyed SHA256 draws; fleet and passenger streams independent',
            'independentWorlds': 'Create separate immutable jobs with common exogenous seed; no shared mutable fleet'})
    validate_connected_result(result)
    return result


def validate_connected_result(result):
    validate_result(result)
    config = ConnectedScenarioConfig.model_validate(result['config'])
    if result['schemaVersion'] != RESULT_SCHEMA or len(result['vehicles']) != config.fleetSize:
        raise ValueError('Connected result schema/fleet mismatch')
    expected = connected_kpis(result)
    if expected != result['kpis']:
        raise ValueError('Global and zone KPI numerators/denominators do not reconcile')
    for allocation in config.fleetAllocations:
        for mode, n in (('CAR', allocation.carCount), ('MOTORBIKE', allocation.motorbikeCount)):
            if sum(v['homeZoneId'] == allocation.zoneId and v['vehicleType'] == mode for v in result['vehicles']) != n:
                raise ValueError('Zone/mode fleet conservation failure')
    return True


def connected_snapshot(result, time_seconds):
    projected = snapshot(result, time_seconds)
    home = {v['id']: v['homeZoneId'] for v in result['vehicles']}
    zones = result['operatingZones']
    keys = ('total', 'offline', 'online', 'idle', 'assigned', 'onTrip', 'moving')
    counts = {zone: dict.fromkeys(keys, 0) for zone in (*ZONE_IDS, 'outside-operating-zones')}
    for vehicle in projected['vehicles']:
        vehicle.update(homeZoneId=home[vehicle['id']], currentZoneId=zone_at(vehicle['position'], zones), isMoving=False)
        bucket = counts[vehicle['currentZoneId']]
        bucket['total'] += 1
        bucket[{'OFFLINE': 'offline', 'IDLE': 'idle', 'ASSIGNED': 'assigned', 'ON_TRIP': 'onTrip'}[vehicle['serviceState']]] += 1
        if vehicle['serviceState'] != 'OFFLINE':
            bucket['online'] += 1
        if vehicle['routeRef']:
            # Match the global projector: nonzero geometry still in progress.
            route = result['routes'][vehicle['routeRef']]
            timeline = result['timelines'][vehicle['id']]
            active = next(t for t in reversed(timeline) if t['time'] <= projected['simulationTimeSeconds'])
            if active['endTime'] > projected['simulationTimeSeconds'] and route['cumulativeMeters'][-1] > .1:
                bucket['moving'] += 1
                vehicle['isMoving'] = True
    if any(sum(bucket[key] for bucket in counts.values()) != projected['counts'][key] for key in keys):
        raise ValueError('Snapshot zone/global vehicle conservation failure')
    projected.update(schemaVersion='gsm-nvmr-connected-snapshot/v1', zoneCounts=counts)
    return projected


def connected_summary(result):
    return {key: result[key] for key in ('schemaVersion', 'runId', 'regionId', 'config',
        'simulationDurationSeconds', 'counts', 'routingIdentities', 'assumptions', 'metrics',
        'kpis', 'distributionQuality', 'operatingZones', 'simulationModelVersion', 'provenance') if key in result}
