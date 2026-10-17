"""NVMR v3 event core. Travel evidence is injected; no synthetic runtime routing.

This module deliberately leaves v1/v2 booking and voucher contracts untouched.
All simulation ordering uses simulation time, never request completion/wall time.
"""
from bisect import bisect_right, insort
from collections import OrderedDict
import hashlib
import heapq
import json
import math
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import Coordinate

MODES = ('CAR', 'MOTORBIKE')
STATES = ('OFFLINE', 'IDLE', 'ASSIGNED', 'ON_TRIP')


def meters(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, h)))


class OnlineSchedulePoint(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    timeSeconds: float = Field(ge=0, allow_inf_nan=False)
    onlineFraction: float = Field(ge=0, le=1, allow_inf_nan=False, strict=True)


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    regionId: Literal['nvmr-hanoi-core'] = 'nvmr-hanoi-core'
    seed: str = Field(default='nvmr-m3', min_length=1, max_length=80)
    fleetSize: int = Field(default=100, ge=1, le=5000, strict=True)
    carCount: int = Field(default=40, ge=0, le=5000, strict=True)
    bookingCount: int = Field(default=20, ge=0, le=20000, strict=True)
    horizonSeconds: int = Field(default=900, ge=1, le=86400, strict=True)
    maxWaitSeconds: int = Field(default=300, ge=0, le=3600, strict=True)
    onlineFraction: float = Field(default=.8, ge=0, le=1, allow_inf_nan=False, strict=True)
    onlineSchedule: tuple[OnlineSchedulePoint, ...] = ()
    workload: Literal['low', 'typical', 'burst'] = 'typical'
    initialCandidates: int = Field(default=16, ge=1, le=128, strict=True)
    maxCandidates: int = Field(default=128, ge=1, le=512, strict=True)
    gridCellDegrees: float = Field(default=.005, gt=0, le=.1, allow_inf_nan=False)

    @model_validator(mode='after')
    def bounds(self):
        if self.carCount > self.fleetSize or self.initialCandidates > self.maxCandidates:
            raise ValueError('CAR count or initial shortlist exceeds its bound')
        times = [p.timeSeconds for p in self.onlineSchedule]
        if times != sorted(set(times)) or any(t > self.horizonSeconds for t in times):
            raise ValueError('Online schedule must be strictly increasing within horizon')
        return self


class VehicleInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str = Field(min_length=1)
    vehicleType: Literal['CAR', 'MOTORBIKE']
    position: Coordinate
    online: bool = True
    # Each transition is (simulation seconds, desired online). Busy OFFLINE is deferred.
    schedule: tuple[tuple[float, bool], ...] = ()

    @model_validator(mode='after')
    def valid_schedule(self):
        times = [x[0] for x in self.schedule]
        if any(not math.isfinite(t) or t < 0 for t in times) or times != sorted(set(times)):
            raise ValueError('Schedule needs unique increasing finite times')
        return self


class BookingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str = Field(min_length=1)
    serviceType: Literal['CAR', 'MOTORBIKE']
    requestTimeSeconds: float = Field(ge=0, allow_inf_nan=False)
    pickup: Coordinate
    dropoff: Coordinate

    @model_validator(mode='after')
    def different_points(self):
        if self.pickup == self.dropoff:
            raise ValueError('Pickup and dropoff must differ')
        return self


def generate_inputs(config, anchors):
    """Hash-counter exogenous draws. Multiple vehicles may share a verified anchor."""
    if len({tuple(p) for p in anchors}) < 2:
        raise ValueError('Need two distinct verified anchors')
    anchors = sorted({tuple(p) for p in anchors})
    counter = 0

    def draw(n):
        nonlocal counter
        value = int.from_bytes(hashlib.sha256(f'm3-demand/v1:{config.seed}:{counter}'.encode()).digest()[:8], 'big')
        counter += 1
        return value % n

    vehicles = []
    for i in range(config.fleetSize):
        mode = 'CAR' if i < config.carCount else 'MOTORBIKE'
        # Exact online fraction per mode avoids accidentally zero CAR in a small pilot.
        offset = i if mode == 'CAR' else i-config.carCount
        count = config.carCount if mode == 'CAR' else config.fleetSize-config.carCount
        vehicles.append(VehicleInput(id=f'GSM-{i+1:05}', vehicleType=mode,
            position=anchors[draw(len(anchors))], online=offset < round(count*config.onlineFraction),
            schedule=tuple((p.timeSeconds, offset < round(count*p.onlineFraction)) for p in config.onlineSchedule)))
    bookings = []
    for i in range(config.bookingCount):
        a = draw(len(anchors))
        b = (a+1+draw(len(anchors)-1)) % len(anchors)
        arrival = draw(1000000)/1000000*config.horizonSeconds
        if config.workload == 'burst':
            arrival *= .05
        service = 'CAR' if draw(config.fleetSize) < config.carCount else 'MOTORBIKE'
        bookings.append(BookingInput(id=f'BK-{i+1:06}', serviceType=service,
            requestTimeSeconds=round(arrival, 3), pickup=anchors[a], dropoff=anchors[b]))
    return vehicles, sorted(bookings, key=lambda b: (b.requestTimeSeconds, b.id))


class IdleGrid:
    """Mode partitioned cells with sorted identities. Only occupied cells are visited.

    Cells ordered by squared distance of their bounding box; nearby cell candidates
    are ranked by distance, then ID, to build a heuristic shortlist (not ETA winner).
    No full-fleet OSRM Table and no sorting all idle identities per dispatch.
    """
    def __init__(self, cell_size):
        self.size = cell_size
        self.cells = {m: {} for m in MODES}
        self.positions = {}
        self.mode_counts = {m: 0 for m in MODES}

    def key(self, p):
        return (math.floor(p[0]/self.size), math.floor(p[1]/self.size))

    def add(self, id, mode, p):
        if id in self.positions:
            raise ValueError('Duplicate idle insertion')
        p = tuple(p)
        self.positions[id] = (mode, p)
        insort(self.cells[mode].setdefault(self.key(p), []), id)
        self.mode_counts[mode] += 1

    def remove(self, id):
        mode, p = self.positions.pop(id)
        key = self.key(p)
        bucket = self.cells[mode][key]
        bucket.remove(id)
        if not bucket:
            del self.cells[mode][key]
        self.mode_counts[mode] -= 1

    def shortlist(self, mode, pickup, limit, excluded=()):
        excluded = set(excluded)
        x, y = pickup
        def cell_distance(key):
            a, b = key
            dx = max(a*self.size-x, 0, x-(a+1)*self.size)
            dy = max(b*self.size-y, 0, y-(b+1)*self.size)
            return dx*dx+dy*dy
        cells = [(cell_distance(key), key) for key in self.cells[mode]]
        heapq.heapify(cells)
        candidates = []
        while cells and len(candidates) < limit:
            _, key = heapq.heappop(cells)
            # Stop collecting even when a depot has thousands of idle vehicles.
            for id in self.cells[mode][key]:
                if id not in excluded:
                    p = self.positions[id][1]
                    candidates.append(((p[0]-x)**2+(p[1]-y)**2, id))
                    if len(candidates) >= limit:
                        break
        return [id for _, id in sorted(candidates)]


async def simulate(config, initial, demand, travels, identities, run_id, cancelled=None, progress=None):
    """Heap indexed lifecycle; deterministic single routing operation in flight.

    Same time: completions -> schedules -> arrivals -> pickup transitions -> FIFO
    dispatch -> inclusive deadline expiration. New zero pickup transitions happen
    atomically after assignment. Busy shift ending finishes service then goes offline.
    """
    if len({v.id for v in initial}) != len(initial) or len({b.id for b in demand}) != len(demand):
        raise ValueError('Duplicate immutable input identities')
    if len(initial) != config.fleetSize or len(demand) != config.bookingCount:
        raise ValueError('Input cardinality differs from config')
    if sum(v.vehicleType == 'CAR' for v in initial) != config.carCount:
        raise ValueError('Input mode mix differs from config')
    vehicles = {v.id: {'input': v, 'position': list(v.position), 'state': 'IDLE' if v.online else 'OFFLINE',
                      'booking': None, 'desiredOnline': v.online} for v in initial}
    grid = IdleGrid(config.gridCellDegrees)
    events, routes, assignments = [], {}, []
    timelines = {v.id: [] for v in initial}
    pending = {m: OrderedDict() for m in MODES}
    invalid, reasons, trips = {}, {}, {}
    queue, counter, terminal_count = [], 0, 0
    metrics = {'eventsProcessed': 0, 'peakEventQueue': 0, 'peakPending': 0, 'tableCandidates': 0,
               'searchBudgetExhaustions': 0, 'dispatchAttempts': 0, 'dispatchVersion': 'grid-fifo/v1'}

    def push(t, priority, kind, id):
        nonlocal counter
        heapq.heappush(queue, (t, priority, id, counter, kind))
        counter += 1
        metrics['peakEventQueue'] = max(metrics['peakEventQueue'], len(queue))

    def emit(kind, now, booking=None, vehicle=None, **payload):
        nonlocal terminal_count
        events.append({'id': f'EV-{len(events)+1:08}', 'timestampSeconds': now, 'type': kind,
                       'bookingId': booking, 'vehicleId': vehicle, 'payload': payload})
        if kind in ('TRIP_COMPLETED', 'BOOKING_UNSERVED'):
            terminal_count += 1

    def transition(id, now, state, booking=None, route=None, end=None):
        v = vehicles[id]
        v.update(state=state, booking=booking)
        timelines[id].append({'time': now, 'state': state, 'bookingId': booking,
            'position': list(v['position']), 'routeRef': route, 'endTime': end})

    def save_route(route, mode):
        raw = route.model_dump(mode='json') if hasattr(route, 'model_dump') else dict(route)
        # Geometry stored once, never repeated in vehicle snapshots.
        key = hashlib.sha256(json.dumps([mode, identities[mode], raw], sort_keys=True).encode()).hexdigest()
        if key not in routes:
            coords = raw['coordinates']
            distances = [0.]
            for a, b in zip(coords, coords[1:]):
                distances.append(distances[-1]+meters(a, b))
            routes[key] = {'schemaVersion': 'gsm-simulation-route/v1', 'runId': run_id,
                'regionId': config.regionId, 'routeRef': key, 'routingIdentity': identities[mode],
                'coordinates': coords, 'distance': raw['distance'], 'duration': raw['duration'],
                'cumulativeMeters': distances}
        return key

    async def check_cancel():
        if cancelled and await cancelled():
            raise HTTPException(499, {'code': 'JOB_CANCELLED', 'message': 'Simulation cancelled'})

    for id, v in vehicles.items():
        transition(id, 0, v['state'])
        if v['state'] == 'IDLE':
            grid.add(id, v['input'].vehicleType, v['position'])
        for t, _ in v['input'].schedule:
            push(t, 1, 'schedule', id)
    bookings = {b.id: b for b in demand}
    for b in demand:
        push(b.requestTimeSeconds, 2, 'arrival', b.id)
        push(b.requestTimeSeconds+config.maxWaitSeconds, 4, 'deadline', b.id)

    async def dispatch(now, modes):
        for mode in MODES:
            if mode not in modes or not grid.mode_counts[mode]:
                continue
            travel = travels[mode]
            for bid, b in list(pending[mode].items()):
                if not grid.mode_counts[mode]:
                    break
                if bid in invalid:
                    continue
                await check_cancel()
                metrics['dispatchAttempts'] += 1
                deadline = b.requestTimeSeconds+config.maxWaitSeconds
                if now > deadline:
                    continue
                if bid not in trips:
                    try:
                        trips[bid] = await travel.route(b.pickup, b.dropoff)
                    except HTTPException as exc:
                        if exc.status_code != 422:
                            raise
                        invalid[bid] = exc.detail['code']
                        continue
                trip = trips[bid]
                checked, selected, batch_size = [], None, config.initialCandidates
                candidate_evidence = []
                while len(checked) < min(config.maxCandidates, grid.mode_counts[mode]):
                    ids = grid.shortlist(mode, trip.coordinates[0],
                        min(batch_size, config.maxCandidates-len(checked)), checked)
                    if not ids:
                        break
                    await check_cancel()
                    try:
                        etas = await travel.table([vehicles[id]['position'] for id in ids], trip.coordinates[0])
                    except HTTPException as exc:
                        if exc.status_code != 422:
                            raise
                        # A recoverable disconnected Table batch is evidence only
                        # for this batch. Expand, preserve code if nothing is feasible.
                        reasons[bid] = exc.detail['code']
                        etas = [None]*len(ids)
                    if len(etas) != len(ids) or any(e is not None and
                        (isinstance(e, bool) or not isinstance(e, (int, float)) or not math.isfinite(e) or e < 0) for e in etas):
                        raise ValueError('Malformed travel table')
                    metrics['tableCandidates'] += len(ids)
                    checked.extend(ids)
                    candidate_evidence.extend({'vehicleId': id, 'etaSeconds': eta} for id, eta in zip(ids, etas))
                    for eta, id in sorted((eta, id) for id, eta in zip(ids, etas) if eta is not None and now+eta <= deadline):
                        p = vehicles[id]['position']
                        try:
                            pickup = None if meters(p, trip.coordinates[0]) < .1 else await travel.route(p, trip.coordinates[0])
                            duration = pickup.duration if pickup else 0
                            if pickup and (meters(pickup.coordinates[0], p) > 1 or
                                           meters(pickup.coordinates[-1], trip.coordinates[0]) > 1):
                                reasons[bid] = 'DISCONTINUOUS_LEGS'
                                continue
                            if now+duration > deadline:
                                reasons[bid] = 'PICKUP_WAIT_LIMIT'
                                continue
                            selected = (id, pickup, duration, eta)
                            break
                        except HTTPException as exc:
                            if exc.status_code != 422:
                                raise
                            reasons[bid] = exc.detail['code']
                    if selected:
                        break
                    batch_size = min(batch_size*2, config.maxCandidates)
                if selected is None:
                    if len(checked) < grid.mode_counts[mode]:
                        reasons[bid] = 'SEARCH_BUDGET_EXHAUSTED'
                        metrics['searchBudgetExhaustions'] += 1
                    else:
                        reasons.setdefault(bid, 'PICKUP_WAIT_LIMIT' if any(x['etaSeconds'] is not None for x in candidate_evidence) else 'NO_ROUTE')
                    continue
                id, pickup, duration, eta = selected
                grid.remove(id)
                del pending[mode][bid]
                pickup_ref = save_route(pickup, mode) if pickup else None
                trip_ref = save_route(trip, mode)
                a = {'bookingId': bid, 'vehicleId': id, 'vehicleType': mode, 'assignedAtSeconds': now,
                    'pickupAtSeconds': now+duration, 'dropoffAtSeconds': now+duration+trip.duration,
                    'pickupRouteRef': pickup_ref, 'tripRouteRef': trip_ref, 'tableEtaSeconds': eta,
                    'estimatedPickupEtaSeconds': duration, 'dispatchCandidates': candidate_evidence}
                assignments.append(a)
                emit('BOOKING_ASSIGNED', now, bid, id, tableEtaSeconds=eta, estimatedPickupEtaSeconds=duration)
                transition(id, now, 'ASSIGNED', bid, pickup_ref, now+duration)
                if duration == 0:
                    vehicles[id]['position'] = list(trip.coordinates[0])
                    emit('VEHICLE_ARRIVED_PICKUP', now, bid, id)
                    emit('TRIP_STARTED', now, bid, id)
                    transition(id, now, 'ON_TRIP', bid, trip_ref, a['dropoffAtSeconds'])
                else:
                    push(a['pickupAtSeconds'], 3, 'pickup', len(assignments)-1)
                push(a['dropoffAtSeconds'], 0, 'complete', len(assignments)-1)

    now = 0.
    while queue:
        await check_cancel()
        now = queue[0][0]
        batch = []
        while queue and queue[0][0] == now:
            batch.append(heapq.heappop(queue))
        changed, deadlines = set(), []
        for _, _, id, _, kind in batch:
            metrics['eventsProcessed'] += 1
            if kind in ('complete', 'pickup'):
                a = assignments[id]
                vid, bid = a['vehicleId'], a['bookingId']
                v = vehicles[vid]
                route = routes[a['tripRouteRef']]
                if kind == 'complete':
                    v['position'] = list(route['coordinates'][-1])
                    emit('TRIP_COMPLETED', now, bid, vid)
                    state = 'IDLE' if v['desiredOnline'] else 'OFFLINE'
                    transition(vid, now, state)
                    if state == 'IDLE':
                        grid.add(vid, a['vehicleType'], v['position'])
                        changed.add(a['vehicleType'])
                else:
                    v['position'] = list(route['coordinates'][0])
                    emit('VEHICLE_ARRIVED_PICKUP', now, bid, vid)
                    emit('TRIP_STARTED', now, bid, vid)
                    transition(vid, now, 'ON_TRIP', bid, a['tripRouteRef'], a['dropoffAtSeconds'])
            elif kind == 'schedule':
                v = vehicles[id]
                desired = dict(v['input'].schedule)[now]
                v['desiredOnline'] = desired
                emit('VEHICLE_ONLINE' if desired else 'VEHICLE_OFFLINE_REQUESTED', now, vehicle=id)
                if v['state'] in ('IDLE', 'OFFLINE'):
                    if v['state'] == 'IDLE':
                        grid.remove(id)
                    transition(id, now, 'IDLE' if desired else 'OFFLINE')
                    if desired:
                        grid.add(id, v['input'].vehicleType, v['position'])
                        changed.add(v['input'].vehicleType)
            elif kind == 'arrival':
                b = bookings[id]
                pending[b.serviceType][id] = b
                emit('BOOKING_REQUESTED', now, id)
                changed.add(b.serviceType)
            else:
                deadlines.append(id)
                changed.add(bookings[id].serviceType)
        metrics['peakPending'] = max(metrics['peakPending'], sum(len(p) for p in pending.values()))
        await dispatch(now, changed)
        for bid in deadlines:
            mode = bookings[bid].serviceType
            if bid in pending[mode]:
                reason = invalid.get(bid, reasons.get(bid, 'NO_ONLINE_IDLE_VEHICLE'))
                emit('BOOKING_UNSERVED', now, bid, failureReason=reason)
                del pending[mode][bid]
        if progress:
            await progress(min(.99, terminal_count/max(1, len(demand))))
    # Event append order is the authoritative same-time execution order.
    result = {'schemaVersion': 'gsm-simulation-result/v1', 'runId': run_id, 'regionId': config.regionId,
        'config': config.model_dump(), 'simulationDurationSeconds': max(config.horizonSeconds, max((e['timestampSeconds'] for e in events), default=0)),
        'routingIdentities': identities, 'vehicles': [v.model_dump(mode='json') for v in initial],
        'bookings': [b.model_dump(mode='json') for b in demand], 'assignments': assignments,
        'events': events, 'routes': routes, 'timelines': timelines, 'metrics': metrics,
        'counts': {'requested': len(demand), 'assigned': len(assignments),
                   'completed': sum(e['type'] == 'TRIP_COMPLETED' for e in events),
                   'unserved': sum(e['type'] == 'BOOKING_UNSERVED' for e in events), 'pending': 0, 'activeTrips': 0},
        'assumptions': {'demandVersion': 'm3-demand/v1', 'dispatchVersion': 'grid-fifo/v1',
            'shortlist': {'initial': config.initialCandidates, 'maximum': config.maxCandidates, 'cellDegrees': config.gridCellDegrees},
            'heuristic': 'First feasible expansion; ETA minimum only within that expansion, not global optimum',
            'sameTimestamp': 'completion,schedule,arrival,pickup,FIFO dispatch,inclusive expiration',
            'offlineSchedule': 'Busy vehicles complete current service before going offline',
            'travel': 'OSRM static duration; constant distance progress; synthetic demand; no traffic observations'}}
    validate_result(result)
    return result


def validate_result(result):
    """Independent linear lifecycle/accounting audit, run before final publication."""
    assignments, last_end, assigned = {}, {}, set()
    vehicles = {v['id']: v for v in result['vehicles']}
    bookings = {b['id']: b for b in result['bookings']}
    idle_consumed = {}
    for vid, timeline in result['timelines'].items():
        for i, state in enumerate(timeline):
            if state['state'] == 'ASSIGNED':
                key = (vid, state['bookingId'])
                if key in idle_consumed or i == 0 or timeline[i-1]['state'] != 'IDLE':
                    raise ValueError('Assignment consumed a non-idle/offline vehicle')
                idle_consumed[key] = timeline[i-1]['position']
    for a in result['assignments']:
        bid, vid = a['bookingId'], a['vehicleId']
        b = bookings[bid]
        if bid in assigned or vehicles[vid]['vehicleType'] != b['serviceType']:
            raise ValueError('Double/cross-mode assignment')
        if a['assignedAtSeconds'] < max(b['requestTimeSeconds'], last_end.get(vid, 0)):
            raise ValueError('Vehicle overlap/request causality violation')
        if a['pickupAtSeconds'] > b['requestTimeSeconds']+result['config']['maxWaitSeconds']:
            raise ValueError('Pickup exceeded inclusive deadline')
        pickup = result['routes'].get(a['pickupRouteRef'])
        trip = result['routes'][a['tripRouteRef']]
        # An assignment transition must consume an actual online/idle checkpoint.
        if (vid, bid) not in idle_consumed:
            raise ValueError('Assignment consumed a non-idle/offline vehicle')
        previous = idle_consumed[vid, bid]
        if pickup is None:
            if a['pickupRouteRef'] is not None or meters(previous, trip['coordinates'][0]) >= .1:
                raise ValueError('Null pickup without valid stationary position')
        elif meters(previous, pickup['coordinates'][0]) > 1 or meters(pickup['coordinates'][-1], trip['coordinates'][0]) > 1:
            raise ValueError('Discontinuous assignment route')
        for route in (pickup, trip):
            if route and (route['runId'] != result['runId'] or route['routingIdentity'] != result['routingIdentities'][a['vehicleType']]):
                raise ValueError('Routing evidence identity mismatch')
        if abs(a['pickupAtSeconds']-a['assignedAtSeconds']-(pickup['duration'] if pickup else 0)) > 1e-6 or abs(a['dropoffAtSeconds']-a['pickupAtSeconds']-trip['duration']) > 1e-6:
            raise ValueError('Routing/time inconsistency')
        assigned.add(bid)
        assignments[bid] = a
        last_end[vid] = a['dropoffAtSeconds']
    history, event_ids, previous = {}, set(), -1
    allowed = {'BOOKING_REQUESTED': None, 'BOOKING_ASSIGNED': 'BOOKING_REQUESTED',
        'VEHICLE_ARRIVED_PICKUP': 'BOOKING_ASSIGNED', 'TRIP_STARTED': 'VEHICLE_ARRIVED_PICKUP',
        'TRIP_COMPLETED': 'TRIP_STARTED', 'BOOKING_UNSERVED': 'BOOKING_REQUESTED'}
    for e in result['events']:
        if e['id'] in event_ids or e['timestampSeconds'] < previous:
            raise ValueError('Non-monotonic or duplicate event')
        event_ids.add(e['id'])
        previous = e['timestampSeconds']
        if e['type'] in allowed:
            bid = e['bookingId']
            if history.get(bid) != allowed[e['type']]:
                raise ValueError('Invalid booking lifecycle')
            if e['type'] == 'BOOKING_REQUESTED':
                expected_time = bookings[bid]['requestTimeSeconds']
            elif e['type'] == 'BOOKING_UNSERVED':
                expected_time = bookings[bid]['requestTimeSeconds']+result['config']['maxWaitSeconds']
                if not e['payload'].get('failureReason'):
                    raise ValueError('Missing unserved reason')
            else:
                a = assignments[bid]
                expected_time = a[{'BOOKING_ASSIGNED': 'assignedAtSeconds', 'VEHICLE_ARRIVED_PICKUP': 'pickupAtSeconds',
                    'TRIP_STARTED': 'pickupAtSeconds', 'TRIP_COMPLETED': 'dropoffAtSeconds'}[e['type']]]
                if e['vehicleId'] != a['vehicleId']:
                    raise ValueError('Event vehicle mismatch')
            if abs(e['timestampSeconds']-expected_time) > 1e-6:
                raise ValueError('Lifecycle event time mismatch')
            history[bid] = e['type']
    if len(history) != len(bookings) or any(t not in ('TRIP_COMPLETED', 'BOOKING_UNSERVED') for t in history.values()):
        raise ValueError('Partial result cannot be final')
    completed = sum(t == 'TRIP_COMPLETED' for t in history.values())
    if result['counts'] != {'requested': len(bookings), 'assigned': len(assignments), 'completed': completed,
        'unserved': len(bookings)-completed, 'pending': 0, 'activeTrips': 0}:
        raise ValueError('Result KPI conservation mismatch')
    for v in result['vehicles']:
        previous_end = 0
        for t in result['timelines'][v['id']]:
            if t['state'] not in STATES or t['time'] < previous_end:
                raise ValueError('Invalid vehicle timeline')
            previous_end = t['time']
    return True


def snapshot(result, time_seconds):
    if not math.isfinite(time_seconds) or time_seconds < 0:
        raise ValueError('Expected nonnegative finite simulation time')
    now = min(time_seconds, result['simulationDurationSeconds'])
    counts = dict(total=len(result['vehicles']), offline=0, online=0, idle=0, assigned=0, onTrip=0, moving=0)
    features = []
    for vehicle in result['vehicles']:
        timeline = result['timelines'][vehicle['id']]
        # bisect key avoids rebuilding an event history/checkpoint array on every poll.
        index = bisect_right(timeline, now, key=lambda x: x['time'])-1
        state = timeline[max(0, index)]
        position, heading = list(state['position']), 0.
        ref = state['routeRef']
        if ref:
            route = result['routes'][ref]
            duration = state['endTime']-state['time']
            fraction = min(1., max(0., (now-state['time'])/duration)) if duration else 1.
            cumulative = route['cumulativeMeters']
            distance = cumulative[-1]*fraction
            i = min(len(cumulative)-2, max(0, bisect_right(cumulative, distance)-1))
            a, b = route['coordinates'][i:i+2]
            length = cumulative[i+1]-cumulative[i]
            f = (distance-cumulative[i])/length if length else 0.
            position = [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f]
            heading = math.degrees(math.atan2((b[0]-a[0])*math.cos(math.radians(a[1])), b[1]-a[1])) % 360
            if fraction < 1 and cumulative[-1] > .1:
                counts['moving'] += 1
        state_key = {'OFFLINE': 'offline', 'IDLE': 'idle', 'ASSIGNED': 'assigned', 'ON_TRIP': 'onTrip'}[state['state']]
        counts[state_key] += 1
        features.append({'id': vehicle['id'], 'vehicleType': vehicle['vehicleType'], 'serviceState': state['state'],
            'position': position, 'headingDegrees': heading, 'activeBookingId': state['bookingId'], 'routeRef': ref})
    counts['online'] = counts['idle']+counts['assigned']+counts['onTrip']
    if counts['total'] != counts['offline']+counts['online']:
        raise ValueError('Fleet accounting violation')
    return {'schemaVersion': 'gsm-simulation-snapshot/v1', 'runId': result['runId'], 'regionId': result['regionId'],
        'sequenceNumber': math.floor(now*1000000), 'simulationTimeSeconds': now, 'counts': counts,
        'vehicles': features, 'routingIdentities': result['routingIdentities']}
