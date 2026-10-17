"""Recorded-fixture domain-only benchmark, serial and RAM guarded (not live OSRM)."""
import argparse
import asyncio
import gc
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.simulation import IdleGrid, SimulationConfig, generate_inputs, simulate, snapshot, validate_result
from backend.app.simulation_jobs import atomic_json
from scripts.m3_fixture_travel import RecordedTravel, fixture_identities, load_fixture
from scripts.m3_resources import Monitor, environment, require_headroom

SCALES = (100, 500, 1000, 3000, 5000)
WORKLOADS = {'low': (.25, .02), 'typical': (.8, .25), 'burst': (.6, 1.)}


async def run_case(config, run_id='domain-benchmark'):
    initial, demand = generate_inputs(config, load_fixture()['anchors'])
    travels = {m: RecordedTravel(m) for m in ('CAR', 'MOTORBIKE')}
    result = await simulate(config, initial, demand, travels, fixture_identities(), run_id)
    for fraction in (0, .25, .5, .75, 1):
        snap = snapshot(result, result['simulationDurationSeconds']*fraction)
        c = snap['counts']
        assert c['total'] == c['offline']+c['online'] == len(initial)
        assert c['online'] == c['idle']+c['assigned']+c['onTrip']
        assert c['moving'] <= c['assigned']+c['onTrip']
    validate_result(result)
    semantic = {k: result[k] for k in ('vehicles', 'bookings', 'assignments', 'events', 'timelines', 'counts', 'routes')}
    digest = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
    return result, digest, {m: t.counts for m, t in travels.items()}


