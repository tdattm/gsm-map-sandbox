"""Serial live profiling including persistence; full job data stays in ignored build/."""
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
from backend.app.simulation import SimulationConfig, snapshot, validate_result
from backend.app.simulation_jobs import JobStore, atomic_json
from backend.app.simulation_worker import run_claimed
from backend.app.simulation_resources import require_simulation_headroom
from scripts.m3_resources import Monitor, environment, memory


def semantic_hash(result):
    # Run identity and wall-clock telemetry differ; all scientific outputs remain compared.
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k not in ('runId', 'metrics')}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    return hashlib.sha256(json.dumps(clean(result), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fleets', nargs='+', type=int, default=[10, 100])
    parser.add_argument('--label', default='manual')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--output', type=Path, default=ROOT/'build/m4-performance/live-profile.json')
    parser.add_argument('--cache-file', type=Path, help='Read-only persisted result parse/release measurement')
    parser.add_argument('--pressure-mib', type=int, default=0, choices=range(0, 513), metavar='0..512', help='Opt-in bounded synthetic RAM pressure; never Google Meet evidence')
    args = parser.parse_args()
    report = {'label': args.label, 'kind': 'serial-live-engine-with-atomic-persistence-not-browser', 'before': environment(), 'runs': []}
    pressure = []
    for _ in range(args.pressure_mib//32):
        current=memory()
        # Never chase the target by forcing swapping. Cap 512 MiB and keep reserves.
        if current['availablePhysicalBytes'] < 1.85*1024**3 or current.get('systemCommitAvailableBytes', 10*1024**3)<2.5*1024**3:
            break
        pressure.append(bytearray(32*1024**2))
    report['syntheticPressureBytes']=len(pressure)*32*1024**2
    store = JobStore(args.output.parent/f'{args.label}-jobs')
    for fleet in args.fleets * max(1, min(10, args.repeats)):
        cfg = SimulationConfig(fleetSize=fleet, carCount=round(fleet*.4), bookingCount=20 if fleet<=100 else round(fleet*.25), onlineFraction=1, seed=f'm4-memory-{fleet}')
        try:
            decision = require_simulation_headroom(cfg)
        except Exception as exc:
            report['runs'].append({'fleetSize': fleet, 'status': 'NOT RUN', 'reason': str(exc)})
            continue
        before = memory()
        with Monitor(.05) as monitor:
            queued = store.create(cfg)
            status = store.claim()
            assert status['id'] == queued['id'], 'Use an isolated empty queue'
            final = asyncio.run(run_claimed(store, status))
        row = {'fleetSize': fleet, 'jobId': final['id'], 'status': final['status'], 'error': final.get('error'), 'admission': decision, 'before': before, 'resources': monitor.result()}
        if final['status']=='COMPLETED':
            result = store.result(final['id']);validate_result(result)
            row.update(semanticSha256=semantic_hash(result), counts=result['counts'], routingIdentities=result['routingIdentities'], resultBytes=(store.path(final['id'])/'result.json').stat().st_size,
                       snapshotBytes=len(json.dumps(snapshot(result, 100)).encode()),routing=result['metrics']['routing'])
            del result
        gc.collect();row['afterRelease'] = memory();report['runs'].append(row)
        atomic_json(args.output, report)
    if args.cache_file:
        gc.collect();before=memory();begun=time.perf_counter()
        raw=json.loads(args.cache_file.read_text(encoding='utf-8'));after=memory()
        counts={k: len(raw[k]) for k in ('vehicles', 'bookings', 'events', 'routes')}
        del raw;gc.collect();time.sleep(.2)
        report['persistedCache']={'fileBytes':args.cache_file.stat().st_size,'counts':counts,'before':before,'loaded':after,'released':memory(),'parseSeconds':time.perf_counter()-begun,
            'note':'Single process parse/release. Private bytes delta is evidence of retained allocation, not an exclusive RAM footprint.'}
    pressure.clear();gc.collect()
    report['after']=environment();atomic_json(args.output,report)
    print(args.output)


if __name__=='__main__':
    main()
