"""Server-owned registry. Contexts are immutable snapshots, never an active region."""
import json
import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from fastapi import HTTPException
from pydantic import ConfigDict

from .config import Region, Settings

Bbox = tuple[float, float, float, float]


class FrozenRegion(Region):
    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class RegionContext:
    id: str
    region: FrozenRegion
    viewport_center: tuple[float, float]
    viewport_zoom: float
    operating_bbox: Bbox | None
    routing_bbox: Bbox | None
    render_bbox: Bbox | None
    pbf_path: Path
    map_path: Path
    routing_dir: Path
    extracted_path: Path
    graph_basename: str
    osrm_base_url: str
    osrm_timeout_seconds: float
    max_snap_meters: float
    enabled: bool = True
    unavailable_reason: str = ""
    artifact_config_sha256: str = ""
    pipeline_version: str = "hanoi-car-pilot/v1"

    @property
    def artifact_identity(self):
        if not self.artifact_config_sha256:
            return None  # Legacy HCM and explicit synthetic test contexts.
        return {"region_id": self.id, "config_sha256": self.artifact_config_sha256,
                "pipeline_version": self.pipeline_version}

    def __post_init__(self):
        object.__setattr__(self, "region", FrozenRegion.model_validate(self.region.model_dump()))
        object.__setattr__(self, "viewport_center", tuple(self.viewport_center))
        for name in ("operating_bbox", "routing_bbox", "render_bbox"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, tuple(value))
        if not re.fullmatch(r"[a-z0-9-]+", self.id) or not re.fullmatch(r"[a-z0-9-]+", self.graph_basename):
            raise ValueError("Invalid server region/artifact identity")
        for bbox in (self.operating_bbox, self.routing_bbox, self.render_bbox):
            if bbox is not None and (len(bbox) != 4 or not all(math.isfinite(x) for x in bbox)
                    or not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90)):
                raise ValueError("Invalid region coverage")
        if self.osrm_base_url:
            object.__setattr__(self, "osrm_base_url", Settings.local_router_only(self.osrm_base_url))

    @property
    def route_validation_bbox(self):
        # Preserve A2/A3/A4's stricter HCM coverage, including the explicit adapter.
        return self.region.display_bbox if self.id == "hcm-center" else self.routing_bbox


@dataclass(frozen=True)
class RegionRegistry:
    contexts: Mapping[str, RegionContext]

    def __post_init__(self):
        entries = dict(self.contexts)
        if any(key != value.id for key, value in entries.items()):
            raise ValueError("Region registry identity mismatch")
        object.__setattr__(self, "contexts", MappingProxyType(entries))

    def resolve(self, region_id: str) -> RegionContext:
        context = self.contexts.get(region_id)
        if context is None:
            raise HTTPException(404, {"code": "UNKNOWN_REGION", "message": "Khu vực không có trong danh mục máy chủ."})
        return context


def default_registry(settings: Settings) -> RegionRegistry:
    region = FrozenRegion.model_validate(settings.region.model_dump())
    w, s, e, n = region.display_bbox
    hcm = RegionContext(
        id="hcm-center", region=region, viewport_center=((w+e)/2, (s+n)/2), viewport_zoom=14.2,
        operating_bbox=region.display_bbox, routing_bbox=region.routing_bbox, render_bbox=region.display_bbox,
        pbf_path=settings.pbf_path, map_path=settings.map_path, routing_dir=settings.routing_dir,
        extracted_path=settings.routing_dir.parent / "extracted/hcm-center.osm.pbf",
        graph_basename="hcm-center", osrm_base_url=settings.osrm_base_url,
        osrm_timeout_seconds=settings.osrm_timeout_seconds, max_snap_meters=settings.max_snap_meters)
    # The file is shipped with the server, not selected by an HTTP parameter.
    config_bytes = (Path(__file__).resolve().parents[2] / "config/regions/nvmr-hanoi-core.json").read_bytes()
    config = json.loads(config_bytes)
    viewport = tuple(config["viewport_bbox"])
    w, s, e, n = viewport
    hanoi_region = FrozenRegion.model_validate({**region.model_dump(), "name": config["label"], "display_bbox": viewport,
        "routing_buffer_degrees": config.get("routing_buffer_degrees", 0), "boundary_note": config["note"]})
    base = settings.resolve("data/regions/nvmr-hanoi-core")
    hanoi = RegionContext(
        id="nvmr-hanoi-core", region=hanoi_region,
        viewport_center=((w+e)/2, (s+n)/2), viewport_zoom=config["viewport_zoom"],
        operating_bbox=config.get("operating_bbox"), routing_bbox=config.get("routing_bbox"), render_bbox=config.get("render_bbox"),
        pbf_path=settings.pbf_path, map_path=base / "render/streets.geojson",
        routing_dir=base / "routing/car", extracted_path=base / "extracted/coverage.osm.pbf",
        graph_basename=config.get("graph_basename", "hanoi-core"), osrm_base_url=config.get("osrm_base_url", ""), osrm_timeout_seconds=settings.osrm_timeout_seconds,
        max_snap_meters=settings.max_snap_meters, enabled=config.get("enabled", False),
        artifact_config_sha256=hashlib.sha256(config_bytes).hexdigest())
    # Keep the historical Hanoi configuration bytes/identity untouched.
    bac_bytes = (Path(__file__).resolve().parents[2] / "config/regions/nvmr-bac-ninh-core.json").read_bytes()
    bac = json.loads(bac_bytes)
    w, s, e, n = bac["viewport_bbox"]
    bac_region = FrozenRegion.model_validate({**region.model_dump(), "name": bac["label"],
        "display_bbox": bac["viewport_bbox"], "routing_buffer_degrees": bac["routing_buffer_degrees"], "boundary_note": bac["note"]})
    base = settings.resolve("data/regions/nvmr-bac-ninh-core")
    bac_ninh = RegionContext(id="nvmr-bac-ninh-core", region=bac_region,
        viewport_center=((w+e)/2, (s+n)/2), viewport_zoom=bac["viewport_zoom"],
        operating_bbox=bac["operating_bbox"], routing_bbox=bac["routing_bbox"], render_bbox=bac["render_bbox"],
        pbf_path=settings.pbf_path, map_path=base/"render/streets.geojson", routing_dir=base/"routing/car",
        extracted_path=base/"extracted/coverage.osm.pbf", graph_basename=bac["graph_basename"],
        osrm_base_url=bac["osrm_base_url"], osrm_timeout_seconds=settings.osrm_timeout_seconds,
        max_snap_meters=settings.max_snap_meters, enabled=bac["enabled"],
        artifact_config_sha256=hashlib.sha256(bac_bytes).hexdigest(), pipeline_version=bac["pipeline_version"])
    return RegionRegistry({hcm.id: hcm, hanoi.id: hanoi, bac_ninh.id: bac_ninh})
