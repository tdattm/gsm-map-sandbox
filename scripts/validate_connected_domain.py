"""Reproducible DOMAIN FIXTURE benchmarks; no local OSRM performance claims.

Run sequentially, outside heavy GIS preprocessing:
python -m scripts.validate_connected_domain --output docs/nvmr/r1b-evidence/domain-benchmark.json
"""
import argparse
import asyncio
import json
from pathlib import Path
import time

from backend.app.connected_simulation import (ConnectedScenarioConfig, connected_inputs,
    connected_snapshot, load_zones, simulate_connected, validate_connected_result)
from backend.app.schemas import RouteResponse
from backend.app.simulation import meters
from backend.app.simulation_jobs import atomic_json
from scripts.m3_fixture_travel import fixture_identities
from scripts.m3_resources import memory


def process_peak_rss():
    return memory()['processPeakRssBytes']


class FixtureTravel:
    def __init__(self, mode):
        self.mode = mode
        self.counts = {'route': 0, 'table': 0, 'routeCacheHits': 0, 'tableCacheHits': 0}

    async def table(self, sources, target):
        self.counts['table'] += 1
        return [0. if tuple(p) == tuple(target) else 5. for p in sources]

    async def route(self, start, end):
        self.counts['route'] += 1
        return RouteResponse(coordinates=[start, end], distance=meters(start, end), duration=10.,
            duration_source=f'Explicit synthetic connected-domain {self.mode} fixture; NOT OSRM',
            snap_points=[{'location': start, 'distance': 0}, {'location': end, 'distance': 0}])


async def benchmark(size, booking_count):
    zones = load_zones()
    config = ConnectedScenarioConfig(fleetSize=size, carCount=size*2//5, bookingCount=booking_count,
        seed='connected-domain-benchmark/v1', horizonSeconds=900)
    anchors = []
    for zone in zones:
        w, s, e, n = zone['bbox']
        # Synthetic fixture positions only. Runtime uses the OSM road catalogs.
        anchors.extend((w+(e-w)*(.05+.9*x/100), s+(n-s)*(.05+.9*y/60))
                       for y in range(60) for x in range(100))
    start = time.perf_counter()
    initial, demand, vmeta, bmeta = connected_inputs(config, dict.fromkeys(('CAR', 'MOTORBIKE'), anchors), zones)
    preparation = time.perf_counter()-start
    travels = {mode: FixtureTravel(mode) for mode in ('CAR', 'MOTORBIKE')}
    identities = {mode: {**identity, 'regionId': 'nvmr-connected'} for mode, identity in fixture_identities().items()}
    result = await simulate_connected(config, initial, demand, travels, identities,
        f'connected-domain-{size}', zones, vmeta, bmeta)
    elapsed = time.perf_counter()-start
    validate_connected_result(result)
    for t in (0, 450, result['simulationDurationSeconds']):
        assert connected_snapshot(result, t)['counts']['total'] == size
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    return {'fleetSize': size, 'bookingCount': booking_count, 'wallSeconds': elapsed,
        'preparationSeconds': preparation, 'peakProcessRssBytes': process_peak_rss(),
        'peakRssScope': 'Process lifetime high-water mark; scales executed in same sequential process',
        'systemMemoryAfter': memory(), 'osrmMemory': None, 'osrmMemoryReason': 'DOMAIN FIXTURE, no OSRM requests',
        'routing': {mode: travel.counts for mode, travel in travels.items()},
        'metrics': result['metrics'], 'persistedOutputBytes': len(encoded), 'counts': result['counts'],
        'distributionQuality': result['distributionQuality'], 'replayConservation': 'PASS'}


async def run(args):
    results = []
    for size in args.sizes:
        result = await benchmark(size, args.bookings)
        results.append(result)
        atomic_json(args.output, {'schemaVersion': 'connected-domain-benchmark/v1',
            'evidenceType': 'DOMAIN FIXTURE ONLY; synthetic positions and route evidence; not local OSRM',
            'status': 'PASS' if len(results) == len(args.sizes) else 'PARTIAL', 'benchmarks': results})
        print(json.dumps({key: result[key] for key in ('fleetSize', 'wallSeconds', 'peakProcessRssBytes', 'persistedOutputBytes', 'counts')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('docs/nvmr/r1b-evidence/domain-benchmark.json'))
    parser.add_argument('--bookings', type=int, default=100)
    parser.add_argument('--sizes', type=int, nargs='+', default=[100, 500, 1000, 5000])
    asyncio.run(run(parser.parse_args()))
