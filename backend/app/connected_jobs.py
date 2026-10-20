"""V5 connected world readiness, execution and persisted replay API."""
import asyncio
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time

import httpx
from fastapi import APIRouter, HTTPException, Query

from .config import PROJECT_ROOT, Settings
from .connected_context import connected_context
from .dataset import router_status
from .connected_simulation import (SCHEMA, RESULT_SCHEMA, REGION_ID, ConnectedScenarioConfig,
    connected_inputs, connected_snapshot, connected_summary, load_zones, simulate_connected, zone_at)
from .modes import routing_identity
from .integrity import digest
from .simulation_cache import IdleResultCache
from .connected_analytics import fleet_state_series
from .simulation_details import booking_detail
from .simulation_jobs import JobStore, error
from .simulation_resources import require_simulation_headroom


def verify_routing_validation(context, identity):
    """Completed independent routing acceptance belongs to this exact graph."""
    folder = context.routing_dir
    if (folder/'.validation-incomplete').exists():
        raise ValueError('Connected graph routing validation is incomplete')
    proof = json.loads((folder/'validation.json').read_text(encoding='utf-8'))
    if (proof['status'] != 'PASS' or proof['regionId'] != REGION_ID or
        proof['manifest_sha256'] != identity['graphManifestSha256'] or
        proof['validator_sha256'] != digest(PROJECT_ROOT/'scripts/validate_connected_routing.py') or
        not {'routing-validation.json', 'synthetic-validation.json'} <= set(proof.get('evidence_sha256', {}))):
        raise ValueError('Connected routing acceptance proof identity mismatch')
    for name, expected in proof['evidence_sha256'].items():
        if Path(name).name != name or digest(folder/name) != expected:
            raise ValueError('Connected routing acceptance evidence changed')
        evidence = json.loads((folder/name).read_text(encoding='utf-8'))
        if evidence.get('status') != 'PASS':
            raise ValueError('Connected routing evidence has not passed')
        if name == 'routing-validation.json' and (evidence.get('routingIdentity') != identity or
                evidence.get('mode') != identity['vehicleType']):
            raise ValueError('Connected routing evidence routing identity/mode mismatch')
        if name == 'synthetic-validation.json' and evidence.get('profile_sha256') != digest(PROJECT_ROOT/'profiles/motorbike.lua'):
            # The generated oracle compares CAR and MOTORBIKE semantics, and is
            # intentionally shared by both independent graph acceptance proofs.
            raise ValueError('Synthetic mode/turn oracle does not match the current motorcycle profile')
    return proof


async def connected_readiness(config, registry=None, cancelled=None):
    # Demand mode mix is independent of the fleet: a zero-fleet mode still needs
    # road/route evidence when that mode is requested by potential passengers.
    modes = set()
    if config.carCount or (config.bookingCount and config.demandCarFraction > 0):
        modes.add('CAR')
    if config.carCount < config.fleetSize or (config.bookingCount and config.demandCarFraction < 1):
        modes.add('MOTORBIKE')
    contexts, identities, failures = {}, {}, []
    for mode in sorted(modes):
        if cancelled and await cancelled():
            raise HTTPException(499, {'code': 'JOB_CANCELLED', 'message': 'Cancelled during connected readiness'})
        try:
            context = await asyncio.to_thread(connected_context, mode)
            from scripts.connected_gis import verify_graph
            await asyncio.to_thread(verify_graph, mode)
            identity = await asyncio.to_thread(routing_identity, context)
            if identity['regionId'] != REGION_ID or identity['vehicleType'] != mode:
                raise ValueError('Connected mode identity mismatch')
            await asyncio.to_thread(verify_routing_validation, context, identity)
            contexts[mode], identities[mode] = context, identity
            # Reuse the graph-specific immutable hint proof, independent of the
            # legacy GeoJSON-based dataset readiness path.
            if (await router_status(context))['state'] != 'connected':
                raise ValueError('Local OSRM service does not match its graph-specific router evidence')
        except (HTTPException, OSError, ValueError, KeyError, RuntimeError) as exc:
            failures.append({'vehicleType': mode, 'message': str(getattr(exc, 'detail', exc))})
    if failures:
        details = '; '.join(f'{failure["vehicleType"]}: {failure["message"]}' for failure in failures)
        raise HTTPException(503, {'code': 'CONNECTED_NOT_READY',
            'message': 'Connected routing evidence unavailable: '+details, 'modes': failures})
    await asyncio.to_thread(read_anchor_catalog, identities)
    return contexts, identities


