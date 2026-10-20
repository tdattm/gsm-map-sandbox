"""Read-only fleet counts at persisted state-transition timestamps; no geometry."""
from itertools import groupby
import math


STATES = ('OFFLINE', 'IDLE', 'ASSIGNED', 'ON_TRIP')


def fleet_state_series(result, limit=120):
    fleet_size = result['config']['fleetSize']
    duration = result['simulationDurationSeconds']
    vehicles = result.get('vehicles', [])
    timelines = result.get('timelines', {})
    if (not isinstance(fleet_size, int) or fleet_size < 1 or
            not math.isfinite(duration) or duration < 0 or len(vehicles) != fleet_size or
            len({v['id'] for v in vehicles}) != fleet_size):
        raise ValueError('Invalid fleet identity or duration')
    changes = []
    for vehicle in vehicles:
        timeline = timelines.get(vehicle['id'])
        if not timeline or timeline[0]['time'] != 0:
            raise ValueError('Missing initial vehicle state')
        previous_time = -1
        previous_state = None
        for entry in timeline:
            at, state = entry['time'], entry['state']
            if (not math.isfinite(at) or at < previous_time or at < 0 or
                    at > duration or state not in STATES):
                raise ValueError('Invalid vehicle timeline')
            # Same-time entries retain original order, as bisect_right in snapshot.
            changes.append((at, previous_state, state))
            previous_time, previous_state = at, state
    changes.sort(key=lambda entry: entry[0])
    counts = dict.fromkeys(STATES, 0)
    points = []
    for at, group in groupby(changes, key=lambda entry: entry[0]):
        for _, before, after in group:
            if before is not None:
                counts[before] -= 1
            counts[after] += 1
        if sum(counts.values()) != fleet_size or min(counts.values()) < 0:
            raise ValueError('Fleet state conservation failed')
        points.append({'timeSeconds': at, **counts})
    if points[-1]['timeSeconds'] != duration:
        points.append({'timeSeconds': duration, **counts})
    original_count = len(points)
    if original_count > limit:
        # Select real checkpoints, including both endpoints; never interpolate states.
        points = [points[round(i * (original_count - 1) / (limit - 1))] for i in range(limit)]
    return {'runId': result['runId'], 'fleetSize': fleet_size,
            'durationSeconds': duration, 'transitionPointCount': original_count,
            'sampled': original_count > limit, 'points': points}


def fleet_state_buckets(result, limit=120):
    """Exact vehicle-seconds over equal half-open intervals, using ALL transitions.

    Fractions are average concurrent vehicles, never instantaneous synthetic states.
    An endpoint change has zero measure. The original checkpoint API stays intact.
    """
    series = fleet_state_series(result, limit=sum(map(len, result['timelines'].values())) + 2)
    duration = series['durationSeconds']
    if duration <= 0:
        raise ValueError('Time-weighted chart requires positive duration')
    points, rows, index = series['points'], [], 0
    for bucket in range(limit):
        start, end = duration * bucket / limit, duration * (bucket + 1) / limit
        cursor, area = start, dict.fromkeys(STATES, 0.)
        while index + 1 < len(points) and points[index + 1]['timeSeconds'] <= start:
            index += 1
        while cursor < end:
            boundary = min(end, points[index + 1]['timeSeconds'] if index + 1 < len(points) else end)
            for state in STATES:
                area[state] += points[index][state] * (boundary - cursor)
            cursor = boundary
            if index + 1 < len(points) and points[index + 1]['timeSeconds'] <= cursor:
                index += 1
        rows.append({'timeSeconds': start, 'endSeconds': end,
                     **{state: area[state] / (end - start) for state in STATES}})
    # Duplicate the final bucket at its end to terminate the step area accurately.
    return {**series, 'aggregation': 'time-weighted-mean/v1', 'sampled': False,
            'bucketCount': limit, 'points': rows + [{**rows[-1], 'timeSeconds': duration}]}
