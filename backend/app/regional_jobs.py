"""Versioned regional API; uses the same bounded durable queue and worker lease."""
import asyncio
import time

import httpx
from fastapi import APIRouter, HTTPException, Query

from .config import Settings
from .dataset import public_region_status
from .fleet import candidate_catalog
from .modes import resolve_mode, routing_identity
from .regions import default_registry
from .regional_simulation import (RESULT_SCHEMA, RegionalScenarioConfig, active_modes,
    combine_regions, engine_config, regional_inputs, regional_snapshot, regional_summary)
from .simulation import simulate
from .simulation_cache import IdleResultCache
from .simulation_details import booking_detail
from .simulation_jobs import JobStore, error
from .simulation_resources import require_simulation_headroom


async def regional_readiness(config, registry=None, cancelled=None):
    """Verify every requested region/mode before any regional execution.

    Large manifest/catalog hashing runs outside the API event loop. No router is
    substituted on missing data; failures include the precise region and mode.
    """
    registry = registry or await asyncio.to_thread(default_registry, Settings())
    contexts, identities, failures = {}, {}, []
    for allocation in config.regions:
        for mode in active_modes(allocation):
            if cancelled and await cancelled():
                raise HTTPException(499, {'code': 'JOB_CANCELLED', 'message': 'Cancelled during regional readiness'})
            try:
                context = await asyncio.to_thread(resolve_mode, registry, allocation.regionId, mode)
                ready = await public_region_status(context)
                if not ready['ready']:
                    failures.append({'regionId': allocation.regionId, 'vehicleType': mode,
                        'code': 'MODE_NOT_READY', 'message': ready['readinessReason']})
                    continue
                identity = await asyncio.to_thread(routing_identity, context)
                if identity['regionId'] != allocation.regionId or identity['vehicleType'] != mode:
                    raise ValueError('Configured routing identity differs from requested region/mode')
                contexts.setdefault(allocation.regionId, {})[mode] = context
                identities.setdefault(allocation.regionId, {})[mode] = identity
            except HTTPException as exc:
                if exc.status_code == 499:
                    raise
                detail = exc.detail if isinstance(exc.detail, dict) else {'message': str(exc.detail)}
                failures.append({'regionId': allocation.regionId, 'vehicleType': mode, **detail})
            except (OSError, ValueError, KeyError) as exc:
                failures.append({'regionId': allocation.regionId, 'vehicleType': mode,
                    'code': 'ROUTING_EVIDENCE_UNAVAILABLE', 'message': str(exc)})
    if failures:
        details = '; '.join(f'{failure["regionId"]}/{failure["vehicleType"]}: {failure.get("message", failure.get("code", "not ready"))}'
                            for failure in failures)
        raise HTTPException(503, {'code': 'REGIONAL_NOT_READY',
            'message': 'Regional routing not ready: '+details,
            'regions': failures})
    return contexts, identities


async def execute_regional_live(config, run_id, cancelled=None, progress=None, prepared=None):
    # Apply unchanged admission floors to aggregate fleet/bookings, and retain
    # all completed regional histories until the one atomic final publication.
    await asyncio.to_thread(require_simulation_headroom, config)
    begun = time.perf_counter()
    contexts, identities = await regional_readiness(config, cancelled=cancelled)
    from .simulation_worker import RegionalInstrumentedTravel
    results, prepared_inputs = [], []
    async with httpx.AsyncClient(timeout=Settings().osrm_timeout_seconds, trust_env=False,
                                 limits=httpx.Limits(max_connections=2)) as client:
        for index, allocation in enumerate(config.regions):
            if cancelled and await cancelled():
                raise HTTPException(499, {'code': 'JOB_CANCELLED', 'message': 'Regional simulation cancelled'})
            region_id = allocation.regionId
            region_begun = time.perf_counter()
            travels = {mode: RegionalInstrumentedTravel(context, client) for mode, context in contexts[region_id].items()}
            catalog = await asyncio.to_thread(candidate_catalog, next(iter(contexts[region_id].values())))
            vehicles, bookings = regional_inputs(config, allocation, [a['coordinate'] for a in catalog['candidates']])
            snapped = {}
            for vehicle in vehicles:
                if cancelled and await cancelled():
                    raise HTTPException(499, {'code': 'JOB_CANCELLED', 'message': 'Cancelled during regional preparation'})
                key = (vehicle.vehicleType, tuple(vehicle.position))
                if key not in snapped:
                    snapped[key] = await travels[vehicle.vehicleType].nearest(vehicle.position)
            vehicles = [v.model_copy(update={'position': tuple(snapped[v.vehicleType, tuple(v.position)])}) for v in vehicles]
            prepared_inputs.append({'regionId': region_id, 'config': engine_config(config, allocation).model_dump(mode='json'),
                'routingIdentities': identities[region_id], 'catalogFingerprint': catalog['datasetFingerprint'],
                'catalogProvenance': catalog['provenance'], 'vehicles': [v.model_dump(mode='json') for v in vehicles],
                'bookings': [b.model_dump(mode='json') for b in bookings]})
            if prepared:
                prepared({'schemaVersion': 'gsm-nvmr-regional-input/v1', 'runId': run_id,
                    'config': config.model_dump(mode='json'), 'complete': False, 'regions': prepared_inputs})
            preparation_ms = (time.perf_counter()-region_begun)*1000
            async def report(value):
                if progress:
                    await progress((index+value)/len(config.regions))
            result = await simulate(engine_config(config, allocation), vehicles, bookings, travels,
                identities[region_id], run_id, cancelled, report)
            result['provenance'] = {'catalogFingerprint': catalog['datasetFingerprint'], 'catalog': catalog['provenance']}
            result['metrics'].update(preparationMilliseconds=preparation_ms,
                totalMilliseconds=(time.perf_counter()-region_begun)*1000,
                routing={mode: travel.telemetry() for mode, travel in travels.items()})
            results.append(result)
            # Release region-specific bounded route/Table caches before next region.
            del travels
    for region_id, modes in contexts.items():
        for mode, context in modes.items():
            if await asyncio.to_thread(routing_identity, context) != identities[region_id][mode]:
                raise HTTPException(503, {'code': 'ROUTING_IDENTITY_CHANGED', 'regionId': region_id,
                    'vehicleType': mode, 'message': 'Regional routing evidence changed during scenario'})
    if prepared:
        prepared({'schemaVersion': 'gsm-nvmr-regional-input/v1', 'runId': run_id,
            'config': config.model_dump(mode='json'), 'complete': True, 'regions': prepared_inputs})
    result = combine_regions(config, results, run_id)
    result['metrics']['totalMilliseconds'] = (time.perf_counter()-begun)*1000
    result['metrics']['preparationMilliseconds'] = sum(r['metrics']['preparationMilliseconds'] for r in results)
    return result


