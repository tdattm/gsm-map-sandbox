import json
import shutil
import asyncio

import httpx
from .config import Settings
from .integrity import region_integrity, digest

GRAPH_FILES = ("hcm-center.osrm.partition", "hcm-center.osrm.cells", "hcm-center.osrm.mldgr")


def pbf_status(settings: Settings):
    path = settings.pbf_path
    state, size = "missing_pbf", None
    if not str(path).lower().endswith(".osm.pbf"):
        state = "invalid_extension"
    else:
        try:
            if path.exists():
                # Only open and read one byte; do not load the national PBF into RAM.
                with path.open("rb") as stream:
                    first = stream.read(1)
                size = path.stat().st_size
                state = "present_unverified" if first else "empty_pbf"
        except OSError:
            state = "unreadable_pbf"
    verified, verification = False, None
    if state == "present_unverified":
        try:
            verification = json.loads((settings.map_path.parent.parent / "source-verification.json").read_text(encoding="utf-8"))
            stat = path.stat()
            verified = (verification.get("path") == str(path) and verification.get("size_bytes") == stat.st_size
                        and verification.get("mtime_ns") == stat.st_mtime_ns and verification.get("format_verified") is True)
        except (OSError, ValueError, AttributeError):
            pass
    # Verification is cached for this size/mtime; checksums are rechecked by the pipeline/audit, not each HTTP request.
    return {"state": "present_verified" if verified else state, "path": str(path), "size_bytes": size,
            "format_verified": verified, "verification": verification if verified else None,
            "osmium_available": shutil.which("osmium") is not None, "osmium_transport": "docker" if verified else None}


def artifact_status(settings: Settings):
    if getattr(settings, 'vehicle_type', 'CAR') == 'MOTORBIKE':
        from .modes import motor_artifacts
        return motor_artifacts(settings)
    basename = getattr(settings, "graph_basename", "hcm-center")
    required = tuple(f"{basename}.osrm.{suffix}" for suffix in ("partition", "cells", "mldgr"))
    routing_bbox = getattr(settings, "routing_bbox", settings.region.routing_bbox)
    render_bbox = getattr(settings, "render_bbox", settings.region.display_bbox)
    graph_files = all((settings.routing_dir / name).is_file() for name in required)
    manifest_path = settings.routing_dir / "manifest.json"
    manifest = None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        graph_files = graph_files and manifest.get("algorithm") == "mld" and manifest.get("profile") == "car"
        graph_files = graph_files and routing_bbox is not None and manifest.get("routing_bbox") == list(routing_bbox)
        graph_files = graph_files and bool(manifest.get("image_digest")) and set(required) <= set(manifest.get("artifact_sizes", {}))
    except (OSError, ValueError, TypeError, AttributeError):
        graph_files = False
    if (settings.routing_dir / ".incomplete").exists():
        graph_files = False
    if graph_files:
        try:
            sizes = manifest["artifact_sizes"]
            graph_files = isinstance(sizes, dict) and all(
                name.startswith(f"{basename}.osrm.") and "/" not in name and "\\" not in name
                and isinstance(size, int) and size > 0 and (settings.routing_dir / name).is_file()
                and (settings.routing_dir / name).stat().st_size == size for name, size in sizes.items())
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            graph_files = False
    map_ready, map_manifest = False, None
    try:
        map_manifest = json.loads((settings.map_path.parent / "manifest.json").read_text(encoding="utf-8"))
        map_ready = (render_bbox is not None and map_manifest.get("display_bbox") == list(render_bbox)
                     and map_manifest["layers"]["streets.geojson"]["features"] > 0
                     and all(name in {"streets.geojson", "water.geojson", "green.geojson", "buildings.geojson", "places.geojson"}
                             and (settings.map_path.parent / name).is_file() and (settings.map_path.parent / name).stat().st_size == entry["size_bytes"]
                             for name, entry in map_manifest["layers"].items()))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    if getattr(settings, "artifact_identity", None):
        source = pbf_status(settings).get("verification")
        valid_map, valid_graph = region_integrity(settings, source, map_manifest, manifest)
        map_ready, graph_files = map_ready and valid_map, graph_files and valid_graph
    return {"map_ready": map_ready, "map_manifest": map_manifest,
            "graph_ready": bool(graph_files), "routing_manifest": manifest,
            "extracted_ready": getattr(settings, "extracted_path", settings.routing_dir.parent / "extracted/hcm-center.osm.pbf").is_file()}


