"""Request-pinned mode contexts. CAR v1 manifests and configuration stay intact."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from fastapi import HTTPException
from .integrity import digest, verified_files

VehicleType = Literal['CAR', 'MOTORBIKE']
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ModeContext:
    base: object
    routing_dir: Path
    graph_basename: str
    osrm_base_url: str
    config_sha256: str
    profile_sha256: str
    assumptions_sha256: str
    vehicle_type: str = 'MOTORBIKE'
    profile: str = 'motorbike'

    def __getattr__(self, name):
        return getattr(self.base, name)

    @property
    def artifact_identity(self):
        return {**self.base.artifact_identity, 'vehicle_type': self.vehicle_type,
                'mode_config_sha256': self.config_sha256, 'profile_sha256': self.profile_sha256,
                'assumptions_sha256': self.assumptions_sha256, 'version': 'hanoi-electric-motorcycle/v1'}


def resolve_mode(registry, region_id, mode):
    base = registry.resolve(region_id)
    if mode == 'CAR':
        return base
    if mode != 'MOTORBIKE':
        raise HTTPException(404, {'code': 'UNKNOWN_VEHICLE_TYPE', 'message': 'Loại dịch vụ không hợp lệ.'})
    if region_id != 'nvmr-hanoi-core':
        raise HTTPException(503, {'code': 'MODE_NOT_READY', 'message': 'MOTORBIKE chỉ hỗ trợ pilot Hanoi Core.'})
    path = ROOT/'config/regions/nvmr-hanoi-core-motorbike.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    if (config['vehicleType'],config['profile'],config['artifactVersion']) != ('MOTORBIKE','motorbike','hanoi-electric-motorcycle/v1'):
        raise ValueError('Unsupported server mode/profile/version')
    from .config import Settings
    return ModeContext(base, base.routing_dir.parent/'motorbike', config['graph_basename'],
                       Settings.local_router_only(config['osrm_base_url']), digest(path),
                       digest(ROOT/'profiles/motorbike.lua'),digest(ROOT/'profiles/motorbike.json'))


def motor_artifacts(context):
    from .dataset import artifact_status
    status = artifact_status(context.base)
    try:
        graph = json.loads((context.routing_dir/'manifest.json').read_text(encoding='utf-8'))
        source = json.loads((context.map_path.parent.parent/'source-verification.json').read_text(encoding='utf-8'))
        valid = (graph['identity'] == context.artifact_identity and graph['profile'] == 'motorbike'
            and graph['algorithm'] == 'mld' and graph['profile_sha256'] == context.artifact_identity['profile_sha256']
            and graph['extract_sha256'] == digest(context.extracted_path)
            and graph['source_sha256'] == source['sha256'] == digest(context.pbf_path)
            and graph['profile_dependencies']['/profiles/motorbike.lua'] == graph['profile_sha256']
            and len(graph['profile_dependencies']) > 20
            and set(graph['artifact_sha256']) == set(graph['artifact_sizes'])
            and {f'{context.graph_basename}.osrm.{x}' for x in ('partition','cells','mldgr')} <= set(graph['artifact_sha256'])
            and graph['routing_bbox'] == list(context.routing_bbox)
            and verified_files(context.routing_dir, graph['artifact_sha256'])
            and not (context.routing_dir/'.incomplete').exists())
        validation = json.loads((context.routing_dir/'validation.json').read_text(encoding='utf-8'))
        valid = valid and validation['status'] == 'PASS' and validation['manifest_sha256'] == digest(context.routing_dir/'manifest.json')
        valid = valid and not (context.routing_dir/'.validation-incomplete').exists()
        valid = valid and validation['validator_sha256'] == digest(ROOT/'scripts/validate_motorbike.py')
        for key,name in [('synthetic_sha256','synthetic-validation.json'),('real_oneway_sha256','osm-oneway-nodes.json'),('directed_cases_sha256','real-mode-cases.json')]:
            evidence=ROOT/'docs/nvmr/m2-evidence'/name
            valid = valid and validation[key] == digest(evidence) and json.loads(evidence.read_text(encoding='utf-8'))['status']=='PASS'
        return {**status, 'graph_ready': bool(valid), 'routing_manifest': graph}
    except (OSError,ValueError,KeyError,TypeError):
        return {**status, 'graph_ready': False, 'routing_manifest': None}


def routing_identity(context):
    graph = json.loads((context.routing_dir/'manifest.json').read_text(encoding='utf-8'))
    return {'regionId': context.id, 'vehicleType': getattr(context,'vehicle_type','CAR'),
            'profile': graph['profile'], 'profileSha256': graph['profile_sha256'],
            'graphManifestSha256': digest(context.routing_dir/'manifest.json'),
            'sourceSha256': graph.get('source_sha256', graph['extract_sha256']),
            'extractSha256': graph['extract_sha256'], 'algorithm': 'mld'}