async def oracle(seed):
    """Small sampled exhaustive Table oracle, plus actual outcome comparison."""
    cfg = SimulationConfig(seed=f'oracle-{seed}', fleetSize=100, carCount=40, bookingCount=40,
        onlineFraction=.8, horizonSeconds=180, maxWaitSeconds=60, initialCandidates=16, maxCandidates=128)
    initial, bookings = generate_inputs(cfg, load_fixture()['anchors'])
    grid = IdleGrid(cfg.gridCellDegrees)
    for v in initial:
        if v.online:
            grid.add(v.id, v.vehicleType, v.position)
    ids = {v.id: v for v in initial}
    wins, feasible_misses, feasible, regrets, examined, exhaustive_points, shortlist_queries = 0, 0, 0, [], 0, 0, 0
    for b in bookings:
        travel = RecordedTravel(b.serviceType)
        all_ids = sorted(v.id for v in initial if v.online and v.vehicleType == b.serviceType)
        all_etas = {id: travel.eta(ids[id].position, b.pickup) for id in all_ids}
        # Match actual expansion's first feasible batch, not a larger ideal shortlist.
        checked, selected, size = [], None, cfg.initialCandidates
        while len(checked) < min(cfg.maxCandidates, len(all_ids)):
            batch = grid.shortlist(b.serviceType, b.pickup, min(size, cfg.maxCandidates-len(checked)), checked)
            shortlist_queries += 1
            checked.extend(batch)
            eligible = sorted((all_etas[id], id) for id in batch if all_etas[id] <= cfg.maxWaitSeconds)
            if eligible:
                selected = eligible[0]
                break
            size *= 2
        eligible = sorted((eta, id) for id, eta in all_etas.items() if eta <= cfg.maxWaitSeconds)
        if eligible:
            feasible += 1
            if selected is None:
                feasible_misses += 1
            else:
                wins += selected == eligible[0]
                regrets.append(selected[0]-eligible[0][0])
        examined += len(checked)
        exhaustive_points += len(all_ids)
    short, _, _ = await run_case(cfg, 'oracle')
    full, _, _ = await run_case(cfg.model_copy(update={'initialCandidates': 100, 'maxCandidates': 100}), 'oracle')
    def outcomes(result):
        return {e['bookingId']: e['type'] for e in result['events'] if e['type'] in ('TRIP_COMPLETED', 'BOOKING_UNSERVED')}
    a, b = outcomes(short), outcomes(full)
    return {'seed': seed, 'policyConfig': cfg.model_dump(), 'sampledStaticDispatches': len(bookings), 'oracleFeasible': feasible,
        'winnerRecall': wins/feasible if feasible else None, 'feasibleCandidateMiss': feasible_misses,
        'etaRegretSeconds': {'mean': sum(regrets)/len(regrets) if regrets else None, 'max': max(regrets, default=None)},
        'shortlistTablePoints': examined, 'exhaustiveTablePoints': exhaustive_points,
        'shortlistTableQueries': shortlist_queries, 'exhaustiveTableQueries': len(bookings),
        'tableQuerySavingsFraction': 1-shortlist_queries/len(bookings) if bookings else None,
        'tablePointSavingsFraction': 1-examined/exhaustive_points if exhaustive_points else None,
        'serviceOutcomeDifferences': sum(a[id] != b[id] for id in a),
        'shortlistCounts': short['counts'], 'exhaustiveCounts': full['counts'],
        'scope': 'Static sampled dispatch quality plus two full small runs; fixture ETA only, not live OSRM; different assignments may change subsequent outcomes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scales', nargs='+', type=int, choices=SCALES, default=list(SCALES))
    parser.add_argument('--seeds', type=int, default=5)
    parser.add_argument('--workloads', nargs='+', choices=list(WORKLOADS), default=list(WORKLOADS))
    parser.add_argument('--minimum-free-gib', type=float, default=2.)
    parser.add_argument('--output', type=Path, default=ROOT/'build/m3/domain.json')
    parser.add_argument('--oracle-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.seeds <= 30:
        parser.error('seeds must be between 1 and 30')
    report = {'schemaVersion': 'gsm-domain-benchmark/v1', 'kind': 'domain-only-recorded-fixture',
        'environment': environment(), 'fixtureIdentities': fixture_identities(), 'runs': [], 'oracle': [],
        'configuration': {'scales': args.scales, 'seeds': args.seeds, 'workloads': args.workloads,
            'minimumFreeGiB': args.minimum_free_gib, 'horizonSeconds': 900, 'maxWaitSeconds': 300},
        'performanceCriteria': 'No timing SLA asserted; correctness PASS requires lifecycle audit and accounting at 5 checkpoints; RAM guard >=2GiB',
        'status': 'RUNNING'}
    atomic_json(args.output, report)
    try:
        if not args.oracle_only:
            for scale in sorted(args.scales):
                for workload in args.workloads:
                    online, ratio = WORKLOADS[workload]
                    for seed in range(args.seeds):
                        gc.collect()
                        before = require_headroom(args.minimum_free_gib)
                        cfg = SimulationConfig(seed=f'm3-bench-{seed}', fleetSize=scale, carCount=round(scale*.4),
                            bookingCount=max(2, round(scale*ratio)), onlineFraction=online,
                            workload=workload, horizonSeconds=900, maxWaitSeconds=300)
                        with Monitor() as monitor:
                            result, digest, routing = asyncio.run(run_case(cfg))
                        resources = monitor.result()
                        row = {'status': 'PASS', 'config': cfg.model_dump(), 'counts': result['counts'],
                            'metrics': result['metrics'], 'semanticSha256': digest, 'fixtureOperations': routing,
                            'resources': resources, 'headroomBefore': before,
                            'bookingsPerSecond': cfg.bookingCount/resources['wallSeconds'],
                            'eventsPerSecond': result['metrics']['eventsProcessed']/resources['wallSeconds'],
                            'simulationSecondsPerWallSecond': result['simulationDurationSeconds']/resources['wallSeconds'],
                            'correctness': 'PASS linear independent lifecycle/provenance audit, 5 fleet checkpoints; final horizon drained'}
                        report['runs'].append(row)
                        print(json.dumps({'fleet': scale, 'workload': workload, 'seed': seed,
                            'wallSeconds': resources['wallSeconds'], 'counts': result['counts']}), flush=True)
                        atomic_json(args.output, report)
                        del result
                        if resources['minimumAvailablePhysicalBytes'] < args.minimum_free_gib*1024**3:
                            raise RuntimeError('RESOURCE_STOP: available physical RAM fell below guard during preceding run; do not increase load')
        for seed in range(args.seeds):
            require_headroom(args.minimum_free_gib)
            report['oracle'].append(asyncio.run(oracle(seed)))
            atomic_json(args.output, report)
        report['status'] = 'PASS'
    except Exception as exc:
        report.update(status='STOPPED', error=str(exc))
        atomic_json(args.output, report)
        raise
    atomic_json(args.output, report)


if __name__ == '__main__':
    main()
