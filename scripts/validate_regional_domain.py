"""Explicit domain-only regional scale fixture; no OSRM, GIS or browser claims.

Reuses the frozen synthetic M3 directed-ring travel matrices independently in
each regional context. Coordinates are fixture coordinates, not coverage proof.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.regional_simulation import (REGION_IDS, RegionalScenarioConfig,
    active_modes, regional_inputs, regional_snapshot, simulate_regional)
from backend.app.simulation import validate_result
from backend.app.simulation_jobs import JobStore, atomic_json
from backend.app.simulation_resources import require_simulation_headroom
from backend.app.simulation_worker import run_claimed
from scripts.m3_fixture_travel import RecordedTravel, fixture_identities, load_fixture
from scripts.m3_resources import Monitor, memory
from scripts.validate_regional_api import audit_aggregates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--total-fleet', type=int, default=5000)
    parser.add_argument('--total-bookings', type=int, default=1000)
    parser.add_argument('--horizon', type=int, default=900)
    parser.add_argument('--seed', default='r1a-domain-scale/v1')
    parser.add_argument('--store', type=Path, default=ROOT/'build/r1a/domain-jobs')
    parser.add_argument('--output', type=Path, default=ROOT/'build/r1a/regional-domain-5000.json')
    args = parser.parse_args()
    sizes = [args.total_fleet//2, args.total_fleet-args.total_fleet//2]
    bookings = [args.total_bookings//2, args.total_bookings-args.total_bookings//2]
    cfg = RegionalScenarioConfig(seed=args.seed, horizonSeconds=args.horizon,
        regions=[{'regionId': region, 'fleetSize': fleet, 'carCount': fleet*2//5,
            'bookingCount': count, 'onlineFraction': .8}
            for region, fleet, count in zip(REGION_IDS, sizes, bookings)])
    report = {'status': 'FAIL', 'scope': 'DOMAIN ONLY: frozen synthetic directed-ring matrices; no local OSRM requests',
        'config': cfg.model_dump(mode='json'), 'resourcesBefore': memory(),
        'limitations': ['No GIS/OSRM graph or routing throughput verification',
            'No browser/WebGL performance or UI rendering verification',
            'Synthetic fleet/demand and fixture geometry are not observed GSM operations or geographic coverage',
            'One bounded workload; not maximum retained history or all 20000-booking schedules']}
    try:
        report['admission'] = require_simulation_headroom(cfg)
        store = JobStore(args.store)
        # Own the ordinary worker lease: never process another runtime's queue.
        from backend.app.simulation_jobs import file_lock
        with file_lock(store.root/'.worker.lock', blocking=False):
            if any(status['status'] not in ('COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED') for status in store.statuses()):
                raise ValueError('Domain evidence store already contains unfinished work; preserve and inspect it first')
            queued = store.create(cfg)
            report['jobId'] = queued['id']
            async def execute(config, run_id, cancelled, progress, save):
                prepared = {}
                for allocation in config.regions:
                    vehicles, demand = regional_inputs(config, allocation, load_fixture()['anchors'])
                    prepared[allocation.regionId] = {'vehicles': vehicles, 'bookings': demand,
                        'travels': {mode: RecordedTravel(mode) for mode in active_modes(allocation)},
                        'identities': {mode: {**identity, 'regionId': allocation.regionId}
                            for mode, identity in fixture_identities().items() if mode in active_modes(allocation)},
                        'provenance': {'syntheticFixture': True, 'source': 'tests/fixtures/m3/travel-matrix.json'}}
                save({'schemaVersion': 'gsm-nvmr-regional-domain-fixture/v1', 'runId': run_id,
                    'config': config.model_dump(mode='json'), 'syntheticFixture': True})
                return await simulate_regional(config, prepared, run_id, cancelled, progress)
            with Monitor() as monitor:
                status = asyncio.run(run_claimed(store, store.claim(), execute))
                if status['status'] != 'COMPLETED':
                    raise ValueError(f'Domain job failed: {status}')
                # Reopen a new store instance to audit actual persisted publication.
                result = JobStore(args.store).result(queued['id'])
                for region in result['regions']:
                    validate_result(region)
                audit_aggregates(result)
                snapshots = []
                for time in (0., result['simulationDurationSeconds']/2, result['simulationDurationSeconds']):
                    snapshot = regional_snapshot(result, time)
                    counts = snapshot['counts']
                    if counts['total'] != cfg.fleetSize or counts['total'] != counts['offline']+counts['online'] or counts['online'] != counts['idle']+counts['assigned']+counts['onTrip']:
                        raise ValueError('Common-time fleet/state conservation failure')
                    if any(region['simulationTimeSeconds'] != snapshot['simulationTimeSeconds'] for region in snapshot['regions']):
                        raise ValueError('Common clock failure')
                    snapshots.append({'timeSeconds': time, 'counts': counts})
                vehicle_ids = [vehicle['id'] for region in result['regions'] for vehicle in region['vehicles']]
                booking_ids = [booking['id'] for region in result['regions'] for booking in region['bookings']]
                if len(set(vehicle_ids)) != cfg.fleetSize or len(set(booking_ids)) != cfg.bookingCount:
                    raise ValueError('Global identity collision')
                raw = json.dumps(result, sort_keys=True, separators=(',', ':')).encode()
                report.update(status='PASS', counts=result['counts'], globalTotals=result['globalTotals'],
                    kpis=result['kpis'], routingIdentities=result['routingIdentities'],
                    simulationDurationSeconds=result['simulationDurationSeconds'],
                    snapshots=snapshots, resultBytes=(store.path(queued['id'])/'result.json').stat().st_size,
                    resultSha256=hashlib.sha256(raw).hexdigest(),
                    perRegion=[{'regionId': region['regionId'], 'counts': region['counts'],
                        'eventCount': len(region['events']), 'routeCount': len(region['routes'])} for region in result['regions']])
            report['resources'] = monitor.result()
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        report['resourcesAfter'] = memory()
        atomic_json(args.output, report)
    print(json.dumps({'status': report['status'], 'jobId': report.get('jobId'), 'output': str(args.output),
                      'error': report.get('error')}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
