"""Small live two-region API acceptance; requires existing local routers/API/worker.

No service is started, stopped, substituted or reconfigured by this command.
Raw evidence defaults to ignored build/r1a; pass --job-id to audit persisted runs.
"""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.regional_simulation import (REGION_IDS, RegionalScenarioConfig,
    engine_config, regional_snapshot)
from backend.app.simulation import validate_result
from backend.app.simulation_jobs import atomic_json
from scripts.m3_resources import memory


def audit_aggregates(result):
    """Reconstruct counts/KPI numerators from raw histories, without production aggregation."""
    config = RegionalScenarioConfig.model_validate(result['config'])
    allocations = {allocation.regionId: allocation for allocation in config.regions}
    if sorted(region['regionId'] for region in result['regions']) != sorted(allocations):
        raise ValueError('Both configured regions are required for independent aggregate audit')
    duration = result['simulationDurationSeconds']
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid common simulation duration')

    def equal(actual, expected, path):
        if isinstance(expected, dict):
            if not isinstance(actual, dict) or actual.keys() != expected.keys():
                raise ValueError(f'{path}: aggregate fields differ')
            for key, value in expected.items():
                equal(actual[key], value, f'{path}.{key}')
        elif isinstance(expected, (int, float)):
            if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-7):
                raise ValueError(f'{path}: {actual!r} differs from independent {expected!r}')
        elif actual != expected:
            raise ValueError(f'{path}: {actual!r} differs from independent {expected!r}')

    def accumulators(regions, mode=None):
        waits, busy, online, fleet_seconds, fleet = [], 0., 0., 0., 0
        requested = assigned = completed = unserved = 0
        for region in regions:
            bookings = {booking['id']: booking for booking in region['bookings']
                        if mode is None or booking['serviceType'] == mode}
            assignments = [assignment for assignment in region['assignments'] if assignment['bookingId'] in bookings]
            waits.extend(assignment['pickupAtSeconds']-bookings[assignment['bookingId']]['requestTimeSeconds']
                         for assignment in assignments)
            requested += len(bookings)
            assigned += len(assignments)
            completed += sum(event['type'] == 'TRIP_COMPLETED' and event['bookingId'] in bookings for event in region['events'])
            unserved += sum(event['type'] == 'BOOKING_UNSERVED' and event['bookingId'] in bookings for event in region['events'])
            for vehicle in region['vehicles']:
                if mode is not None and vehicle['vehicleType'] != mode:
                    continue
                fleet += 1
                fleet_seconds += duration
                history = region['timelines'][vehicle['id']]
                boundaries = [state['time'] for state in history[1:]]+[duration]
                for state, end in zip(history, boundaries):
                    elapsed = max(0., min(end, duration)-state['time'])
                    if state['state'] != 'OFFLINE':
                        online += elapsed
                    if state['state'] in ('ASSIGNED', 'ON_TRIP'):
                        busy += elapsed
        return {'fleetSize': fleet,
            'counts': {'requested': requested, 'assigned': assigned, 'completed': completed, 'unserved': unserved},
            'pickupWait': {'sumSeconds': sum(waits), 'count': len(waits),
                'meanSeconds': sum(waits)/len(waits) if waits else None,
                'maximumSeconds': max(waits) if waits else None},
            'utilization': {'busyVehicleSeconds': busy, 'onlineVehicleSeconds': online,
                'fleetVehicleSeconds': fleet_seconds, 'busyFractionOfOnline': busy/online if online else None,
                'busyFractionOfFleet': busy/fleet_seconds if fleet_seconds else None}}

    regions = result['regions']
    for region in regions:
        expected_config = engine_config(config, allocations[region['regionId']])
        if region['runId'] != result['runId'] or type(expected_config).model_validate(region['config']) != expected_config:
            raise ValueError('Region run/config identity differs from immutable scenario')
        equal(region['simulationDurationSeconds'], duration, f'{region["regionId"]}.clock')
    for label, group, stored in [('scenario', regions, result)]+[(region['regionId'], [region], region) for region in regions]:
        raw = accumulators(group)
        equal(stored['counts'], {**raw['counts'], 'pending': 0, 'activeTrips': 0}, label+'.counts')
        for key in ('pickupWait', 'utilization'):
            equal(stored['kpis'][key], raw[key], label+'.'+key)
        for mode in ('CAR', 'MOTORBIKE'):
            equal(stored['kpis']['byMode'][mode], accumulators(group, mode), label+'.'+mode)
    equal(result['globalTotals'], {
        'fleetSize': sum(len(region['vehicles']) for region in regions),
        'carCount': sum(vehicle['vehicleType'] == 'CAR' for region in regions for vehicle in region['vehicles']),
        'motorbikeCount': sum(vehicle['vehicleType'] == 'MOTORBIKE' for region in regions for vehicle in region['vehicles']),
        'bookingCount': sum(len(region['bookings']) for region in regions)}, 'globalTotals')


