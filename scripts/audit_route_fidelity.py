"""Read-only, independent metric audit of immutable completed M3 runs.

No router calls, no result writes. Projection oracle is deliberately separate from
simulation.snapshot: haversine lengths + local metric point/segment projection.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.simulation import snapshot

R = 6371008.8
TOLERANCE_METERS = .02  # Full GeoJSON, same coordinate grid; 2 cm covers FP projection error, not GPS accuracy.


def arc(a, b):
    x, y = map(math.radians, (a[1], b[1]))
    return 2*R*math.asin(min(1, math.sqrt(math.sin((y-x)/2)**2 +
        math.cos(x)*math.cos(y)*math.sin(math.radians(b[0]-a[0])/2)**2)))


def locate(point, coords):
    scale = math.cos(math.radians(point[1]))
    def xy(p):
        return (R*math.radians(p[0]-point[0])*scale, R*math.radians(p[1]-point[1]))
    best = (float('inf'), 0., 0, 0.)
    cumulative = 0.
    for i, (a, b) in enumerate(zip(coords, coords[1:])):
        ax, ay = xy(a); bx, by = xy(b)
        dx, dy = bx-ax, by-ay
        u = max(0., min(1., -(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx or dy else 0.
        deviation = math.hypot(ax+u*dx, ay+u*dy)
        length = arc(a, b)
        if deviation < best[0]:
            best = (deviation, cumulative+u*length, i, u)
        cumulative += length
    return best, cumulative


def audit(result, limit=40):
    assignments = result['assignments']
    # Keep a mix of types, nonstationary pickups, and reused vehicles.
    chosen = sorted(assignments, key=lambda a: (a['vehicleType'], a['pickupRouteRef'] is None, a['assignedAtSeconds']))
    per_mode = max(1, limit//2)
    chosen = [a for mode in ('CAR', 'MOTORBIKE') for a in [x for x in chosen if x['vehicleType']==mode][:per_mode]]
    rows, failures, transitions = [], [], []
    for a in chosen:
        vid = a['vehicleId']
        for leg, begin, end, ref in (
            ('pickup', a['assignedAtSeconds'], a['pickupAtSeconds'], a['pickupRouteRef']),
            ('trip', a['pickupAtSeconds'], a['dropoffAtSeconds'], a['tripRouteRef'])):
            if not ref:
                continue
            route = result['routes'][ref]
            previous_along = -1.
            for f in (0, .001, .1, .25, .5, .75, .9, .999):
                t = begin + (end-begin)*f
                v = next(v for v in snapshot(result, t)['vehicles'] if v['id']==vid)
                # Zero-duration phases have no observable active interval.
                if t >= end:
                    continue
                nearest, length = locate(v['position'], route['coordinates'])
                deviation, along, segment, segment_fraction = nearest
                row = dict(vehicleId=vid, vehicleType=a['vehicleType'], bookingId=a['bookingId'],
                    simulationTimeSeconds=t, state=v['serviceState'], activeLeg=leg, routeRef=ref,
                    routingIdentity=route['routingIdentity'], position=v['position'],
                    deviationMeters=deviation, segment=segment, segmentFraction=segment_fraction,
                    timeProgress=f, alongMeters=along, polylineMeters=length)
                rows.append(row)
                if (deviation > TOLERANCE_METERS or v['routeRef'] != ref or v['activeBookingId'] != a['bookingId'] or
                    v['serviceState'] != ('ASSIGNED' if leg=='pickup' else 'ON_TRIP') or
                    route['routingIdentity'] != result['routingIdentities'][a['vehicleType']] or
                    abs(along-length*f) > TOLERANCE_METERS or along+.02 < previous_along):
                    failures.append(row)
                previous_along = along
        for label, t in [('before', max(0, a['assignedAtSeconds']-1e-6)),
                         ('assignment', a['assignedAtSeconds']), ('pickup', a['pickupAtSeconds']),
                         ('complete', a['dropoffAtSeconds'])]:
            v = next(v for v in snapshot(result,t)['vehicles'] if v['id']==vid)
            transitions.append(dict(checkpoint=label, time=t, expectedBooking=a['bookingId'], **v))
            # At completion same-time reuse may already assign the next booking.
            if label=='complete' and v['activeBookingId']==a['bookingId']:
                failures.append({'transition': transitions[-1]})
    # Seek determinism is stateless, including returning from another booking.
    times = [r['simulationTimeSeconds'] for r in rows[:8]]
    forward = [snapshot(result,t) for t in times]
    reverse = list(reversed([snapshot(result,t) for t in reversed(times)]))
    if forward != reverse:
        failures.append({'seek':'Forward/reverse mismatch'})
    return dict(schemaVersion='gsm-route-fidelity-audit/v1', runId=result['runId'], config=result['config'],
        toleranceMeters=TOLERANCE_METERS, method='Haversine lengths; query-centered equirectangular segment distance; independent of cumulativeMeters',
        toleranceReason='2 cm numeric allowance for full GeoJSON coordinates; not an allowance for road snapping/GPS error',
        sampledAssignments=len(chosen), samples=len(rows), modes=dict(Counter(r['vehicleType'] for r in rows)),
        stationaryPickups=sum(a['pickupRouteRef'] is None for a in assignments),
        reusedVehicles=sum(n>1 for n in Counter(a['vehicleId'] for a in assignments).values()),
        maxDeviationMeters=max((r['deviationMeters'] for r in rows), default=0),
        seekDeterministic=forward==reverse, violations=failures, passed=not failures,
        scope='Stored OSRM geometry fidelity, not an independent legal/OSM topology certification',
        sampledRoutes={ref:{k:v for k,v in result['routes'][ref].items() if k!='cumulativeMeters'}
                       for ref in sorted({r['routeRef'] for r in rows})},
        rows=rows, transitions=transitions)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--job-dir', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--limit', type=int, default=40)
    args=p.parse_args()
    if json.loads((args.job_dir/'status.json').read_text())['status']!='COMPLETED':
        raise SystemExit('Audit requires a completed immutable job')
    report=audit(json.loads((args.job_dir/'result.json').read_text(encoding='utf-8')),args.limit)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','transitions','violations','sampledRoutes')}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':
    main()
