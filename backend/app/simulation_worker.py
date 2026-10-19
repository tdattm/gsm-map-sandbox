"""One worker process: python -m backend.app.simulation_worker --store build/m3/jobs.

No background worker is silently started by API import. GIS stays at PROJECT_ROOT;
use the integration checkout for live routing, without duplicating ignored graphs.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import signal
import time

import httpx
from fastapi import HTTPException

from .booking import LocalTravel
from .config import Settings
from .dataset import public_region_status
from .fleet import candidate_catalog
from .modes import resolve_mode, routing_identity
from .regions import default_registry
from .schemas import RouteResponse
from .simulation import SimulationConfig, generate_inputs, meters, simulate
from .simulation_jobs import JobStore, atomic_json, file_lock


class InstrumentedTravel(LocalTravel):
    """Mode-pinned existing Table/snap validation, bounded route/Table caches."""
    def __init__(self, context, client, cache_limit=2048):
        self.latencies, self.failures = [], 0
        self.cache_limit = cache_limit
        super().__init__(context, self.fetch, meters, client)

    async def service(self, *args):
        begun = time.perf_counter()
        try:
            return await super().service(*args)
        except Exception:
            self.failures += 1
            raise
        finally:
            self.latencies.append((time.perf_counter()-begun)*1000)

    async def fetch(self, request):
        data = await self.service('route', [request.start, request.end],
            {'geometries': 'geojson', 'overview': 'full', 'steps': 'false'})
        try:
            route = data['routes'][0]
            if route['geometry']['type'] != 'LineString':
                raise ValueError('Expected LineString')
            snaps = data['waypoints']
            if len(snaps) != 2:
                raise ValueError('Expected two route waypoints')
            a, b = (self.snap(p, original) for p, original in zip(snaps, (request.start, request.end)))
            result = RouteResponse(coordinates=route['geometry']['coordinates'], distance=route['distance'],
                duration=route['duration'], snap_points=snaps,
                duration_source=f'OSRM {getattr(self.settings, "vehicle_type", "CAR")} static model; uncalibrated')
            if len(set(result.coordinates)) < 2 or meters(result.coordinates[0], a) > 5 or meters(result.coordinates[-1], b) > 5:
                raise ValueError('Route geometry/snap mismatch')
            return result
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise HTTPException(502, {'code': 'ROUTER_BAD_RESPONSE', 'message': str(exc)}) from exc

    async def route(self, start, end):
        if len(self.cache) >= self.cache_limit:
            self.cache.clear()
        # LocalTravel.route increments route counter; service also does, normalize
        # here so each recorded route count is one actual HTTP request.
        before = self.counts['route']
        try:
            return await super().route(start, end)
        finally:
            if self.counts['route'] > before:
                self.counts['route'] -= 1

    async def table(self, positions, pickup):
        if len(self.table_cache) >= self.cache_limit:
            self.table_cache.clear()
        return await super().table(positions, pickup)

    def telemetry(self):
        values = sorted(self.latencies)
        return {'requests': dict(self.counts), 'requestFailures': self.failures,
            'latencyMilliseconds': {'count': len(values), 'p50': values[len(values)//2] if values else None,
                'p95': values[min(len(values)-1, int(len(values)*.95))] if values else None,
                'total': sum(values)}, 'routeCacheSize': len(self.cache), 'tableCacheSize': len(self.table_cache)}


class RegionalInstrumentedTravel(InstrumentedTravel):
    """V4 Table sources are already verified vehicle positions, never new anchors.

    OSRM may otherwise choose a distant large-component phantom for a source on
    a small component. Keep the existing one-meter continuity requirement in
    the query as well as response validation; disconnected ETAs remain null.
    """
    async def service(self, name, points, params):
        if name == 'table':
            params = {**params, 'radiuses': ';'.join(
                ['1']*(len(points)-1)+[str(self.settings.max_snap_meters)])}
        return await super().service(name, points, params)


@asynccontextmanager
async def live_travels(config):
    registry = default_registry(Settings())
    modes = (["CAR"] if config.carCount else []) + (["MOTORBIKE"] if config.carCount < config.fleetSize else [])
    contexts, identities = {}, {}
    for mode in modes:
        context = resolve_mode(registry, config.regionId, mode)
        ready = await public_region_status(context)
        if not ready['ready']:
            raise HTTPException(503, {'code': 'MODE_NOT_READY', 'message': f'{mode}: {ready["readinessReason"]}'})
        contexts[mode] = context
        identities[mode] = routing_identity(context)
    async with httpx.AsyncClient(timeout=Settings().osrm_timeout_seconds, trust_env=False,
                                 limits=httpx.Limits(max_connections=2)) as client:
        travels = {m: InstrumentedTravel(c, client) for m, c in contexts.items()}
        catalog = candidate_catalog(next(iter(contexts.values())))
        yield contexts, identities, travels, catalog


async def execute_live(config, run_id, cancelled=None, progress=None, prepared=None):
    from .simulation_resources import require_simulation_headroom
    require_simulation_headroom(config)
    begun = time.perf_counter()
    async with live_travels(config) as (contexts, identities, travels, catalog):
        anchors = [c['coordinate'] for c in catalog['candidates']]
        initial, demand = generate_inputs(config, anchors)
        snapped = {}
        for v in initial:
            if cancelled and await cancelled():
                raise HTTPException(499, {'code': 'JOB_CANCELLED', 'message': 'Cancelled during preparation'})
            key = (v.vehicleType, tuple(v.position))
            if key not in snapped:
                snapped[key] = await travels[v.vehicleType].nearest(v.position)
        initial = [v.model_copy(update={'position': tuple(snapped[v.vehicleType, tuple(v.position)])}) for v in initial]
        immutable = {'schemaVersion': 'gsm-simulation-input/v1', 'runId': run_id, 'config': config.model_dump(),
            'routingIdentities': identities, 'catalogFingerprint': catalog['datasetFingerprint'],
            'catalogProvenance': catalog['provenance'],
            'vehicles': [v.model_dump(mode='json') for v in initial], 'bookings': [b.model_dump(mode='json') for b in demand]}
        if prepared:
            prepared(immutable)
        preparation_ms = (time.perf_counter()-begun)*1000
        result = await simulate(config, initial, demand, travels, identities, run_id, cancelled, progress)
        # Fail closed if an on-disk graph/profile changes during preparation or run.
        if any(routing_identity(c) != identities[m] for m, c in contexts.items()):
            raise HTTPException(503, {'code': 'ROUTING_IDENTITY_CHANGED', 'message': 'Routing evidence changed during run'})
        result['provenance'] = {'catalogFingerprint': catalog['datasetFingerprint'], 'catalog': catalog['provenance']}
        result['metrics'].update(preparationMilliseconds=preparation_ms,
            totalMilliseconds=(time.perf_counter()-begun)*1000,
            routing={m: t.telemetry() for m, t in travels.items()})
        return result


async def run_claimed(store, status, executor=None, stopping=lambda: False):
    id = status['id']
    last_progress = 0.
    async def cancelled():
        return stopping() or store.read(id)['status'] != 'RUNNING'
    async def progress(value):
        nonlocal last_progress
        # Disk progress is intentionally throttled; cancellation checked each event/router call.
        now = time.monotonic()
        if now-last_progress >= .25:
            store.update_progress(id, value)
            last_progress = now
    try:
        manifest = json.loads((store.path(id)/'input.json').read_text(encoding='utf-8'))
        if manifest['inputHash'] != status['inputHash']:
            raise ValueError('Immutable input manifest identity mismatch')
        import hashlib
        if hashlib.sha256(json.dumps(manifest['config'], sort_keys=True).encode()).hexdigest() != manifest['inputHash']:
            raise ValueError('Immutable run configuration modified')
        if manifest['config'].get('schemaVersion') == 'gsm-nvmr-connected-scenario/v1':
            from .connected_simulation import ConnectedScenarioConfig
            from .connected_jobs import execute_connected_live
            config = ConnectedScenarioConfig.model_validate(manifest['config'])
            selected_executor = executor or execute_connected_live
        elif manifest['config'].get('schemaVersion') == 'gsm-nvmr-regional-scenario/v1':
            from .regional_simulation import RegionalScenarioConfig
            from .regional_jobs import execute_regional_live
            config = RegionalScenarioConfig.model_validate(manifest['config'])
            selected_executor = executor or execute_regional_live
        else:
            config = SimulationConfig.model_validate(manifest['config'])
            selected_executor = executor or execute_live
        result = await selected_executor(config, id, cancelled, progress,
            lambda value: atomic_json(store.path(id)/'prepared-input.json', value))
        if stopping():
            store.cancel(id)
        return store.finish(id, result=result)
    except HTTPException as exc:
        if exc.status_code == 499:
            return store.cancel(id)
        return store.finish(id, failure=exc.detail)
    except Exception as exc:
        return store.finish(id, failure={'code': 'SIMULATION_FAILED', 'message': str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', default=None, help='Same directory as GSM_SIMULATION_STORE on API')
    parser.add_argument('--once', action='store_true', help='Claim at most one queued job and exit')
    args = parser.parse_args()
    store = JobStore(args.store)
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        with file_lock(store.root/'.worker.lock', blocking=False):
            store.interrupt_abandoned()
            while not stopping:
                status = store.claim()
                if status:
                    print(json.dumps({'job': status['id'], 'status': 'RUNNING'}), flush=True)
                    outcome = asyncio.run(run_claimed(store, status, stopping=lambda: stopping))
                    print(json.dumps({'job': status['id'], 'status': outcome['status']}), flush=True)
                if args.once:
                    break
                if status is None:
                    time.sleep(.25)
    except OSError as exc:
        raise SystemExit(f'Worker store already owned or cannot be locked: {exc}') from exc


if __name__ == '__main__':
    main()
