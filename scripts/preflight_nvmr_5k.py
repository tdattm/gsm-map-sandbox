"""D2a read-only offline preparation. Never executes simulation, HTTP or JobStore mutations.

Only --output is written. Local telemetry/paths belong in ignored build/, not Git.
Reuses Connected input generation, GIS integrity cache and production admission policy.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

from backend.app.config import PROJECT_ROOT
from backend.app.connected_context import connected_context
from backend.app.connected_jobs import read_anchor_catalog, verify_routing_validation
from backend.app.connected_simulation import (ConnectedScenarioConfig, ZONE_IDS,
    connected_inputs, connected_kpis, connected_snapshot, distribution_quality,
    integer_allocation, load_zones, stratified_positions, validate_connected_result, zone_at)
from backend.app.connected_analytics import fleet_state_series
from backend.app.integrity import digest
from backend.app.modes import routing_identity
from backend.app.simulation_jobs import atomic_json
from backend.app.simulation_resources import admission_policy, resource_decision
from scripts.m3_resources import memory
from scripts.validate_connected_inputs import canonical_hash, serialized_inputs

PRESET_ID = 'nvmr-connected-5k-hanoi-centric-v1'
PRESET = PROJECT_ROOT/'config/scenarios'/f'{PRESET_ID}.json'
MANIFEST = PRESET.with_suffix('.manifest.json')
DEMAND = dict(zip(ZONE_IDS, (1050, 175, 175, 175, 175)))
FLEET = {z: {'CAR': 1400 if z == 'hanoi' else 150,
             'MOTORBIKE': 2100 if z == 'hanoi' else 225} for z in ZONE_IDS}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_preset(path=PRESET, manifest_path=MANIFEST):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    config = ConnectedScenarioConfig.model_validate(raw)
    schema = json.loads((PROJECT_ROOT/'contracts/nvmr/connected-scenario-v1.schema.json').read_text())
    require(schema == ConnectedScenarioConfig.model_json_schema(), 'Generated JSON Schema drift')
    require(set(raw) == set(config.model_dump()), 'Preset must explicitly pin every request field')
    require((config.fleetSize, config.carCount, config.bookingCount) == (5000, 2000, 1750), 'Wrong D2a scale')
    require(raw['fleetAllocations'] is not None, 'Explicit fleet allocation required')
    actual = {a.zoneId: {'CAR': a.carCount, 'MOTORBIKE': a.motorbikeCount} for a in config.fleetAllocations}
    require(actual == FLEET, 'Wrong D2a fleet allocation')
    require(config.demandWeights == dict(zip(ZONE_IDS, (6, 1, 1, 1, 1))), 'Wrong demand weights')
    require(integer_allocation(config.bookingCount, config.demandWeights) == DEMAND, 'Wrong demand allocation')
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    require(manifest['presetId'] == PRESET_ID and manifest['version'] == 1, 'Wrong preset identity/version')
    require(manifest['presetSha256'] == digest(path), 'Preset changed: immutable version checksum mismatch')
    for name in ('regionConfig', 'inputGenerator'):
        require(manifest['provenance'][name+'Sha256'] == digest(PROJECT_ROOT/manifest['provenance'][name]),
                f'Preset provenance drift: {name}')
    return config, {'status': 'PASS', 'presetId': PRESET_ID, 'version': 1,
        'seed': config.seed, 'presetSha256': digest(path), 'fleetAllocations': actual,
        'demandAllocations': DEMAND, 'schemaComparison': 'Pydantic generated schema equals checked-in schema; request validated by Pydantic'}


def occupancy(points, cell_degrees):
    coordinates = Counter(tuple(p) for p in points)
    cells = Counter(tuple(math.floor(v/cell_degrees) for v in p) for p in points)
    return {'count': len(points), 'uniqueCoordinates': len(coordinates),
        'duplicateOccurrences': len(points)-len(coordinates),
        'maximumPerCoordinate': max(coordinates.values(), default=0),
        'occupiedCells': len(cells), 'maximumPerCell': max(cells.values(), default=0),
        'top10CellShare': sum(n for _, n in cells.most_common(10))/max(1, len(points)),
        'topCoordinates': [{'coordinate': list(p), 'count': n} for p, n in coordinates.most_common(5)],
        'topCells': [{'cell': list(p), 'count': n} for p, n in cells.most_common(10)]}


def capacity(config, pools, zones):
    """Exact sequential mode capacity including shared coordinates, same sampler/order as engine."""
    used, rows = Counter(), []
    for allocation in config.fleetAllocations:
        for mode, count in (('CAR', allocation.carCount), ('MOTORBIKE', allocation.motorbikeCount)):
            points = {tuple(p) for p in pools.get(mode, []) if zone_at(p, zones) == allocation.zoneId}
            free = sum(max(0, config.distribution.maximumVehiclesPerPosition-used[p]) for p in points)
            rows.append({'zoneId': allocation.zoneId, 'mode': mode, 'uniqueCatalogPositions': len(points),
                'availableSlotsAfterPriorMode': free, 'required': count, 'shortfall': max(0, count-free)})
            if free >= count:
                used.update(stratified_positions(points, count, config.distribution, config.seed,
                    f'fleet:{allocation.zoneId}:{mode}', used))
    return rows


def input_diagnostics(config, pools, zones):
    rows = capacity(config, pools, zones)
    require(not any(r['shortfall'] for r in rows), f'Insufficient verified anchors: {rows}')
    vehicles, bookings, vm, bm = connected_inputs(config, pools, zones)
    require(len(vehicles) == 5000 and len({v.id for v in vehicles}) == 5000, 'Vehicle count/IDs')
    require(len(bookings) == 1750 and len({b.id for b in bookings}) == 1750, 'Booking count/IDs')
    require(Counter(v.vehicleType for v in vehicles) == {'CAR': 2000, 'MOTORBIKE': 3000}, 'Fleet modes')
    allowed = {m: {tuple(p) for p in points} for m, points in pools.items()}
    for v in vehicles:
        require(tuple(v.position) in allowed[v.vehicleType], 'Vehicle coordinate not in mode catalog')
        require(zone_at(v.position, zones) == vm[v.id]['homeZoneId'], 'Vehicle zone attribution')
    for b in bookings:
        require(tuple(b.pickup) in allowed[b.serviceType] and tuple(b.dropoff) in allowed[b.serviceType], 'Booking not in mode catalog')
        require(b.pickup != b.dropoff, 'Identical booking endpoints')
        require(zone_at(b.pickup, zones) == bm[b.id]['pickupZoneId'] and
                zone_at(b.dropoff, zones) == bm[b.id]['dropoffZoneId'], 'Booking zone attribution')
        require(0 <= b.requestTimeSeconds <= config.horizonSeconds, 'Timestamp outside horizon')
    quality = distribution_quality(vehicles, vm, config.distribution)
    require(quality['byZone'] == FLEET, 'Fleet zone/mode totals')
    require(quality['maximumVehiclesPerPosition'] <= config.distribution.maximumVehiclesPerPosition, 'Global coordinate capacity')
    require(Counter(bm[b.id]['pickupZoneId'] for b in bookings) == DEMAND, 'Pickup zone counts')
    demand = {}
    for label, subset in [('global', bookings)]+[(z, [b for b in bookings if bm[b.id]['pickupZoneId'] == z]) for z in ZONE_IDS]:
        demand[label] = {endpoint: occupancy([getattr(b, endpoint) for b in subset], config.distribution.cellDegrees)
                         for endpoint in ('pickup', 'dropoff')}
    modes = Counter(b.serviceType for b in bookings)
    od = Counter((bm[b.id]['pickupZoneId'], bm[b.id]['dropoffZoneId']) for b in bookings)
    crossed = sum(n for (a, b), n in od.items() if a != b)
    times = [b.requestTimeSeconds for b in bookings]
    def buckets(subset, width):
        counts = Counter(min(int(b.requestTimeSeconds//width), math.ceil(config.horizonSeconds/width)-1) for b in subset)
        return [counts[i] for i in range(math.ceil(config.horizonSeconds/width))]
    temporal = {'earliestSeconds': min(times), 'latestSeconds': max(times),
        'uniqueTimestamps': len(set(times)), 'maximumAtSameTimestamp': max(Counter(times).values()),
        'oneMinuteBuckets': buckets(bookings, 60), 'fiveMinuteBuckets': buckets(bookings, 300),
        'byPickupZone': {z: {'oneMinuteBuckets': buckets([b for b in bookings if bm[b.id]['pickupZoneId'] == z], 60),
                            'fiveMinuteBuckets': buckets([b for b in bookings if bm[b.id]['pickupZoneId'] == z], 300)} for z in ZONE_IDS}}
    temporal['peakRequestsPerMinute'] = max(temporal['oneMinuteBuckets'])
    warnings = []
    # Diagnostic flags only, not business KPIs or calibrated statistical acceptance limits.
    if max(times)-min(times) < .8*config.horizonSeconds or max(Counter(times).values()) > .01*len(times):
        warnings.append('Temporal concentration: span <80% horizon or >1% at one timestamp')
    if max(temporal['oneMinuteBuckets']) > 2*len(bookings)/len(temporal['oneMinuteBuckets']):
        warnings.append('Minute peak exceeds twice uniform bucket mean')
    for zone in ZONE_IDS:
        for endpoint in ('pickup', 'dropoff'):
            stats = demand[zone][endpoint]
            if stats['occupiedCells'] < 5 or max(stats['maximumPerCoordinate'], stats['maximumPerCell']) > .1*stats['count']:
                warnings.append(f'{zone}/{endpoint}: <5 cells or >10% at one coordinate/cell')
    fleet_cells = {z: occupancy([v.position for v in vehicles if vm[v.id]['homeZoneId'] == z],
                               config.distribution.cellDegrees) for z in ZONE_IDS}
    for z, stats in fleet_cells.items():
        if stats['occupiedCells'] < 5 or stats['maximumPerCell'] > .1*stats['count']:
            warnings.append(f'{z}/fleet: <5 cells or >10% in one cell; inspect catalog geometry')
    dropoff_by_zone = {z: occupancy([b.dropoff for b in bookings if bm[b.id]['dropoffZoneId'] == z],
        config.distribution.cellDegrees) for z in ZONE_IDS}
    first_hash = canonical_hash(serialized_inputs(vehicles, bookings, vm, bm))
    del vehicles, bookings, vm, bm
    gc.collect()
    repeated = canonical_hash(serialized_inputs(*connected_inputs(config, pools, zones)))
    require(first_hash == repeated, 'Same-seed sequential input hash mismatch')
    return {'status': 'PASS', 'anchorCapacity': rows, 'fleet': quality, 'fleetByZone': fleet_cells,
        'demand': demand, 'actualDemandModes': dict(modes),
        'dropoffByDestinationZone': dropoff_by_zone,
        'actualDemandCarFraction': modes['CAR']/1750, 'actualCrossZoneCount': crossed,
        'actualCrossZoneFraction': crossed/1750,
        'odMatrix': {a: {b: od[a, b] for b in ZONE_IDS} for a in ZONE_IDS},
        'temporal': temporal, 'determinism': {'status': 'PASS', 'firstSha256': first_hash,
            'secondSha256': repeated, 'method': 'Sequential regeneration; first full input released before second'},
        'warnings': warnings}


def command_read(args):
    try:
        p = subprocess.run(args, capture_output=True, timeout=15, encoding='utf-8', errors='replace')
        return {'exitCode': p.returncode, 'stdout': p.stdout.replace('\x00', '').strip(),
                'stderr': p.stderr.replace('\x00', '').strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'WARNING', 'error': str(exc)}


def resource_report(config, store):
    readings = memory()
    result = {'memory': readings, 'diskFreeBytes': shutil.disk_usage(PROJECT_ROOT).free,
        'policy': admission_policy(), 'admission': resource_decision(config, readings),
        'store': str(store.resolve()), 'jobs': [],
        'workerLease': 'NOT_RUN: lock file presence is not lease ownership; no writable runtime probe',
        'routerRuntime': 'NOT_RUN: no OSRM calls; port/container presence does not prove graph readiness',
        'docker': command_read(['docker', 'ps', '-a', '--format', '{{json .}}'])}
    for path in sorted(store.glob('*/status.json')):
        try:
            status = json.loads(path.read_text(encoding='utf-8'))
            result['jobs'].append({k: status.get(k) for k in ('id', 'status', 'updatedAt', 'progress')})
        except (OSError, ValueError) as exc:
            result['jobs'].append({'status': 'WARNING', 'error': str(exc)})
    result['workerLockFilePresent'] = (store/'.worker.lock').is_file()
    if os.name == 'nt':
        result['wsl'] = command_read(['wsl', '--list', '--verbose'])
        result['processesAndPorts'] = command_read(['powershell', '-NoProfile', '-Command',
            "@{processes=@(Get-Process python*,vmmem*,*docker* -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,WorkingSet64,PrivateMemorySize64); ports=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -in 5005,5006,8000,8022 | Select-Object LocalAddress,LocalPort,OwningProcess)} | ConvertTo-Json -Depth 4 -Compress"])
    return result


def persistence_check(result, prepared, manifest):
    """Audit actual persisted data with existing replay/KPI validators; no executor."""
    required = ('config', 'vehicles', 'bookings', 'assignments', 'events', 'timelines', 'routes',
                'kpis', 'distributionQuality', 'routingIdentities', 'provenance',
                'operatingZones', 'simulationModelVersion', 'assumptions')
    require(all(k in result for k in required), 'Missing persisted result fields')
    require(prepared['config'] == result['config'] == manifest['config'], 'Prepared/config mismatch')
    require(manifest['inputHash'] == hashlib.sha256(json.dumps(manifest['config'], sort_keys=True).encode()).hexdigest(), 'Config inputHash mismatch')
    require([{k: v[k] for k in prepared['vehicles'][i]} for i, v in enumerate(result['vehicles'])]
            == prepared['vehicles'], 'Initial vehicle input differs')
    require(prepared['routingIdentities'] == result['routingIdentities'] and
            prepared['operatingZones'] == result['operatingZones'] and
            prepared['provenance'] == result['provenance'], 'Prepared provenance differs')
    input_fields = ('id', 'serviceType', 'requestTimeSeconds', 'pickup', 'dropoff',
                    'pickupZoneId', 'dropoffZoneId', 'potentialPassengerId')
    require([{k: b[k] for k in input_fields} for b in prepared['bookings']] ==
            [{k: b[k] for k in input_fields} for b in result['bookings']], 'Initial demand differs')
    require(all(result['provenance'].get(k) for k in ('catalogSha256', 'source', 'boundaryVersion')), 'Missing GIS provenance')
    validate_connected_result(result)
    from scripts.validate_connected_api import audit
    audit(result)  # Pure independent arithmetic only; never call live validate()/main().
    require(connected_kpis(result) == result['kpis'], 'KPI reconstruction')
    series = fleet_state_series(result)
    for point in series['points']:
        snap = connected_snapshot(result, point['timeSeconds'])
        for state, count in (('OFFLINE', 'offline'), ('IDLE', 'idle'), ('ASSIGNED', 'assigned'), ('ON_TRIP', 'onTrip')):
            require(point[state] == snap['counts'][count], 'Fleet chart vs persisted snapshot mismatch')
    return {'status': 'PASS', 'evidenceScale': {'fleetSize': result['config']['fleetSize'],
        'bookingCount': result['config']['bookingCount']}, 'fields': list(required),
        'checks': ['config hash', 'prepared input preservation', 'mode route identity/geometry invariants',
                   'independent KPI reconstruction', 'replay projection', 'fleet-state chart vs snapshot'],
        'chartCheckpoints': len(series['points']),
        'portable': 'Source fields present; copy full job directory plus compatible application/config/map artifacts. Packaging/restore exercise deferred to D2c.',
        'fiveThousandCompletedRun': 'NOT_RUN'}


def run(preset=PRESET, output=PROJECT_ROOT/'build/d2a/preflight.json', store=PROJECT_ROOT/'build/r1b/jobs'):
    report = {'schemaVersion': 'nvmr-d2a-preflight/v1', 'createdAt': datetime.now(timezone.utc).isoformat(),
        'scope': 'Offline input preparation only; no simulation/job/HTTP/router startup',
        'blockers': [], 'warnings': [], 'routingCalls': 0, 'simulationJobsCreated': 0,
        'sourceSha256': {p: digest(PROJECT_ROOT/p) for p in ('scripts/preflight_nvmr_5k.py',
            'backend/app/connected_simulation.py', 'backend/app/connected_jobs.py',
            'backend/app/simulation.py', 'backend/app/simulation_worker.py', 'backend/app/simulation_jobs.py',
            'backend/app/connected_analytics.py', 'backend/app/simulation_resources.py', 'config/connected-nvmr.json')}}
    def check(name, fn):
        try:
            value = fn()
            report[name] = value
            print(f'{name}: PASS', flush=True)
            return value
        except Exception as exc:
            report[name] = {'status': 'BLOCKED', 'error': str(getattr(exc, 'detail', exc))}
            report['blockers'].append(f'{name}: {report[name]["error"]}')
            print(f'{name}: BLOCKED', flush=True)
            return None
    validated = check('config', lambda: validate_preset(preset, Path(preset).with_suffix('.manifest.json')))
    if not validated:
        atomic_json(output, report)
        return report
    config, config_report = validated
    report['config'] = config_report
    report['resources'] = resource_report(config, Path(store))
    from scripts.connected_gis import verify_graph, verify_render, verify_source
    from scripts.connected_overview_tiles import verify_overview
    artifacts = {}
    report['artifacts'] = artifacts
    def artifact(label, fn):
        value = check(label, fn)
        artifacts[label] = report.pop(label)
        return value
    artifact('source', lambda: {'status': 'PASS', 'sha256': digest(verify_source())})
    identities = {}
    for mode in ('CAR', 'MOTORBIKE'):
        def verify(mode=mode):
            graph = verify_graph(mode)
            identity = routing_identity(connected_context(mode))
            verify_routing_validation(connected_context(mode), identity)
            identities[mode] = identity
            return {'status': 'PASS', 'routingIdentity': identity, 'graphFiles': len(graph['artifact_sha256']),
                'runtime': 'NOT_RUN'}
        artifact(mode, verify)
    artifact('map', lambda: {'status': 'PASS', 'detailIdentity': verify_render()['identity'],
                            'overviewIdentity': verify_overview()['identity']})
    if len(identities) == 2:
        def inputs():
            # Conservative floor for offline catalog load and two sequential input preparations.
            headroom = memory()
            require(min(headroom['availablePhysicalBytes'], headroom.get('systemCommitAvailableBytes', 2**40)) >= 512*1024**2,
                    'Offline preparation needs >=512MiB physical/commit headroom; rerun after releasing memory')
            begun = time.perf_counter()
            pools, provenance = read_anchor_catalog(identities)
            require(provenance['preSnapped'], 'Verified mode-specific pre-snapped catalog required; no raw fallback')
            diagnostics = input_diagnostics(config, pools, load_zones())
            diagnostics['provenance'] = provenance
            diagnostics['preparationAndRepeatSeconds'] = time.perf_counter()-begun
            diagnostics['memoryAfter'] = memory()
            return diagnostics
        value = check('inputs', inputs)
        if value:
            report['warnings'].extend(value['warnings'])
    else:
        report['inputs'] = {'status': 'NOT_RUN', 'reason': 'Graph identity/evidence unavailable'}
    def persistence():
        candidates = []
        for path in sorted(Path(store).glob('*/status.json')):
            status = json.loads(path.read_text(encoding='utf-8'))
            if status['status'] == 'COMPLETED' and status['config'].get('schemaVersion') == config.schemaVersion:
                candidates.append((status['config']['fleetSize'], path.parent))
        require(candidates, 'No persisted completed v5 run to verify persistence; run fixture tests and inspect source')
        # Smallest existing artifact with prepared inputs; never create a replacement run.
        folder = next((p for _, p in sorted(candidates) if (p/'prepared-input.json').is_file()), None)
        require(folder is not None, 'No existing completed v5 run with prepared inputs')
        read = lambda name: json.loads((folder/name).read_text(encoding='utf-8'))
        value = persistence_check(read('result.json'), read('prepared-input.json'), read('input.json'))
        value['existingJobId'] = folder.name
        return value
    check('persistence', persistence)
    report['memoryAfter'] = memory()
    if not report['resources']['admission']['allowed']:
        report['warnings'].append('Resource admission currently refused; owner releases memory before D2b, no scale reduction')
    report['warnings'].append('Router/worker runtime identity and headroom after routers start must be checked in D2b; offline artifacts do not establish runtime READY')
    report['beforeD2b'] = ['Owner approval; preserve preset checksum/version',
        'Release approximately 6.4 GB RAM as planned; recheck physical/commit/disk after routers load',
        'Confirm current API/worker source, same absolute JobStore and exactly one worker lease',
        'Verify both mode-specific runtime graph identities using existing readiness, then POST preset exactly once',
        'Record returned job ID; never repeat POST after timeout; retain complete job directory and GIS identities']
    report['conclusion'] = 'BLOCKED' if report['blockers'] else 'CONDITIONAL READY'
    atomic_json(output, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preset', type=Path, default=PRESET)
    parser.add_argument('--output', type=Path, default=PROJECT_ROOT/'build/d2a/preflight.json')
    parser.add_argument('--store', type=Path, default=PROJECT_ROOT/'build/r1b/jobs')
    args = parser.parse_args()
    value = run(args.preset, args.output, args.store)
    print(value.get('conclusion', 'BLOCKED'))
    raise SystemExit(2 if value['blockers'] else 0)