async def router_status(settings: Settings):
    w, s, e, n = settings.region.display_bbox
    try:
        async with httpx.AsyncClient(timeout=settings.osrm_timeout_seconds, trust_env=False) as client:
            response = await client.get(f"{settings.osrm_base_url}/nearest/v1/driving/{(w+e)/2},{(s+n)/2}", params={"number": 1})
            response.raise_for_status()
            data = response.json()
        valid = (data.get("code") == "Ok" and isinstance(data.get("waypoints"), list) and len(data["waypoints"]) >= 1)
        if valid and getattr(settings, "artifact_identity", None):
            # The serve command first validates the container image/command/mount,
            # then records graph-specific hints. A different graph fails these probes.
            evidence = json.loads((settings.routing_dir/'router-evidence.json').read_text(encoding='utf-8'))
            valid = (evidence['identity'] == settings.artifact_identity
                     and evidence['manifest_sha256'] == digest(settings.routing_dir/'manifest.json')
                     and len(evidence['probes']) >= 3)
            async with httpx.AsyncClient(timeout=settings.osrm_timeout_seconds, trust_env=False) as client:
                for probe in evidence['probes']:
                    point = probe['point']
                    response = await client.get(f'{settings.osrm_base_url}/nearest/v1/driving/{point[0]},{point[1]}')
                    response.raise_for_status()
                    waypoint = response.json()['waypoints'][0]
                    valid = valid and waypoint['hint'] == probe['hint'] and waypoint['location'] == probe['location']
            if not valid:
                return {"state": "identity_mismatch", "url": settings.osrm_base_url}
        return {"state": "connected" if valid else "no_segment", "url": settings.osrm_base_url}
    except (httpx.HTTPError, OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        return {"state": "unavailable", "url": settings.osrm_base_url}


async def dataset_status(settings: Settings):
    # Cold checksum reads must not block other requests' OSRM response timers.
    pbf, artifacts = await asyncio.to_thread(lambda: (pbf_status(settings), artifact_status(settings)))
    router = await router_status(settings)
    artifacts["graph_built"] = artifacts["graph_ready"]
    artifacts["graph_ready"] = artifacts["graph_built"] and router["state"] == "connected"
    ready = pbf["format_verified"] and artifacts["map_ready"] and artifacts["graph_ready"]
    state = "ready" if ready else (pbf["state"] if pbf["state"] not in {"present_unverified", "present_verified"} else "artifacts_pending")
    return {"state": state, "ready": ready, "pbf": pbf, "artifacts": artifacts,
            "osrm": router, "region": {**settings.region.model_dump(), "routing_bbox": settings.region.routing_bbox}}


async def public_region_status(context):
    """Only the new API uses this redacted shape. Legacy status stays unchanged."""
    configured = context.enabled and all((context.operating_bbox, context.routing_bbox, context.render_bbox, context.osrm_base_url))
    if configured:
        status = await dataset_status(context)
        pbf, artifacts, router = status["pbf"], status["artifacts"], status["osrm"]
        ready = status["ready"]
    else:
        pbf = {"state": "not_prepared", "size_bytes": None, "format_verified": False, "osmium_available": False}
        artifacts = {"map_ready": False, "graph_ready": False, "extracted_ready": False}
        router, ready = {"state": "not_configured"}, False
    reason = "" if ready else (context.unavailable_reason or "Dữ liệu bản đồ hoặc bộ định tuyến CAR cục bộ chưa sẵn sàng.")
    region = context.region
    return {"regionId": context.id, "state": "ready" if ready else "not_ready", "ready": ready,
            "readinessReason": reason,
            "viewport": {"center": context.viewport_center, "zoom": context.viewport_zoom, "bounds": region.display_bbox},
            "coverage": {"operating": context.operating_bbox, "routing": context.routing_bbox, "render": context.render_bbox},
            "pbf": {key: pbf[key] for key in ("state", "size_bytes", "format_verified", "osmium_available")},
            "artifacts": {key: artifacts[key] for key in ("map_ready", "graph_ready", "extracted_ready")},
            "osrm": {"state": router["state"]},
            "region": {"name": region.name, "display_bbox": region.display_bbox, "routing_bbox": context.routing_bbox,
                       "source": region.source, "attribution": region.attribution, "boundary_note": region.boundary_note}}