def validate_anchor_catalog(raw, identities, config, config_sha256, snapped):
    """Bind catalog coordinates to the same frozen source/extract/config world."""
    expected = {'region_id': config['regionId'], 'config_sha256': config_sha256,
                'pipeline_version': config['pipelineVersion']}
    if (raw.get('identity') != expected or raw.get('sourceSha256') != config['source']['sha256'] or
        raw.get('boundaryVersion') != config['boundaryVersion'] or
        any(raw.get('extractSha256') != identity['extractSha256'] or
            raw.get('sourceSha256') != identity['sourceSha256'] for identity in identities.values())):
        raise ValueError('Anchor catalog source/extract/config/boundary identity mismatch')
    if snapped:
        if raw.get('schemaVersion') != 'connected-snapped-anchors/v1':
            raise ValueError('Unsupported snapped road catalog schema')
        if any(raw.get('routingIdentities', {}).get(mode) != identity for mode, identity in identities.items()):
            raise ValueError('Snapped anchors belong to a different routing graph')
        modes = raw.get('modes', {})
        if any(mode not in modes for mode in identities):
            raise ValueError('Snapped catalog lacks an active demand/fleet mode')
        entries = {mode: modes[mode] for mode in identities}
    else:
        if raw.get('schemaVersion') != 'connected-road-candidates/v1':
            raise ValueError('Unsupported raw road catalog schema')
        entries = dict.fromkeys(identities, raw.get('candidates', []))
    zones = config['operatingZones']
    pools = {}
    for mode, records in entries.items():
        points = []
        for entry in records:
            if not isinstance(entry, dict) or 'coordinate' not in entry or 'zoneId' not in entry:
                raise ValueError('Anchor record requires road coordinate and technical zone attribution')
            point = entry['coordinate']
            if (not isinstance(point, (list, tuple)) or len(point) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point) or
                zone_at(point, zones) != entry['zoneId'] or entry['zoneId'] == 'outside-operating-zones'):
                raise ValueError('Invalid/outside/incorrectly attributed road anchor')
            points.append(point)
        pools[mode] = points
    return pools


def read_anchor_catalog(identities, path=None):
    config_bytes = (PROJECT_ROOT/'config/connected-nvmr.json').read_bytes()
    config = json.loads(config_bytes)
    candidate = Path(path or PROJECT_ROOT/config['snappedAnchorCatalog'])
    snapped = candidate.is_file()
    if not snapped:
        candidate = PROJECT_ROOT/config['anchorCatalog']
    if not candidate.is_file():
        raise HTTPException(503, {'code': 'ANCHORS_NOT_READY', 'message': f'Missing connected road catalog: {candidate}'})
    if (candidate.parent/'.incomplete').exists():
        raise HTTPException(503, {'code': 'ANCHORS_INCOMPLETE', 'message': 'Connected road catalog preparation is incomplete'})
    try:
        raw_bytes = candidate.read_bytes()
        raw = json.loads(raw_bytes)
        manifest = json.loads((candidate.parent/'manifest.json').read_text(encoding='utf-8'))
        if (manifest.get('identity') != raw.get('identity') or
            manifest.get('source_sha256') != raw.get('sourceSha256') or
            manifest.get('extract_sha256') != raw.get('extractSha256') or
            manifest.get('artifact_sha256', {}).get(candidate.name) != hashlib.sha256(raw_bytes).hexdigest()):
            raise ValueError('Anchor content differs from its immutable checksum manifest')
        pools = validate_anchor_catalog(raw, identities, config, hashlib.sha256(config_bytes).hexdigest(), snapped)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, {'code': 'ANCHOR_IDENTITY_MISMATCH', 'message': str(exc)}) from exc
    return pools, {'catalogPath': str(candidate.relative_to(PROJECT_ROOT)),
        'catalogSha256': hashlib.sha256(raw_bytes).hexdigest(), 'preSnapped': snapped,
        'catalogProvenance': raw.get('provenance', {}), 'source': config['source'],
        'boundaryVersion': config['boundaryVersion']}


