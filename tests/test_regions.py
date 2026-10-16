"""M1a synthetic namespaces/graphs + mocked local OSRM; no Hanoi GIS evidence."""
import asyncio
import json
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.regions import RegionRegistry, default_registry, FrozenRegion
from backend.app.dataset import public_region_status
from backend.app.main import create_app, meters
from backend.app.fleet import candidate_catalog
from backend.app.booking import LocalTravel
from backend.app.schemas import RouteResponse


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def registry(tmp_path):
    original = default_registry(Settings()).resolve("hcm-center")
    contexts = {}
    for region_id, west, south, port in [("hcm-center", 106.6, 10.7, 5101), ("nvmr-hanoi-core", 105.7, 21.0, 5102)]:
        base = tmp_path / region_id
        region = FrozenRegion.model_validate({**original.region.model_dump(), "name": region_id,
            "display_bbox": (west, south, west+.2, south+.2), "routing_buffer_degrees": .02})
        context = replace(original, id=region_id, region=region, viewport_center=(west+.1, south+.1),
            operating_bbox=region.display_bbox, routing_bbox=region.routing_bbox, render_bbox=region.display_bbox,
            map_path=base/"processed/render/streets.geojson", pbf_path=base/"source.osm.pbf",
            routing_dir=base/"routing", extracted_path=base/"extracted/coverage.osm.pbf",
            graph_basename=region_id, osrm_base_url=f"http://127.0.0.1:{port}")
        context.pbf_path.parent.mkdir(parents=True, exist_ok=True)
        context.pbf_path.write_bytes(b"SYNTHETIC TEST ONLY - NOT PBF")
        stat = context.pbf_path.stat()
        write_json(context.map_path.parent.parent/"source-verification.json", {
            "path": str(context.pbf_path), "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "format_verified": True})
        points = [[west+.05+x*.02, south+.05+y*.025] for x in range(6) for y in range(4)]
        layers = {}
        for layer in ("streets", "water", "green", "buildings", "places"):
            path = context.map_path.parent/f"{layer}.geojson"
            write_json(path, {"type": "FeatureCollection", "features": [{"type": "Feature", "id": region_id,
                "properties": {"highway": "residential", "name": region_id},
                "geometry": {"type": "LineString", "coordinates": points}}]})
            layers[path.name] = {"features": 1, "size_bytes": path.stat().st_size}
        write_json(context.map_path.parent/"manifest.json", {"display_bbox": region.display_bbox, "layers": layers})
        context.routing_dir.mkdir(parents=True)
        sizes = {}
        for suffix in ("partition", "cells", "mldgr"):
            path = context.routing_dir/f"{region_id}.osrm.{suffix}"
            path.write_bytes(b"SYNTHETIC TEST ONLY - NOT GRAPH")
            sizes[path.name] = path.stat().st_size
        write_json(context.routing_dir/"manifest.json", {"algorithm": "mld", "profile": "car",
            "routing_bbox": context.routing_bbox, "image_digest": "synthetic-image", "profile_sha256": "synthetic-profile",
            "extract_sha256": f"synthetic-{region_id}", "artifact_sizes": sizes})
        contexts[region_id] = context
    return RegionRegistry(contexts)


@pytest.fixture
def mock_router(monkeypatch, registry):
    real_client = httpx.AsyncClient
    calls = []

    async def handle(request):
        await asyncio.sleep(.001)  # Ensure interleaving rather than sequential request proof.
        context = registry.resolve("hcm-center" if request.url.port == 5101 else "nvmr-hanoi-core")
        service = request.url.path.split('/')[1]
        points = [tuple(map(float, point.split(','))) for point in request.url.path.rsplit('/', 1)[-1].split(';')]
        w, s, e, n = context.routing_bbox
        assert all(w <= lon <= e and s <= lat <= n for lon, lat in points), "Cross-region router request"
        calls.append((context.id, service, points))
        waypoints = [{"location": point, "distance": 0, "name": context.id} for point in points]
        if service == "nearest":
            data = {"code": "Ok", "waypoints": waypoints}
        elif service == "table":
            data = {"code": "Ok", "durations": [[10] for _ in points[:-1]], "sources": waypoints[:-1], "destinations": waypoints[-1:]}
        else:
            data = {"code": "Ok", "waypoints": waypoints,
                "routes": [{"distance": 1000, "duration": 30, "geometry": {"type": "LineString", "coordinates": points}}]}
        return httpx.Response(200, json=data)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw))
    return real_client, calls


