"""Small artifact checksum/identity fixtures, never real GIS correctness evidence."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.app.integrity import digest
from scripts.connected_gis import CAR_PROFILE_SHA256, OSRM_IMAGE, identity, verify_graph, verify_render


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def artifacts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root/'config/connected-nvmr.json').read_text(encoding='utf-8'))
    source = tmp_path/cfg['source']['path']
    source.parent.mkdir(parents=True)
    source.write_bytes(b'INTEGRITY FIXTURE ONLY, not a valid OSM PBF')
    cfg['source']['sha256'] = digest(source)
    write(tmp_path/'config/connected-nvmr.json', cfg)
    base = tmp_path/'data/regions/nvmr-connected'
    extract = base/'extracted/coverage.osm.pbf'
    extract.parent.mkdir(parents=True)
    extract.write_bytes(b'INTEGRITY FIXTURE ONLY, not a road extract')
    for mode in ('CAR', 'MOTORBIKE'):
        folder = base/'routing'/mode.lower()
        folder.mkdir(parents=True)
        hashes, sizes = {}, {}
        for suffix in ('partition', 'cells', 'mldgr'):
            path = folder/f'connected.osrm.{suffix}'
            path.write_bytes(mode.encode())
            hashes[path.name], sizes[path.name] = digest(path), path.stat().st_size
        profile = tmp_path/'profiles/motorbike.lua'
        profile.parent.mkdir(exist_ok=True)
        profile.write_text('-- explicit synthetic profile fixture')
        profile_hash = CAR_PROFILE_SHA256 if mode == 'CAR' else digest(profile)
        path = cfg['routing'][mode]['profilePath']
        write(folder/'manifest.json', {'identity': identity(tmp_path), 'profile': mode.lower(),
            'algorithm': 'mld', 'source_sha256': cfg['source']['sha256'],
            'extract_sha256': digest(extract), 'routing_bbox': cfg['routingBbox'],
            'profile_path': path, 'profile_sha256': profile_hash, 'profile_dependencies': {path: profile_hash},
            'image_digest': OSRM_IMAGE, 'artifact_sha256': hashes, 'artifact_sizes': sizes})
    render = base/'render'
    render.mkdir()
    archive = render/'tiles.mbtiles'
    archive.write_bytes(b'INTEGRITY FIXTURE ONLY, not real vector tiles')
    write(render/'manifest.json', {'identity': identity(tmp_path),
        'source_sha256': cfg['source']['sha256'], 'extract_sha256': digest(extract),
        'map_bbox': cfg['mapBbox'], 'minzoom': cfg['tiles']['minZoom'], 'maxzoom': cfg['tiles']['maxZoom'],
        'source_layers': cfg['tiles']['sourceLayers'], 'artifact_sha256': {'tiles.mbtiles': digest(archive)}})
    return base


@pytest.mark.parametrize('mutation', ['bytes', 'coverage', 'profile', 'source', 'incomplete'])
def test_connected_graph_identity_fails_closed(mutation, tmp_path):
    base = artifacts(tmp_path)
    assert verify_graph('CAR', tmp_path)['algorithm'] == 'mld'
    assert verify_graph('MOTORBIKE', tmp_path)['profile'] == 'motorbike'
    folder = base/'routing/motorbike'
    path = folder/'manifest.json'
    raw = json.loads(path.read_text())
    if mutation == 'bytes':
        (folder/'connected.osrm.cells').write_bytes(b'changed bytes of same or different size')
    elif mutation == 'coverage':
        raw['routing_bbox'][0] += .01
    elif mutation == 'profile':
        (tmp_path/'profiles/motorbike.lua').write_text('-- changed source profile')
    elif mutation == 'source':
        (tmp_path/'data/raw/vietnam-latest.osm.pbf').write_bytes(b'changed national bytes')
    else:
        (folder/'.incomplete').touch()
    write(path, raw)
    with pytest.raises(RuntimeError):
        verify_graph('MOTORBIKE', tmp_path)


@pytest.mark.parametrize('mutation', ['bytes', 'coverage', 'config', 'incomplete'])
def test_connected_map_identity_fails_closed(mutation, tmp_path):
    base = artifacts(tmp_path)
    assert verify_render(tmp_path)['source_layers'] == ['streets', 'water', 'green', 'places']
    folder = base/'render'
    path = folder/'manifest.json'
    raw = deepcopy(json.loads(path.read_text()))
    if mutation == 'bytes':
        (folder/'tiles.mbtiles').write_bytes(b'changed archive')
    elif mutation == 'coverage':
        raw['map_bbox'][0] += .01
    elif mutation == 'config':
        config_path = tmp_path/'config/connected-nvmr.json'
        cfg = json.loads(config_path.read_text())
        cfg['boundaryVersion'] = 'different-config'
        write(config_path, cfg)
    else:
        (folder/'.incomplete').touch()
    write(path, raw)
    with pytest.raises(RuntimeError):
        verify_render(tmp_path)
