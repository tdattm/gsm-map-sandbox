"""Real HTTP API/worker smoke and cancellation; existing local routers only.

Start API + one simulation_worker with the same store before running this script.
Does not start/stop any other service, rewrite M2 evidence or create GIS artifacts.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.simulation import validate_result
from backend.app.simulation_jobs import atomic_json
from scripts.m3_resources import require_headroom


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8013')
    parser.add_argument('--fleet-size', type=int, default=100)
    parser.add_argument('--booking-count', type=int, default=20)
    parser.add_argument('--check-cancel', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'build/m3-m4/api-integration.json')
    args = parser.parse_args()
    if urlparse(args.base_url).hostname not in ('127.0.0.1', 'localhost'):
        parser.error('Only the local task API is allowed')
    require_headroom()
    config = dict(regionId='nvmr-hanoi-core', seed='m3-m4-integration',
        fleetSize=args.fleet_size, carCount=round(args.fleet_size*.4), bookingCount=args.booking_count,
        horizonSeconds=900, maxWaitSeconds=300, onlineFraction=.8)
    report = {'status': 'RUNNING', 'baseUrl': args.base_url, 'config': config}
    atomic_json(args.output, report)
    with httpx.Client(base_url=args.base_url, trust_env=False, timeout=30) as client:
        base = '/api/v3/simulation/jobs'
        def create(body):
            response = client.post(base, json=body)
            assert response.status_code == 202, response.text
            return response.json()
        job = create(config)
        report['jobId'] = job['id']
        begun = time.perf_counter()
        observed = [job['status']]
        while time.perf_counter()-begun < 180:
            job = client.get(f'{base}/{job["id"]}').json()
            if job['status'] != observed[-1]:
                observed.append(job['status'])
            if job['status'] in ('COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED'):
                break
            time.sleep(.1)
        assert job['status'] == 'COMPLETED', job
        result = client.get(f'{base}/{job["id"]}/result').json()
        assert validate_result(result)
        snapshots = []
        for fraction in (0, .25, .5, .75, 1):
            response = client.get(f'{base}/{job["id"]}/snapshot',
                params={'timeSeconds': result['simulationDurationSeconds']*fraction})
            assert response.status_code == 200, response.text
            raw = response.json()
            c = raw['counts']
            assert c['total'] == c['online']+c['offline'] == args.fleet_size
            assert c['online'] == c['idle']+c['assigned']+c['onTrip']
            assert all('coordinates' not in v for v in raw['vehicles'])
            snapshots.append({'time': raw['simulationTimeSeconds'], 'sequence': raw['sequenceNumber'], 'counts': c})
        report.update(status='PASS', observedStatuses=observed, wallSeconds=time.perf_counter()-begun,
            counts=result['counts'], routingIdentities=result['routingIdentities'], snapshotSamples=snapshots,
            metrics=result['metrics'])
        if args.check_cancel:
            # The worker is single-process; cancellation is requested as soon as
            # RUNNING is observed, before this stress-shaped input can finish.
            require_headroom()
            cancelled = create({**config, 'fleetSize': 5000, 'carCount': 2000,
                'bookingCount': 5000, 'seed': 'cancel-probe'})
            cancel_id = cancelled['id']
            running = False
            until = time.monotonic()+30
            while time.monotonic() < until:
                state = client.get(f'{base}/{cancel_id}').json()['status']
                if state == 'RUNNING':
                    running = True
                    break
                assert state == 'QUEUED', state
                time.sleep(.02)
            assert running, 'Worker did not claim cancel-probe within 30s'
            before_cancel = time.perf_counter()
            response = client.post(f'{base}/{cancel_id}/cancel')
            assert response.json()['status'] == 'CANCELLED', response.text
            acknowledgement = time.perf_counter()-before_cancel
            checks = []
            for _ in range(10):
                status = client.get(f'{base}/{cancel_id}').json()['status']
                final = client.get(f'{base}/{cancel_id}/result')
                assert status == 'CANCELLED' and final.status_code == 409, (status, final.text)
                checks.append(status)
                time.sleep(.1)
            report['cancellation'] = {'status': 'PASS', 'jobId': cancel_id, 'observedRunning': running,
                'apiAcknowledgementSeconds': acknowledgement,
                'noFinalResultPolls': len(checks), 'latePublication': 'rejected'}
    atomic_json(args.output, report)
    print(json.dumps({'status': report['status'], 'jobId': report['jobId'], 'counts': report['counts'],
        'cancellation': report.get('cancellation')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