def semantic(value):
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items() if k not in {"createdAt", "preparationMilliseconds"}}
    if isinstance(value, list):
        return [semantic(v) for v in value]
    return value


def test_registry_is_immutable_and_snapshots_settings():
    settings = Settings()
    registry = default_registry(settings)
    hcm = registry.resolve("hcm-center")
    before = hcm.osrm_base_url
    settings.osrm_base_url = "http://localhost:5999"
    assert hcm.osrm_base_url == before
    with pytest.raises(FrozenInstanceError):
        hcm.id = "other"
    with pytest.raises(ValidationError):
        hcm.region.name = "other"
    with pytest.raises(TypeError):
        registry.contexts["other"] = hcm


def test_unconfigured_hanoi_not_ready_and_public_metadata_redacted():
    original = default_registry(Settings())
    # Preserve M1a unavailable-region assertions independently of local M1b data.
    unavailable = replace(original.resolve('nvmr-hanoi-core'), enabled=False,
        operating_bbox=None, routing_bbox=None, render_bbox=None, unavailable_reason='M1b data not prepared fixture')
    registry = RegionRegistry({**original.contexts, unavailable.id: unavailable})
    hanoi = registry.resolve("nvmr-hanoi-core")
    status = asyncio.run(public_region_status(hanoi))
    assert not status["ready"] and not status["artifacts"]["map_ready"]
    assert status["coverage"] == {"operating": None, "routing": None, "render": None}
    assert "M1b" in status["readinessReason"]
    client = TestClient(create_app(registry=registry))
    payload = client.get('/api/regions').json()
    assert payload["defaultRegionId"] == "hcm-center"
    assert [r["id"] for r in payload["regions"]] == ["hcm-center", "nvmr-hanoi-core"]
    text = json.dumps(payload)
    assert "127.0.0.1" not in text and "data/" not in text and "TIEN DAT" not in text
    for path in ('route', 'booking-simulation/prepare', 'voucher-experiment/prepare'):
        config = {"start": [105.8, 21.0], "end": [105.85, 21.05]} if path == 'route' else {}
        response = client.post(f'/api/regions/nvmr-hanoi-core/{path}', json=config)
        assert response.status_code == 503 and response.json()['error']['code'] == 'REGION_NOT_READY'
    for path in ('map/streets', 'fleet/candidates'):
        assert client.get(f'/api/regions/nvmr-hanoi-core/{path}').json()['error']['code'] == 'REGION_NOT_READY'


@pytest.mark.parametrize('path,method', [('dataset/status','get'), ('map/streets','get'), ('fleet/candidates','get'),
    ('route','post'), ('booking-simulation/prepare','post'), ('voucher-experiment/prepare','post')])
def test_unknown_region_never_falls_back(path, method):
    client = TestClient(create_app())
    options = {"json": {"start": [106.69, 10.77], "end": [106.7, 10.78]} if path == 'route' else {}} if method == 'post' else {}
    response = getattr(client, method)(f'/api/regions/unknown/{path}', **options)
    assert response.status_code == 404 and response.json()['error']['code'] == 'UNKNOWN_REGION'