async def execute_connected_live(config, run_id, cancelled=None, progress=None, prepared=None):
    await asyncio.to_thread(require_simulation_headroom, config)
    begun = time.perf_counter()
    contexts, identities = await connected_readiness(config, cancelled=cancelled)
    zones = await asyncio.to_thread(load_zones)
    pools, provenance = await asyncio.to_thread(read_anchor_catalog, identities)
    vehicles, bookings, vmeta, bmeta = await asyncio.to_thread(connected_inputs, config, pools, zones)
    from .simulation_worker import RegionalInstrumentedTravel
    async with httpx.AsyncClient(timeout=max(Settings().osrm_timeout_seconds, 20), trust_env=False,
                                 limits=httpx.Limits(max_connections=2)) as client:
        travels = {mode: RegionalInstrumentedTravel(context, client) for mode, context in contexts.items()}
        if not provenance['preSnapped']:
            snapped, updated = {}, []
            for vehicle in vehicles:
                if cancelled and await cancelled():
                    raise HTTPException(499, {'code': 'JOB_CANCELLED', 'message': 'Cancelled during connected input preparation'})
                key = (vehicle.vehicleType, tuple(vehicle.position))
                if key not in snapped:
                    snapped[key] = await travels[vehicle.vehicleType].nearest(vehicle.position)
                position = tuple(snapped[key])
                if zone_at(position, zones) != vmeta[vehicle.id]['homeZoneId']:
                    raise HTTPException(503, {'code': 'ANCHOR_ZONE_MISMATCH', 'message': 'Snapping moved an initial vehicle outside its technical home zone'})
                updated.append(vehicle.model_copy(update={'position': position}))
            vehicles = updated
        if max(Counter(tuple(v.position) for v in vehicles).values(), default=0) > config.distribution.maximumVehiclesPerPosition:
            raise HTTPException(503, {'code': 'ANCHOR_DISTRIBUTION_COLLAPSE', 'message': 'Snapped anchors exceed configured position occupancy; rebuild verified catalog'})
        if prepared:
            prepared({'schemaVersion': 'gsm-nvmr-connected-input/v1', 'runId': run_id,
                'config': config.model_dump(mode='json'), 'routingIdentities': identities,
                'operatingZones': zones, 'provenance': provenance,
                'vehicles': [{**v.model_dump(mode='json'), **vmeta[v.id]} for v in vehicles],
                'bookings': [{**b.model_dump(mode='json'), **bmeta[b.id]} for b in bookings]})
        prep_ms = (time.perf_counter()-begun)*1000
        result = await simulate_connected(config, vehicles, bookings, travels, identities, run_id,
            zones, vmeta, bmeta, cancelled, progress)
        for mode, context in contexts.items():
            from scripts.connected_gis import verify_graph
            await asyncio.to_thread(verify_graph, mode)
            await asyncio.to_thread(verify_routing_validation, context, identities[mode])
            if await asyncio.to_thread(routing_identity, context) != identities[mode]:
                raise HTTPException(503, {'code': 'ROUTING_IDENTITY_CHANGED', 'message': 'Connected graph changed during run'})
        result['provenance'] = provenance
        result['metrics'].update(preparationMilliseconds=prep_ms, totalMilliseconds=(time.perf_counter()-begun)*1000,
            routing={mode: travel.telemetry() for mode, travel in travels.items()})
    return result


def create_connected_router(store=None, registry=None, readiness=connected_readiness):
    store = store or JobStore()
    router = APIRouter(prefix='/api/v5/simulation/jobs', tags=['Connected NVMR global simulation'])
    cache = IdleResultCache()
    analytics_cache = IdleResultCache(idle_seconds=300.)

    def status(id):
        value = store.read(id)
        if value['config'].get('schemaVersion') != SCHEMA:
            error('JOB_NOT_FOUND', 'No connected job with this identity', 404)
        return value

    def result(id):
        status(id)
        value = cache.get(id, lambda: store.result(id))
        if value['schemaVersion'] != RESULT_SCHEMA:
            error('RESULT_SCHEMA_MISMATCH', 'Stored result is not a connected simulation')
        return value

    @router.post('', status_code=202)
    async def create(config: ConnectedScenarioConfig):
        await asyncio.to_thread(require_simulation_headroom, config)
        await readiness(config, registry)
        return await asyncio.to_thread(store.create, config)

    @router.get('')
    def listing():
        return {'jobs': [job for job in store.statuses() if job['config'].get('schemaVersion') == SCHEMA]}

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
        return connected_summary(value) if summary else value

    @router.get('/{id}/snapshot')
    def current(id: str, timeSeconds: float = Query(default=0, ge=0, allow_inf_nan=False)):
        return connected_snapshot(result(id), timeSeconds)

    @router.get('/{id}/analytics/fleet-states')
    def fleet_states(id: str):
        status(id)  # Keep the same identity/lifecycle errors as persisted replay.
        try:
            return analytics_cache.get(id, lambda: fleet_state_series(result(id)))
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            error('CONNECTED_ANALYTICS_UNAVAILABLE', str(exc), 422)

    @router.get('/{id}/routes/{ref}')
    def route(id: str, ref: str):
        value = result(id)['routes'].get(ref)
        if value is None:
            error('ROUTE_UNAVAILABLE', 'No route in this immutable connected run', 404)
        return {key: value for key, value in value.items() if key != 'cumulativeMeters'}

    @router.get('/{id}/bookings/{booking_id}')
    def selected_booking(id: str, booking_id: str):
        return booking_detail(result(id), booking_id)

    @router.get('/{id}/vehicles/{vehicle_id}')
    def selected_vehicle(id: str, vehicle_id: str, timeSeconds: float = Query(default=0, ge=0, allow_inf_nan=False)):
        raw = result(id)
        projected = connected_snapshot(raw, timeSeconds)
        vehicle = next((v for v in projected['vehicles'] if v['id'] == vehicle_id), None)
        if vehicle is None:
            error('VEHICLE_NOT_FOUND', 'No such vehicle in this immutable connected run', 404)
        return {'schemaVersion': 'gsm-nvmr-connected-vehicle-detail/v1', 'runId': id,
            'simulationTimeSeconds': projected['simulationTimeSeconds'], **vehicle,
            'routingIdentity': raw['routingIdentities'][vehicle['vehicleType']],
            'booking': booking_detail(raw, vehicle['activeBookingId']) if vehicle['activeBookingId'] else None}

    return router
