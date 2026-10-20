import math
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pydantic import ValidationError

from .config import Settings
from .dataset import dataset_status, artifact_status, pbf_status, public_region_status
from .regions import RegionRegistry, default_registry
from .schemas import RouteRequest, RouteResponse, SnapPoint
from .fleet import candidate_catalog
from .booking import PrepareRequest, ScenarioPlan, LocalTravel, build_plan
from .voucher import ExperimentRequest, prepare_experiment
from .modes import resolve_mode, routing_identity
from .multimodal import MixedRequest, mode_catalog, prepare_mixed


def api_error(code, message, status=503):
    raise HTTPException(status, detail={"code": code, "message": message})


def meters(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, h)))


def create_app(settings: Settings | None = None, registry: RegionRegistry | None = None, connected_map_root=None):
    settings = settings or Settings()
    settings.region  # Fail early for invalid configuration, never for a missing PBF.
    app = FastAPI(title="GSM Map Sandbox", version="0.1.0")
    from .simulation_jobs import create_router
    app.include_router(create_router())
    preparation_lock = asyncio.Semaphore(2)
    registry = registry or default_registry(settings)
    from .regional_jobs import create_regional_router
    app.include_router(create_regional_router(registry=registry))
    from .connected_jobs import create_connected_router
    app.include_router(create_connected_router())
    from .connected_assets import create_connected_map_router
    app.include_router(create_connected_map_router() if connected_map_root is None else create_connected_map_router(connected_map_root, portable=True))
    settings = registry.resolve("hcm-center")  # Pin legacy requests to the same immutable HCM snapshot.

    @app.exception_handler(HTTPException)
    async def structured_error(_, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": exc.detail}
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.url.path.startswith(('/api/v3/simulation/', '/api/v4/simulation/', '/api/v5/simulation/')):
            return JSONResponse(status_code=422, content={"error": {"code": "INVALID_SIMULATION_CONFIG", "message": "Simulation config hoặc thời điểm snapshot ngoài giới hạn của contract."}})
        if request.url.path.endswith("/voucher-experiment/prepare"):
            return JSONResponse(status_code=422, content={"error": {"code": "INVALID_EXPERIMENT_CONFIG", "message": "Config fare, behavior, voucher hoặc scenario ngoài giới hạn PoC."}})
        if request.url.path.endswith("/booking-simulation/prepare"):
            return JSONResponse(status_code=422, content={"error": {"code": "INVALID_SCENARIO_CONFIG", "message": "Cần seed, 1–10 xe, 10–30 bookings, horizon 60–3600 s, maxWait 10–900 s và preset hợp lệ."}})
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_COORDINATES", "message": "Expected start/end as finite WGS84 [longitude, latitude], with no extra fields."}})

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "backend_ready": True, "version": "0.1.0"}

    @app.get("/api/dataset/status")
    async def status():
        return await dataset_status(settings)

    @app.get("/api/fleet/candidates")
    async def fleet_candidates():
        if not (await dataset_status(settings))["ready"]:
            api_error("DATASET_NOT_READY", "Bản đồ hoặc OSRM local chưa sẵn sàng cho fleet.")
        try:
            result = candidate_catalog(settings)
            if len(result["candidates"]) < 2:
                api_error("INSUFFICIENT_CANDIDATES", "Không đủ điểm OSM trong vùng hiển thị.")
            return result
        except (OSError, ValueError, KeyError, TypeError):
            api_error("CANDIDATES_UNAVAILABLE", "Không đọc được candidate/provenance local.")

    @app.get("/api/map/streets")
    async def streets():
        if not settings.map_path.is_file():
            api_error("DATASET_NOT_READY", "GeoJSON local chưa được tạo.")
        return FileResponse(settings.map_path, media_type="application/geo+json")

    @app.get("/api/map/{layer}")
    async def map_layer(layer: str):
        if layer not in {"water", "green", "buildings", "places"}:
            api_error("UNKNOWN_MAP_LAYER", "Lớp bản đồ không hợp lệ.", 404)
        path = settings.map_path.parent / f"{layer}.geojson"
        if not path.is_file():
            api_error("DATASET_NOT_READY", "Lớp GeoJSON chưa sẵn sàng.")
        return FileResponse(path, media_type="application/geo+json")

    async def calculate_route(request: RouteRequest, router_client=None, selected=None):
        selected = selected or settings
        w, s, e, n = getattr(selected, "routing_bbox", selected.region.routing_bbox)
        if any(not (w <= lon <= e and s <= lat <= n) for lon, lat in (request.start, request.end)):
            api_error("OUTSIDE_ROUTING_REGION", "Điểm nằm ngoài vùng routing đã cấu hình.", 422)
        if request.start == request.end:
            api_error("IDENTICAL_POINTS", "Chọn hai điểm khác nhau.", 422)
        inputs_ready = await asyncio.to_thread(lambda: pbf_status(selected)["format_verified"] and artifact_status(selected)["graph_ready"])
        if not inputs_ready:
            api_error("DATASET_NOT_READY", "Chưa có PBF đọc được và OSRM graph MLD đã chuẩn bị.")
        coords = ";".join(f"{lon},{lat}" for lon, lat in (request.start, request.end))
        try:
            async def query(client):
                return await client.get(f"{selected.osrm_base_url}/route/v1/driving/{coords}", params={"geometries": "geojson", "overview": "full", "steps": "false", "radiuses": f"{selected.max_snap_meters};{selected.max_snap_meters}"})
            if router_client is not None:
                response = await query(router_client)
            else:
                async with httpx.AsyncClient(timeout=selected.osrm_timeout_seconds, trust_env=False) as client:
                    response = await query(client)
            data = response.json()
            if data.get("code") in {"NoRoute", "NoSegment"}:
                message = ('Không tìm thấy tuyến MOTORBIKE hoặc điểm snap phù hợp.'
                           if getattr(selected,'vehicle_type','CAR')=='MOTORBIKE'
                           else 'Không tìm thấy tuyến ô tô hoặc điểm snap phù hợp.')
                api_error(data["code"].upper(), message, 422)
            response.raise_for_status()
            if data.get("code") != "Ok":
                api_error("ROUTER_BAD_RESPONSE", "OSRM trả về phản hồi không hợp lệ.", 502)
            result = data["routes"][0]
            if result["geometry"].get("type") != "LineString":
                api_error("ROUTER_BAD_RESPONSE", "OSRM geometry phải là LineString.", 502)
            snaps = [SnapPoint(**point) for point in data["waypoints"]]
            if any(point.distance > selected.max_snap_meters for point in snaps):
                api_error("SNAP_TOO_FAR", "Điểm snap quá xa vị trí đã chọn.", 422)
            validated = RouteResponse(coordinates=result["geometry"]["coordinates"], distance=result["distance"], duration=result["duration"], snap_points=snaps)
            if getattr(selected,'vehicle_type','CAR')=='MOTORBIKE':
                validated=validated.model_copy(update={'duration_source':'OSRM motorbike profile model estimate; uncalibrated; not live traffic'})
            if len(set(validated.coordinates)) < 2 or any(meters(p, snap.location) > 5 for p, snap in zip([validated.coordinates[0], validated.coordinates[-1]], snaps)):
                api_error("ROUTER_BAD_RESPONSE", "Geometry không khớp điểm snap hoặc không có độ dài.", 502)
            if any(meters(p, snap.location) > selected.max_snap_meters + 1 for p, snap in zip([request.start, request.end], snaps)):
                api_error("SNAP_TOO_FAR", "Tọa độ snap quá xa điểm đã chọn.", 422)
            if any(not (w <= lon <= e and s <= lat <= n) for lon, lat in [*validated.coordinates, *(p.location for p in snaps)]):
                api_error("ROUTE_OUTSIDE_REGION", "Tuyến vượt vùng routing; cần kiểm tra buffer.", 502)
            return validated
        except httpx.TimeoutException:
            api_error("ROUTER_TIMEOUT", "OSRM local phản hồi quá thời gian cho phép.")
        except httpx.HTTPError:
            api_error("ROUTER_UNAVAILABLE", "Không kết nối được OSRM local.")
        except (ValueError, KeyError, IndexError, TypeError, ValidationError, AttributeError):
            api_error("ROUTER_BAD_RESPONSE", "OSRM trả về dữ liệu tuyến không hợp lệ.", 502)

    @app.post("/api/route", response_model=RouteResponse)
    async def route(request: RouteRequest):
        return await calculate_route(request)

    async def build_booking(config, request, selected):
        if not (await dataset_status(selected))["ready"]:
            api_error("DATASET_NOT_READY", "Cần dữ liệu bản đồ và OSRM local sẵn sàng.")
        async with preparation_lock:
            try:
                catalog = candidate_catalog(selected)
                async with httpx.AsyncClient(timeout=selected.osrm_timeout_seconds, trust_env=False) as client:
                    async def fetch_route(route_request):
                        return await calculate_route(route_request, client, selected)
                    return await build_plan(catalog, config, LocalTravel(selected, fetch_route, meters, client), request.is_disconnected)
            except (OSError, KeyError, ValueError, TypeError):
                api_error("INVALID_SCENARIO_PLAN", "Không xác minh được candidate, ETA hoặc scenario plan.", 502)

    async def build_voucher(config, request, selected):
        if not (await dataset_status(selected))["ready"]:
            api_error("DATASET_NOT_READY", "Cần dữ liệu bản đồ và OSRM local sẵn sàng.")
        async with preparation_lock:
            try:
                catalog = candidate_catalog(selected)
                async with httpx.AsyncClient(timeout=selected.osrm_timeout_seconds, trust_env=False) as client:
                    async def fetch_route(route_request):
                        return await calculate_route(route_request, client, selected)
                    return await prepare_experiment(catalog, config, LocalTravel(selected, fetch_route, meters, client), request.is_disconnected)
            except (OSError, KeyError, ValueError, TypeError):
                api_error("INVALID_EXPERIMENT_PLAN", "Không xác minh được paired experiment hoặc ledger.", 502)

    @app.post("/api/booking-simulation/prepare", response_model=ScenarioPlan)
    async def prepare_booking(config: PrepareRequest, request: Request):
        return await build_booking(config, request, settings)

    @app.post("/api/voucher-experiment/prepare")
    async def prepare_voucher(config: ExperimentRequest, request: Request):
        return await build_voucher(config, request, settings)

    async def require_region(region_id, *, map_only=False):
        context = registry.resolve(region_id)
        if map_only:
            if not context.enabled or context.render_bbox is None or not artifact_status(context)["map_ready"]:
                api_error("REGION_NOT_READY", context.unavailable_reason or "Bản đồ khu vực chưa sẵn sàng.")
            return context
        status = await public_region_status(context)
        if not status["ready"]:
            if artifact_status(context)['graph_ready']:
                if status['osrm']['state'] == 'unavailable':
                    api_error('ROUTER_UNAVAILABLE', 'Không kết nối được OSRM CAR của khu vực.')
                if status['osrm']['state'] == 'identity_mismatch':
                    api_error('ROUTER_IDENTITY_MISMATCH', 'OSRM không khớp graph đã kiểm chứng của khu vực.')
            api_error("REGION_NOT_READY", status["readinessReason"])
        return context

    @app.get("/api/regions")
    async def regions():
        statuses = await asyncio.gather(*(public_region_status(c) for c in registry.contexts.values()))
        return {"defaultRegionId": "hcm-center", "regions": [
            {"id": c.id, "label": c.region.name, "viewport": status["viewport"],
             "coverage": status["coverage"], "ready": status["ready"], "mapReady": status["artifacts"]["map_ready"],
             "state": status["state"], "reason": status["readinessReason"]}
            for c, status in zip(registry.contexts.values(), statuses)]}

    async def require_mode(region_id, vehicle_type):
        context = resolve_mode(registry, region_id, vehicle_type)
        status = await public_region_status(context)
        if not status['ready']:
            code = 'MODE_NOT_READY'
            if artifact_status(context)['graph_ready']:
                code = 'ROUTER_IDENTITY_MISMATCH' if status['osrm']['state']=='identity_mismatch' else 'ROUTER_UNAVAILABLE'
            api_error(code, f'{vehicle_type}: dữ liệu/profile/router chưa sẵn sàng.')
        return context

    @app.get('/api/v2/regions/{region_id}/modes')
    async def modes(region_id: str):
        registry.resolve(region_id)
        result=[]
        for mode in ('CAR','MOTORBIKE'):
            try:
                context=resolve_mode(registry,region_id,mode)
                status=await public_region_status(context)
                result.append({'vehicleType':mode,'ready':status['ready'],
                    'reason':status['readinessReason'] if mode=='CAR' else ('' if status['ready'] else 'MOTORBIKE chưa được kiểm chứng/sẵn sàng.'),
                    'routingIdentity':routing_identity(context) if status['ready'] else None})
            except HTTPException as exc:
                result.append({'vehicleType':mode,'ready':False,'reason':exc.detail['message'],'routingIdentity':None})
        return {'regionId':region_id,'modes':result}

    @app.post('/api/v2/regions/{region_id}/modes/{vehicle_type}/route')
    async def mode_route(region_id: str, vehicle_type: str, config: RouteRequest):
        context=await require_mode(region_id,vehicle_type)
        identity=routing_identity(context)
        result=await calculate_route(config,selected=context)
        if routing_identity(context)!=identity:
            api_error('ROUTING_IDENTITY_CHANGED','Graph đã đổi trong khi tính tuyến; hãy thử lại.')
        return {'schemaVersion':'gsm-mode-route/v1','routingIdentity':identity,'route':result}

    @app.get('/api/v2/regions/{region_id}/modes/{vehicle_type}/candidates')
    async def mode_candidates(region_id: str, vehicle_type: str):
        context=await require_mode(region_id,vehicle_type)
        return await asyncio.to_thread(mode_catalog,context)

    @app.post('/api/v2/regions/{region_id}/booking-simulation/prepare')
    async def mixed_booking(region_id: str, config: MixedRequest, request: Request):
        modes=sorted(set(config.vehicleTypes+config.serviceTypes))
        contexts={m:await require_mode(region_id,m) for m in modes}
        async with preparation_lock:
            async with httpx.AsyncClient(timeout=settings.osrm_timeout_seconds,trust_env=False) as client:
                def travel_for(context):
                    async def fetch(config): return await calculate_route(config,client,context)
                    return LocalTravel(context,fetch,meters,client)
                return await prepare_mixed(config,contexts,{m:travel_for(c) for m,c in contexts.items()},request.is_disconnected)

    @app.get("/api/regions/{region_id}/dataset/status")
    async def region_status(region_id: str):
        return await public_region_status(registry.resolve(region_id))

    @app.get("/api/regions/{region_id}/map/{layer}")
    async def region_map(region_id: str, layer: str):
        context = registry.resolve(region_id)
        if layer not in {"streets", "water", "green", "buildings", "places"}:
            api_error("UNKNOWN_MAP_LAYER", "Lớp bản đồ không hợp lệ.", 404)
        context = await require_region(region_id, map_only=True)
        path = context.map_path.parent / f"{layer}.geojson"
        if not path.is_file():
            api_error("REGION_NOT_READY", "Lớp bản đồ của khu vực chưa sẵn sàng.")
        return FileResponse(path, media_type="application/geo+json")

    @app.get("/api/regions/{region_id}/fleet/candidates")
    async def region_candidates(region_id: str):
        context = await require_region(region_id)
        try:
            result = candidate_catalog(context)
            if len(result["candidates"]) < 2:
                api_error("INSUFFICIENT_CANDIDATES", "Không đủ điểm OSM trong vùng hoạt động.")
            return result
        except (OSError, ValueError, KeyError, TypeError):
            api_error("CANDIDATES_UNAVAILABLE", "Không đọc được candidate/provenance của khu vực.")

    @app.post("/api/regions/{region_id}/route", response_model=RouteResponse)
    async def region_route(region_id: str, config: RouteRequest):
        context = await require_region(region_id)
        return await calculate_route(config, selected=context)

    @app.post("/api/regions/{region_id}/booking-simulation/prepare", response_model=ScenarioPlan)
    async def region_booking(region_id: str, config: PrepareRequest, request: Request):
        return await build_booking(config, request, await require_region(region_id))

    @app.post("/api/regions/{region_id}/voucher-experiment/prepare")
    async def region_voucher(region_id: str, config: ExperimentRequest, request: Request):
        return await build_voucher(config, request, await require_region(region_id))

    return app


app = create_app()