def test_legacy_strict_schema_and_hcm_explicit_parity(registry, mock_router):
    client = TestClient(create_app(registry=registry))
    context = registry.resolve('hcm-center')
    catalog = client.get('/api/fleet/candidates').json()
    assert catalog == client.get('/api/regions/hcm-center/fleet/candidates').json()
    legacy_settings = SimpleNamespace(**{key: getattr(context, key) for key in
        ('region', 'map_path', 'routing_dir', 'osrm_base_url', 'max_snap_meters')})
    assert candidate_catalog(legacy_settings) == candidate_catalog(context)  # Fingerprint byte inputs unchanged.
    start, end = [c['coordinate'] for c in catalog['candidates'][:2]]
    for path, config in [('route', {'start': start, 'end': end}),
                         ('booking-simulation/prepare', {}), ('voucher-experiment/prepare', {})]:
        old = client.post(f'/api/{path}', json=config)
        new = client.post(f'/api/regions/hcm-center/{path}', json=config)
        assert old.status_code == new.status_code == 200, (old.text, new.text)
        assert semantic(old.json()) == semantic(new.json())
        bad = client.post(f'/api/{path}', json={**config, 'regionId': 'nvmr-hanoi-core'})
        assert bad.status_code == 422
    status = client.get('/api/regions/hcm-center/dataset/status').json()
    assert 'path' not in status['pbf'] and 'url' not in status['osrm']


def test_concurrent_region_routes_preparations_assets_and_cache_isolated(registry, mock_router):
    real_client, calls = mock_router
    app = create_app(registry=registry)

    async def run():
        async with real_client(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            async def scenario(region_id):
                base = f'/api/regions/{region_id}'
                catalog = (await client.get(base+'/fleet/candidates')).json()
                asset = (await client.get(base+'/map/streets')).json()
                booking, voucher = await asyncio.gather(
                    client.post(base+'/booking-simulation/prepare', json={'fleetSize': 2, 'bookingCount': 10}),
                    client.post(base+'/voucher-experiment/prepare', json={'fleetSize': 2, 'potentialCount': 10}))
                assert booking.status_code == voucher.status_code == 200, (booking.text, voucher.text)
                return catalog, asset, booking.json(), voucher.json()
            return await asyncio.gather(scenario('hcm-center'), scenario('nvmr-hanoi-core'))

    hcm, hanoi = asyncio.run(run())
    assert hcm[0]['datasetFingerprint'] != hanoi[0]['datasetFingerprint']
    for region_id, result in zip(('hcm-center', 'nvmr-hanoi-core'), (hcm, hanoi)):
        catalog, asset, plan, experiment = result
        assert asset['features'][0]['id'] == region_id
        assert plan['datasetFingerprint'] == experiment['datasetFingerprint'] == catalog['datasetFingerprint']
        assert plan['provenance'] == catalog['provenance']
        assert experiment['baseline']['plan']['vehicles'] == experiment['treatment']['plan']['vehicles']
        w, s, e, n = registry.resolve(region_id).operating_bbox
        assert all(w <= v['initialPosition'][0] <= e and s <= v['initialPosition'][1] <= n for v in plan['vehicles'])
    assert {region_id for region_id, _, _ in calls} == {'hcm-center', 'nvmr-hanoi-core'}


def test_new_region_routes_use_routing_coverage_not_viewport(registry):
    hanoi = registry.resolve('nvmr-hanoi-core')
    w, s, e, n = hanoi.region.display_bbox
    points = [(w+.05, s+.05), (w-.01, s+.05), (w+.06, s+.06)]
    route = RouteResponse(coordinates=points, distance=100, duration=10,
        snap_points=[{'location': points[0], 'distance': 0}, {'location': points[-1], 'distance': 0}])

    async def fetch(_):
        return route

    assert asyncio.run(LocalTravel(hanoi, fetch, meters).route(points[0], points[-1])) == route
    with pytest.raises(HTTPException) as error:
        asyncio.run(LocalTravel(replace(hanoi, id='hcm-center'), fetch, meters).route(points[0], points[-1]))
    assert error.value.detail['code'] == 'ROUTE_OUTSIDE_DISPLAY'
