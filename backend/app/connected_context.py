"""Server-owned connected contexts; legacy region/map readiness is unchanged."""
from dataclasses import dataclass
import hashlib
import json

from .config import PROJECT_ROOT, Settings
from .regions import FrozenRegion, RegionContext


@dataclass(frozen=True)
class ConnectedModeContext:
    base: RegionContext
    vehicle_type: str
    profile: str

    def __getattr__(self, name):
        return getattr(self.base, name)


def connected_context(mode):
    if mode not in ('CAR', 'MOTORBIKE'):
        raise ValueError('Unknown connected mode')
    raw_bytes = (PROJECT_ROOT/'config/connected-nvmr.json').read_bytes()
    config, settings = json.loads(raw_bytes), Settings()
    routing = config['routing'][mode]
    w, s, e, n = config['mapBbox']
    region = FrozenRegion(name=config['label'], display_bbox=config['mapBbox'],
        routing_buffer_degrees=0, extract_strategy='complete_ways', complete_relation_types='multipolygon',
        source='OpenStreetMap', source_url=config['source']['url'], attribution=config['source']['attribution'],
        boundary_note=config['boundaryNote'])
    directory = (PROJECT_ROOT/routing['manifest']).parent
    base = RegionContext(id=config['regionId'], region=region, viewport_center=((w+e)/2, (s+n)/2),
        viewport_zoom=7, operating_bbox=tuple(config['routingBbox']), routing_bbox=tuple(config['routingBbox']),
        render_bbox=tuple(config['mapBbox']), pbf_path=PROJECT_ROOT/config['source']['path'],
        map_path=PROJECT_ROOT/config['tiles']['archive'], routing_dir=directory,
        extracted_path=PROJECT_ROOT/'data/regions/nvmr-connected/extracted/coverage.osm.pbf',
        graph_basename='connected', osrm_base_url=routing['baseUrl'],
        osrm_timeout_seconds=max(settings.osrm_timeout_seconds, 20),
        max_snap_meters=config['distribution']['maxSnapMeters'],
        artifact_config_sha256=hashlib.sha256(raw_bytes).hexdigest(), pipeline_version=config['pipelineVersion'])
    return ConnectedModeContext(base, mode, 'car' if mode == 'CAR' else 'motorbike')