def process_memory(pid):
    """Read-only local process RSS. Lifetime peak is labelled separately."""
    try:
        if os.name == 'nt':
            import ctypes
            class Counters(ctypes.Structure):
                _fields_ = [('cb', ctypes.c_ulong), ('pageFaultCount', ctypes.c_ulong)]+[(name, ctypes.c_size_t)
                    for name in ('peakWorkingSet', 'workingSet', 'quotaPeakPagedPool', 'quotaPagedPool',
                                 'quotaPeakNonPagedPool', 'quotaNonPagedPool', 'pagefile', 'peakPagefile', 'privateUsage')]
            kernel = ctypes.windll.kernel32
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenProcess(0x1000 | 0x10, False, pid)
            if not handle:
                return None
            try:
                values = Counters()
                values.cb = ctypes.sizeof(values)
                query = ctypes.windll.psapi.GetProcessMemoryInfo
                query.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
                if not query(handle, ctypes.byref(values), values.cb):
                    return None
                return {'pid': pid, 'rssBytes': values.workingSet,
                        'lifetimePeakRssBytes': values.peakWorkingSet, 'privateBytes': values.privateUsage}
            finally:
                kernel.CloseHandle(handle)
        values = {}
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                key, raw = line.split(':', 1)
                values[key] = int(raw.strip().split()[0])*1024
        return {'pid': pid, 'rssBytes': values['VmRSS'], 'lifetimePeakRssBytes': values.get('VmHWM')}
    except (OSError, KeyError, ValueError):
        return None


