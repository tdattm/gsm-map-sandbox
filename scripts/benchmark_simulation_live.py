"""Serial live OSRM benchmark using validated existing CAR/MOTORBIKE artifacts."""
import argparse
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.simulation import SimulationConfig, snapshot
from backend.app.simulation_jobs import atomic_json
from backend.app.simulation_worker import execute_live
from scripts.m3_resources import Monitor, environment, require_headroom


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fleet-size', type=int, default=100)
    parser.add_argument('--booking-count', type=int, default=20)
    parser.add_argument('--online-fraction', type=float, default=.8)
    parser.add_argument('--workload', choices=['low', 'typical', 'burst'], default='typical')
    parser.add_argument('--seed', default='m3-live')
    parser.add_argument('--minimum-free-gib', type=float, default=2.)
    parser.add_argument('--output', type=Path, default=ROOT/'build/m3/live-100.json')
    args = parser.parse_args()
    require_headroom(args.minimum_free_gib)
    cfg = SimulationConfig(seed=args.seed, fleetSize=args.fleet_size, carCount=round(args.fleet_size*.4),
        bookingCount=args.booking_count, onlineFraction=args.online_fraction, workload=args.workload,
        horizonSeconds=900, maxWaitSeconds=300)
    report = {'schemaVersion': 'gsm-live-simulation-benchmark/v1', 'kind': 'live-local-OSRM',
        'environmentBefore': environment(), 'config': cfg.model_dump(), 'status': 'RUNNING'}
    atomic_json(args.output, report)
    try:
        with Monitor() as monitor:
            result = asyncio.run(execute_live(cfg, f'live-{args.fleet_size}',
                prepared=lambda value: atomic_json(args.output.with_suffix('.inputs.json'), value)))
            for fraction in (0, .25, .5, .75, 1):
                s = snapshot(result, fraction*result['simulationDurationSeconds'])
                c = s['counts']
                assert c['online'] == c['idle']+c['assigned']+c['onTrip']
                assert c['total'] == c['offline']+c['online']
        report.update(status='PASS', resources=monitor.result(), counts=result['counts'],
            metrics=result['metrics'], routingIdentities=result['routingIdentities'],
            simulationDurationSeconds=result['simulationDurationSeconds'],
            provenance=result['provenance'], environmentAfter=environment())
        # Full run and prepared routing evidence remain ignored, with a small summary publishable.
        atomic_json(args.output.with_suffix('.result.json'), result)
    except Exception as exc:
        report.update(status='FAIL', error=str(exc), detail=getattr(exc, 'detail', None))
        atomic_json(args.output, report)
        raise
    atomic_json(args.output, report)
    print(args.output)


if __name__ == '__main__':
    main()
