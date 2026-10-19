"""Live local v5 acceptance; creates one run or audits an existing immutable run."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from backend.app.connected_simulation import ConnectedScenarioConfig, ZONE_IDS, connected_snapshot
from backend.app.simulation import validate_result
from backend.app.simulation_jobs import atomic_json
from scripts.m3_resources import memory
from scripts.validate_regional_api import process_memory


def audit(result):
    """Reconstruct additive KPI numerators independently from persisted histories."""
    validate_result(result)
    cfg = ConnectedScenarioConfig.model_validate(result['config'])
    if result['schemaVersion'] != 'gsm-nvmr-connected-result/v1' or result['regionId'] != 'nvmr-connected':
        raise ValueError('Wrong connected result identity')
    if len(result['vehicles']) != cfg.fleetSize:
        raise ValueError('Fleet cardinality mismatch')
    for allocation in cfg.fleetAllocations:
        for mode, expected in [('CAR', allocation.carCount), ('MOTORBIKE', allocation.motorbikeCount)]:
            if sum(v['homeZoneId'] == allocation.zoneId and v['vehicleType'] == mode for v in result['vehicles']) != expected:
                raise ValueError('Home-zone/mode allocation mismatch')
    duration = result['simulationDurationSeconds']
    for label, vehicles, bookings, stored in [
        ('global', result['vehicles'], result['bookings'], result['kpis']['global'])
    ]+[(z, [v for v in result['vehicles'] if v['homeZoneId'] == z],
        [b for b in result['bookings'] if b['pickupZoneId'] == z], result['kpis']['byZone'][z]) for z in ZONE_IDS]+[
        (mode, [v for v in result['vehicles'] if v['vehicleType'] == mode],
         [b for b in result['bookings'] if b['serviceType'] == mode], result['kpis']['byMode'][mode])
        for mode in ('CAR', 'MOTORBIKE')]:
        bids = {b['id']: b for b in bookings}
        assignments = [a for a in result['assignments'] if a['bookingId'] in bids]
        waits = [a['pickupAtSeconds']-bids[a['bookingId']]['requestTimeSeconds'] for a in assignments]
        busy = online = 0.
        for vehicle in vehicles:
            history = result['timelines'][vehicle['id']]
            for state, end in zip(history, [s['time'] for s in history[1:]]+[duration]):
                elapsed = max(0., min(duration, end)-state['time'])
                online += elapsed*(state['state'] != 'OFFLINE')
                busy += elapsed*(state['state'] in ('ASSIGNED', 'ON_TRIP'))
        numerators = [(stored['pickupWait']['sumSeconds'], sum(waits)),
            (stored['pickupWait']['count'], len(waits)),
            (stored['utilization']['busyVehicleSeconds'], busy),
            (stored['utilization']['onlineVehicleSeconds'], online),
            (stored['utilization']['fleetVehicleSeconds'], len(vehicles)*duration)]
        if any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6) for a, b in numerators):
            raise ValueError(f'Independent KPI numerator mismatch: {label}')
        derived = [
            (stored['pickupWait']['meanSeconds'], sum(waits)/len(waits) if waits else None),
            (stored['pickupWait']['maximumSeconds'], max(waits) if waits else None),
            (stored['utilization']['busyFractionOfOnline'], busy/online if online else None),
            (stored['utilization']['busyFractionOfFleet'], busy/(len(vehicles)*duration) if vehicles and duration else None)]
        if any((a is None) != (b is None) or (a is not None and
            not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6)) for a, b in derived):
            raise ValueError(f'Independent KPI ratio mismatch: {label}')
        expected = {'requested': len(bookings), 'assigned': len(assignments),
            'completed': sum(e['type'] == 'TRIP_COMPLETED' and e['bookingId'] in bids for e in result['events']),
            'unserved': sum(e['type'] == 'BOOKING_UNSERVED' and e['bookingId'] in bids for e in result['events'])}
        if stored['counts'] != expected:
            raise ValueError(f'Independent booking count mismatch: {label}')
    return cfg


def validate(client, base, job_id, timeout):
    prefix = base+'/api/v5/simulation/jobs/'+job_id
    deadline, samples, systems = time.monotonic()+timeout, [], []
    while True:
        response = client.get(prefix)
        response.raise_for_status()
        status = response.json()
        systems.append(memory())
        if status.get('workerPid'):
            sample = process_memory(status['workerPid'])
            if sample:
                samples.append(sample)
        if status['status'] == 'COMPLETED':
            break
        if status['status'] in ('FAILED', 'CANCELLED', 'INTERRUPTED'):
            raise RuntimeError(json.dumps(status))
        if time.monotonic() >= deadline:
            raise TimeoutError(f'Run {job_id} retained in {status["status"]}; no duplicate POST')
        time.sleep(.5)
    raw = client.get(prefix+'/result')
    raw.raise_for_status()
    result = raw.json()
    cfg = audit(result)
    if result['runId'] != job_id:
        raise ValueError('Wrong immutable run ID')
    for mode, identity in result['routingIdentities'].items():
        if identity['algorithm'] != 'mld' or identity['profile'] != mode.lower() or identity['regionId'] != 'nvmr-connected':
            raise ValueError('Live acceptance requires real independent connected OSRM graphs')
    snapshots = []
    for now in [0., result['simulationDurationSeconds']/2, result['simulationDurationSeconds']]:
        projected = client.get(prefix+'/snapshot', params={'timeSeconds': now})
        projected.raise_for_status()
        snap = projected.json()
        if snap != connected_snapshot(result, now) or snap['counts']['total'] != cfg.fleetSize:
            raise ValueError('Immutable snapshot/fleet mismatch')
        snapshots.append({'time': now, 'counts': snap['counts'], 'zoneCounts': snap['zoneCounts']})
    selected = []
    for mode in ('CAR', 'MOTORBIKE'):
        assignment = next((a for a in result['assignments'] if a['vehicleType'] == mode), None)
        if assignment is None:
            if any(v['vehicleType'] == mode for v in result['vehicles']) and any(b['serviceType'] == mode for b in result['bookings']):
                raise ValueError(f'No {mode} assignment: selected journey live acceptance not established')
            continue
        detail = client.get(prefix+'/bookings/'+assignment['bookingId'])
        detail.raise_for_status()
        route_refs = []
        for leg in ('pickupLeg', 'tripLeg'):
            ref = detail.json()[leg]['routeRef']
            if ref is None:
                continue
            fetched = client.get(prefix+'/routes/'+ref)
            fetched.raise_for_status()
            route = fetched.json()
            if route['routingIdentity'] != result['routingIdentities'][mode] or route['runId'] != job_id or len(route['coordinates']) < 2:
                raise ValueError('Selected immutable route mismatch')
            route_refs.append(ref)
        selected.append({'vehicleType': mode, 'vehicleId': assignment['vehicleId'], 'bookingId': assignment['bookingId'], 'routeRefs': route_refs})
    docker_stats = {'available': False, 'samples': [], 'reason': ''}
    try:
        stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}'],
            capture_output=True, text=True, timeout=20)
        docker_stats.update(available=stats.returncode == 0, samples=stats.stdout.splitlines(),
            returnCode=stats.returncode, reason=stats.stderr.strip() if stats.returncode else '')
    except (OSError, subprocess.TimeoutExpired) as exc:
        docker_stats['reason'] = str(exc)
    return {'status': 'PASS', 'evidenceKind': 'real-local-OSRM-v5', 'jobId': job_id,
        'fleetSize': cfg.fleetSize, 'counts': result['counts'], 'metrics': result['metrics'],
        'crossZoneDispatchExamples': [{key: a[key] for key in ('vehicleId', 'bookingId', 'vehicleType',
            'vehicleZoneAtAssignment', 'pickupZoneId', 'estimatedPickupEtaSeconds', 'pickupRouteRef')}
            for a in result['assignments'] if a['vehicleZoneAtAssignment'] != a['pickupZoneId']][:5],
        'distributionQuality': result['distributionQuality'], 'routingIdentities': result['routingIdentities'],
        'resultBytes': len(raw.content), 'snapshots': snapshots, 'selected': selected,
        'resources': {'workerPeakRssSampledBytes': max((s['rssBytes'] for s in samples), default=None),
            'workerLifetimePeakRssBytes': max((s['lifetimePeakRssBytes'] for s in samples
                if isinstance(s.get('lifetimePeakRssBytes'), (int, float))), default=None),
            'minimumAvailablePhysicalBytes': min(s['availablePhysicalBytes'] for s in systems),
            'minimumCommitHeadroomBytes': min((s['systemCommitAvailableBytes'] for s in systems if 'systemCommitAvailableBytes' in s), default=None),
            'sampleCount': len(systems), 'pollSeconds': .5, 'dockerStatsAfter': docker_stats},
        'limitations': ['Synthetic inputs/static modeled ETA; not observed GSM operations',
            'RSS samples can miss peaks; process lifetime peak may include earlier runs',
            'OSRM stats captured after run, not per-process peak; browser verified separately']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8022')
    parser.add_argument('--job-id')
    parser.add_argument('--fleet', type=int, default=100)
    parser.add_argument('--bookings', type=int, default=25)
    parser.add_argument('--seed', default='connected-live/v1')
    parser.add_argument('--horizon', type=int, default=900)
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--cross-zone-proof', action='store_true',
        help='Place the entire fleet in Bac Ninh and demand in Hanoi; max wait3600s, intra-Hanoi trips')
    parser.add_argument('--output', type=Path, default=ROOT/'build/r1b/live.json')
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('Local loopback HTTP API required')
    report = {'status': 'FAIL', 'baseUrl': args.base_url}
    try:
        with httpx.Client(timeout=120, trust_env=False) as client:
            job_id = args.job_id
            if job_id is None:
                cfg = ConnectedScenarioConfig(fleetSize=args.fleet, carCount=round(args.fleet*.4),
                    bookingCount=args.bookings, seed=args.seed, horizonSeconds=args.horizon, onlineFraction=1.)
                if args.cross_zone_proof:
                    raw_config = cfg.model_dump()
                    raw_config.update(fleetAllocations=[{'zoneId': zone, 'carCount': cfg.carCount if zone == 'bac-ninh' else 0,
                        'motorbikeCount': cfg.fleetSize-cfg.carCount if zone == 'bac-ninh' else 0} for zone in ZONE_IDS],
                        demandWeights={zone: 1. if zone == 'hanoi' else 0. for zone in ZONE_IDS},
                        crossZoneDemandFraction=0., maxWaitSeconds=3600)
                    cfg = ConnectedScenarioConfig.model_validate(raw_config)
                created = client.post(args.base_url+'/api/v5/simulation/jobs', json=cfg.model_dump(mode='json'))
                created.raise_for_status()
                job_id = created.json()['id']
                report['jobId'] = job_id
                atomic_json(args.output, {**report, 'status': 'RUNNING'})
            report.update(validate(client, args.base_url, job_id, args.timeout))
            if args.cross_zone_proof and not any(a['vehicleZoneAtAssignment'] == 'bac-ninh' and
                a['pickupZoneId'] == 'hanoi' for a in report['crossZoneDispatchExamples']):
                raise ValueError('Targeted Bac Ninh -> Hanoi dispatch has not been established')
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error'] = str(exc)
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                report['errorDetail'] = exc.response.json()
            except ValueError:
                report['errorDetail'] = exc.response.text[:1000]
    atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