def create_regional_router(store=None, registry=None, readiness=regional_readiness):
    """Optional store/registry/readiness injection supports artifact-free API tests."""
    store = store or JobStore()
    router = APIRouter(prefix='/api/v4/simulation/jobs', tags=['NVMR regional simulation'])
    cache = IdleResultCache()

    def status(id):
        value = store.read(id)
        if value['config'].get('schemaVersion') != 'gsm-nvmr-regional-scenario/v1':
            error('JOB_NOT_FOUND', 'No regional job with this identity', 404)
        return value

    def result(id):
        status(id)
        value = cache.get(id, lambda: store.result(id))
        if value['schemaVersion'] != RESULT_SCHEMA:
            error('RESULT_SCHEMA_MISMATCH', 'Stored result is not a regional scenario')
        return value

    @router.post('', status_code=202)
    async def create(config: RegionalScenarioConfig):
        await asyncio.to_thread(require_simulation_headroom, config)
        await readiness(config, registry)
        return await asyncio.to_thread(store.create, config)

    @router.get('')
    def listing():
        return {'jobs': [job for job in store.statuses()
            if job['config'].get('schemaVersion') == 'gsm-nvmr-regional-scenario/v1']}

    @router.get('/{id}')
    def current_status(id: str):
        return status(id)

    @router.post('/{id}/cancel')
    def cancel(id: str):
        status(id)
        return store.cancel(id)

    @router.get('/{id}/result')
    def final(id: str, summary: bool = False):
        value = result(id)
        return regional_summary(value) if summary else value

    @router.get('/{id}/snapshot')
    def current(id: str, timeSeconds: float = Query(default=0, ge=0, allow_inf_nan=False)):
        return regional_snapshot(result(id), timeSeconds)

    @router.get('/{id}/routes/{ref}')
    def route(id: str, ref: str):
        for region in result(id)['regions']:
            value = region['routes'].get(ref)
            if value is not None:
                return {key: value for key, value in value.items() if key != 'cumulativeMeters'}
        error('ROUTE_UNAVAILABLE', 'No route in this immutable regional run', 404)

    @router.get('/{id}/bookings/{booking_id}')
    def selected_booking(id: str, booking_id: str):
        for region in result(id)['regions']:
            if any(booking['id'] == booking_id for booking in region['bookings']):
                return booking_detail(region, booking_id)
        error('BOOKING_NOT_FOUND', 'No such booking in this immutable regional run', 404)

    @router.get('/{id}/vehicles/{vehicle_id}')
    def selected_vehicle(id: str, vehicle_id: str,
                         timeSeconds: float = Query(default=0, ge=0, allow_inf_nan=False)):
        raw = result(id)
        projected = regional_snapshot(raw, timeSeconds)
        for vehicle in projected['vehicles']:
            if vehicle['id'] == vehicle_id:
                region = next(region for region in raw['regions'] if region['regionId'] == vehicle['regionId'])
                return {'schemaVersion': 'gsm-nvmr-regional-vehicle-detail/v1', 'runId': id,
                    'simulationTimeSeconds': projected['simulationTimeSeconds'], **vehicle,
                    'routingIdentity': region['routingIdentities'][vehicle['vehicleType']],
                    'booking': booking_detail(region, vehicle['activeBookingId']) if vehicle['activeBookingId'] else None}
        error('VEHICLE_NOT_FOUND', 'No such vehicle in this immutable regional run', 404)

    return router
