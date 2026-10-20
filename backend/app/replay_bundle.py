"""Portable completed-run verification. No source PBF, routers or worker required."""
import json
from pathlib import Path, PurePosixPath

from .integrity import digest


def bundle_file(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe bundle path')
    target = (Path(root) / name).resolve()
    if not target.is_relative_to(Path(root).resolve()):
        raise ValueError('Bundle path escapes root')
    return target


def verify_bundle(root):
    root = Path(root)
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 'gsm-connected-research-bundle/v1':
        raise ValueError('Unsupported research bundle')
    job = manifest['jobId']
    required = {f'jobs/{job}/{name}' for name in ['input.json', 'prepared-input.json', 'status.json', 'event-log.json', 'result.json']}
    if not required <= manifest['files'].keys():
        raise ValueError('Incomplete completed-job inventory')
    for name, record in manifest['files'].items():
        path = bundle_file(root, name)
        if path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
            raise ValueError(f'Bundle checksum mismatch: {name}')
    status = json.loads(bundle_file(root, f'jobs/{job}/status.json').read_text())
    if status['id'] != job or status['status'] != 'COMPLETED':
        raise ValueError('Bundle must contain the identified completed job')
    return manifest


def portable_map_status(root):
    """Check copied tiles against both bundle inventory and original GIS identities.

    This validates published map bytes, not the ability to rebuild their sources.
    """
    root = Path(root)
    manifest = verify_bundle(root)
    required = {'config/connected-nvmr.json'} | {
        f'data/regions/nvmr-connected/{directory}/{name}'
        for directory in ['render', 'render-overview'] for name in ['manifest.json', 'tiles.mbtiles']}
    if not required <= manifest['files'].keys():
        raise ValueError('Incomplete portable-map inventory')
    config = json.loads((root/'config/connected-nvmr.json').read_text())
    identity = {'region_id': config['regionId'], 'config_sha256': digest(root/'config/connected-nvmr.json'),
                'pipeline_version': config['pipelineVersion']}
    maps = []
    for directory, minimum, maximum in [('render', config['tiles']['minZoom'], config['tiles']['maxZoom']), ('render-overview', 0, 5)]:
        folder = root/'data/regions/nvmr-connected'/directory
        value = json.loads((folder/'manifest.json').read_text())
        if (value['identity'] != identity or value['source_sha256'] != config['source']['sha256']
                or value['map_bbox'] != config['mapBbox'] or value['source_layers'] != config['tiles']['sourceLayers']
                or value['minzoom'] != minimum or value['maxzoom'] != maximum
                or value['artifact_sha256'] != {'tiles.mbtiles': digest(folder/'tiles.mbtiles')}):
            raise ValueError('Portable map identity mismatch')
        maps.append(value)
    if (maps[1]['base_archive_sha256'] != maps[0]['artifact_sha256']['tiles.mbtiles']
            or maps[1]['extract_sha256'] != maps[0]['extract_sha256']):
        raise ValueError('Portable map provenance chain mismatch')
    return config, maps, manifest
