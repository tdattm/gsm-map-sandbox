"""Audit real road-derived Connected inputs OFFLINE, without executing simulation.

No OSRM requests, synthetic travel adapters, or completed-run performance claims.
Run after graph/anchor artifacts have passed their independent GIS validation:
python -m scripts.validate_connected_inputs
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from backend.app.config import PROJECT_ROOT
from backend.app.connected_context import connected_context
from backend.app.connected_jobs import read_anchor_catalog, verify_routing_validation
from backend.app.connected_simulation import (ConnectedScenarioConfig, ZONE_IDS,
    connected_inputs, distribution_quality, load_zones, zone_at)
from backend.app.integrity import digest
from backend.app.modes import routing_identity
from backend.app.simulation_jobs import atomic_json
from scripts.m3_resources import memory


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def serialized_inputs(vehicles, bookings, vmeta, bmeta):
    return {'vehicles': [{**v.model_dump(mode='json'), **vmeta[v.id]} for v in vehicles],
            'bookings': [{**b.model_dump(mode='json'), **bmeta[b.id]} for b in bookings]}


def run(args):
    report = {'schemaVersion': 'connected-real-road-input-audit/v1', 'status': 'PARTIAL',
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'evidenceType': 'OFFLINE REAL ROAD INPUT PREPARATION ONLY; not simulation or live OSRM benchmark',
        'routingCalls': {'nearest': 0, 'table': 0, 'route': 0},
        'limitations': ['No vehicle lifecycle, dispatch, booking outcomes, or completed replay is exercised.',
            'Geographic nearest-neighbor distances describe initial distribution, not road travel.',
            'Operating zones are versioned technical rectangles, not administrative polygons.',
            'Graph byte integrity must be independently checked by the GIS verify command; this audit binds current graph manifests and validation proofs.'],
        'scales': []}
    try:
        identities = {}
        for mode in ('CAR', 'MOTORBIKE'):
            context = connected_context(mode)
            identities[mode] = routing_identity(context)
            verify_routing_validation(context, identities[mode])
        begun = time.perf_counter()
        pools, provenance = read_anchor_catalog(identities)
        assert provenance['preSnapped'], 'Real input audit requires a verified snapped catalog'
        report['catalogLoadSeconds'] = time.perf_counter()-begun
        report['routingIdentities'] = identities
        report['provenance'] = provenance
        report['sourceSha256'] = {name: digest(PROJECT_ROOT/name) for name in (
            'scripts/validate_connected_inputs.py', 'backend/app/connected_simulation.py',
            'backend/app/connected_jobs.py', 'config/connected-nvmr.json')}
        zones = load_zones()
        allowed = {mode: {tuple(p) for p in points} for mode, points in pools.items()}
        report['catalogUniquePositionsByMode'] = {mode: len(points) for mode, points in allowed.items()}
        reference_demand_hash = None
        for size in (100, 500, 1000, 5000):
            config = ConnectedScenarioConfig(fleetSize=size, carCount=size*2//5,
                bookingCount=100, seed=args.seed, horizonSeconds=900)
            memory_before = memory()
            begun = time.perf_counter()
            vehicles, bookings, vmeta, bmeta = connected_inputs(config, pools, zones)
            preparation_seconds = time.perf_counter()-begun
            payload = serialized_inputs(vehicles, bookings, vmeta, bmeta)
            assert len(vehicles) == size
            assert len({v.id for v in vehicles}) == size
            assert len({tuple(v.position) for v in vehicles}) == size
            assert Counter(v.vehicleType for v in vehicles) == {'CAR': size*2//5, 'MOTORBIKE': size*3//5}
            actual = Counter((vmeta[v.id]['homeZoneId'], v.vehicleType) for v in vehicles)
            for allocation in config.fleetAllocations:
                assert actual[allocation.zoneId, 'CAR'] == allocation.carCount
                assert actual[allocation.zoneId, 'MOTORBIKE'] == allocation.motorbikeCount
            for vehicle in vehicles:
                assert tuple(vehicle.position) in allowed[vehicle.vehicleType]
                assert zone_at(vehicle.position, zones) == vmeta[vehicle.id]['homeZoneId']
            for booking in bookings:
                assert tuple(booking.pickup) in allowed[booking.serviceType]
                assert tuple(booking.dropoff) in allowed[booking.serviceType]
                assert booking.pickup != booking.dropoff
            demand_hash = canonical_hash(payload['bookings'])
            if reference_demand_hash is None:
                reference_demand_hash = demand_hash
            assert demand_hash == reference_demand_hash, 'Fleet changes must not change exogenous demand'
            begun = time.perf_counter()
            quality = distribution_quality(vehicles, vmeta, config.distribution)
            quality_seconds = time.perf_counter()-begun
            entry = {'fleetSize': size, 'bookingCount': len(bookings),
                'inputPreparationWallSeconds': preparation_seconds,
                'distributionQualityWallSeconds': quality_seconds,
                'peakProcessRssBytes': memory()['processPeakRssBytes'],
                'peakRssScope': 'Process lifetime high-water mark; all scales run sequentially in the same process; includes catalog load and imports',
                'systemMemoryBefore': memory_before, 'systemMemoryAfter': memory(),
                'demandHash': demand_hash, 'initialInputHash': canonical_hash(payload),
                'checks': {'exactAllocation': 'PASS', 'modeConservation': 'PASS',
                    'globalIdUniqueness': 'PASS', 'modeRoadMembership': 'PASS',
                    'homeZoneMembership': 'PASS', 'uniqueSnappedPositions': 'PASS',
                    'demandIndependentOfFleetSize': 'PASS'}, 'distributionQuality': quality}
            report['scales'].append(entry)
            if size == 5000:
                assert quality['byZone'] == {zone: {'CAR': 1600 if zone == 'hanoi' else 100,
                    'MOTORBIKE': 2400 if zone == 'hanoi' else 150} for zone in ZONE_IDS}
                begun = time.perf_counter()
                repeated = serialized_inputs(*connected_inputs(config, pools, zones))
                assert repeated == payload, 'Same-seed input generation changed'
                entry['sameSeedRepeatWallSeconds'] = time.perf_counter()-begun
                entry['checks']['sameSeedFullInputRepeat'] = 'PASS'
                initial = {'schemaVersion': 'gsm-nvmr-connected-input/v1',
                    'evidenceType': report['evidenceType'], 'runId': 'offline-road-input-audit-5000',
                    'config': config.model_dump(mode='json'), 'routingIdentities': identities,
                    'operatingZones': zones, 'provenance': provenance, **payload}
                atomic_json(args.initial_output, initial)
                report['persistedInitialInputs'] = {'path': str(args.initial_output),
                    'sha256': digest(args.initial_output), 'bytes': args.initial_output.stat().st_size}
            atomic_json(args.output, report)
            print(json.dumps({'fleetSize': size, 'inputPreparationWallSeconds': preparation_seconds,
                'uniquePositions': quality['uniqueSnappedPositions'], 'occupiedCells': quality['occupiedCells'],
                'peakProcessRssBytes': entry['peakProcessRssBytes']}), flush=True)
        report['status'] = 'PASS'
        report['finishedAt'] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        report.update(status='FAIL', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        atomic_json(args.output, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('docs/nvmr/r1b-evidence/real-road-inputs.json'))
    parser.add_argument('--initial-output', type=Path, default=Path('build/r1b/real-road-initial-5000.json'))
    parser.add_argument('--seed', default='connected-real-road-inputs/v1')
    run(parser.parse_args())