def validate(client, base, job_id, timeout=300):
    prefix = base+'/api/v4/simulation/jobs/'+job_id
    deadline, progress, process_samples, system_samples = time.monotonic()+timeout, [], [], []
    runtime_response = client.get(base+'/api/v3/simulation/jobs/runtime')
    runtime_response.raise_for_status()
    runtime = runtime_response.json()
    while True:
        response = client.get(prefix)
        response.raise_for_status()
        status = response.json()
        for pid in {runtime['apiPid'], status.get('workerPid')} - {None}:
            value = process_memory(pid)
            if value:
                process_samples.append(value)
        system_samples.append(memory())
        if not progress or status['status'] != progress[-1]['status'] or status['progress'] != progress[-1]['progress']:
            progress.append({'status': status['status'], 'progress': status['progress']})
        if status['status'] == 'COMPLETED':
            break
        if status['status'] in ('FAILED', 'CANCELLED', 'INTERRUPTED'):
            raise RuntimeError(f'Regional job ended without final result: {status}')
        if time.monotonic() >= deadline:
            raise TimeoutError(f'Job {job_id} remains {status["status"]}; retained for explicit resume')
        time.sleep(.5)
    response = client.get(prefix+'/result')
    response.raise_for_status()
    result_bytes = len(response.content)
    result = response.json()
    if result['runId'] != job_id:
        raise ValueError('Stored result identity differs from requested job')
    cfg = RegionalScenarioConfig.model_validate(result['config'])
    for region in result['regions']:
        validate_result(region)
        for mode, identity in region['routingIdentities'].items():
            if (identity['algorithm'] != 'mld' or identity['profile'] != ('car' if mode == 'CAR' else 'motorbike')
                or identity['regionId'] != region['regionId'] or identity['vehicleType'] != mode):
                raise ValueError('Live acceptance requires region/mode-pinned local OSRM MLD evidence; fixture results are domain-only')
    audit_aggregates(result)
    if result['routingIdentities'] != {region['regionId']: region['routingIdentities'] for region in result['regions']}:
        raise ValueError('Stored regional routing identities differ from regional evidence')
    snapshots = []
    times = [0., min(30., result['simulationDurationSeconds']/2), result['simulationDurationSeconds']]
    for now in times:
        response = client.get(prefix+'/snapshot', params={'timeSeconds': now})
        response.raise_for_status()
        snap = response.json()
        if snap != regional_snapshot(result, now):
            raise ValueError('Regional API snapshot differs from immutable projection')
        if snap['counts']['total'] != cfg.fleetSize or any(region['simulationTimeSeconds'] != snap['simulationTimeSeconds'] for region in snap['regions']):
            raise ValueError('Fleet conservation/common-clock mismatch')
        snapshots.append({key: snap[key] for key in ('simulationTimeSeconds', 'counts')})
    selected, modes = [], set()
    for region in result['regions']:
        for mode in ('CAR', 'MOTORBIKE'):
            assignment = next((a for a in region['assignments'] if a['vehicleType'] == mode), None)
            expected_count = region['config']['carCount'] if mode == 'CAR' else region['config']['fleetSize']-region['config']['carCount']
            if expected_count and assignment is None:
                raise ValueError(f'{region["regionId"]}/{mode}: no assigned booking; selected-route live acceptance not proven')
            if assignment is None:
                continue
            detail_response = client.get(prefix+'/bookings/'+assignment['bookingId'])
            detail_response.raise_for_status()
            detail = detail_response.json()
            if detail['regionId'] != region['regionId'] or detail['vehicleType'] != mode:
                raise ValueError('Selected booking identity mismatch')
            checked = []
            for leg in ('pickupLeg', 'tripLeg'):
                ref = detail[leg]['routeRef']
                if ref is None:
                    if leg != 'pickupLeg' or detail[leg]['duration'] != 0:
                        raise ValueError('Only a stationary pickup may omit a route')
                    continue
                route_response = client.get(prefix+'/routes/'+ref)
                route_response.raise_for_status()
                route = route_response.json()
                if (route['runId'] != job_id or route['regionId'] != region['regionId']
                    or route['routingIdentity'] != detail['routingIdentity'] or len(route['coordinates']) < 2
                    or route['distance'] <= 0 or route['duration'] <= 0):
                    raise ValueError('Selected immutable route lacks correct region/mode/geometry/metrics')
                checked.append({'leg': leg, 'routeRef': ref, 'distance': route['distance'],
                    'duration': route['duration'], 'coordinateCount': len(route['coordinates']),
                    'routingIdentity': route['routingIdentity']})
            modes.add((region['regionId'], mode))
            selected.append({'regionId': region['regionId'], 'vehicleType': mode,
                'vehicleId': assignment['vehicleId'], 'bookingId': assignment['bookingId'], 'routes': checked})
    return {'status': 'PASS', 'scope': 'Live local API/worker regional result, counts, clock and immutable selected routes',
        'jobId': job_id, 'globalTotals': result['globalTotals'], 'counts': result['counts'],
        'routingIdentities': result['routingIdentities'], 'metrics': result['metrics'],
        'progress': progress, 'snapshots': snapshots, 'selected': selected,
        'validatedRegionModes': sorted([list(pair) for pair in modes]),
        'resultBytes': result_bytes,
        'resources': {'processes': [{'pid': pid,
            'role': 'api' if pid == runtime['apiPid'] else 'worker',
            'peakRssBytesSampled': max(sample['rssBytes'] for sample in process_samples if sample['pid'] == pid),
            'lifetimePeakRssBytes': max(sample.get('lifetimePeakRssBytes') or 0 for sample in process_samples if sample['pid'] == pid)}
            for pid in sorted({sample['pid'] for sample in process_samples})],
            'minimumAvailablePhysicalBytes': min(sample['availablePhysicalBytes'] for sample in system_samples),
            'minimumCommitHeadroomBytes': min((sample['systemCommitAvailableBytes'] for sample in system_samples
                if 'systemCommitAvailableBytes' in sample), default=None),
            'sampleCount': len(system_samples), 'pollSeconds': .5,
            'limitations': 'RSS samples can miss transient peaks; OS lifetime peaks may include prior jobs; verifier own RSS is separate'},
        'limitations': ['Synthetic fleet/demand, local OSRM static durations; no observed GSM operations',
            'Does not establish browser/WebGL performance, legal access, NoRoute/NoSegment fixtures or large-fleet capacity']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--job-id', help='Reopen and audit existing persisted regional job instead of creating')
    parser.add_argument('--total-fleet', type=int, default=20, help='Aggregate fleet over both regions (e.g. 20, 100, 500)')
    parser.add_argument('--fleet-per-region', type=int, help='Optional equal split overriding --total-fleet')
    parser.add_argument('--car-per-region', type=int, help='Optional exact CAR count for each region; default half its fleet')
    parser.add_argument('--bookings-per-region', type=int, default=12)
    parser.add_argument('--horizon', type=int, default=120)
    parser.add_argument('--seed', default='r1a-live-pilot-20/v1')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--output', type=Path, default=ROOT/'build/r1a/regional-api-validation.json')
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('--base-url must be local loopback HTTP')
    begun, before = time.perf_counter(), memory()
    report = {'status': 'FAIL', 'baseUrl': args.base_url, 'resourcesBefore': before}
    exit_code = 1
    try:
        with httpx.Client(timeout=60, trust_env=False) as client:
            job_id = args.job_id
            if job_id is None:
                sizes = ([args.fleet_per_region]*2 if args.fleet_per_region is not None
                         else [args.total_fleet//2, args.total_fleet-args.total_fleet//2])
                cfg = RegionalScenarioConfig(seed=args.seed, horizonSeconds=args.horizon,
                    regions=[{'regionId': region, 'fleetSize': fleet,
                        'carCount': args.car_per_region if args.car_per_region is not None else fleet//2,
                        'bookingCount': args.bookings_per_region,
                        'onlineFraction': 1.} for region, fleet in zip(REGION_IDS, sizes)])
                response = client.post(args.base_url.rstrip('/')+'/api/v4/simulation/jobs', json=cfg.model_dump(mode='json'))
                response.raise_for_status()
                job_id = response.json()['id']
            report['jobId'] = job_id
            report.update(validate(client, args.base_url.rstrip('/'), job_id, args.timeout))
            exit_code = 0
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError, TimeoutError) as exc:
        report['error'] = str(exc)
        if isinstance(exc, httpx.HTTPStatusError):
            report['response'] = exc.response.text
    finally:
        report.update(wallSeconds=time.perf_counter()-begun, resourcesAfter=memory())
        atomic_json(args.output, report)
    print(json.dumps({'status': report['status'], 'jobId': report.get('jobId'), 'output': str(args.output),
        'error': report.get('error')}, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
