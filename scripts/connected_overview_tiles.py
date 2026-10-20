"""Write-once z0-5 real-OSM overview, derived from the preserved geometry DB.

The independently validated z6-13 basemap and frozen configuration are read-only.
python -m scripts.connected_overview_tiles
"""
from collections import defaultdict
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3

from backend.app.integrity import digest, verified_files
from backend.app.simulation_jobs import atomic_json
from scripts.connected_gis import ROOT, base, config, guard, heavy_lock, identity, verify_render
from scripts.connected_gis_render import EXTENT, mercator
from scripts.m3_resources import Monitor

SCRIPT = 'scripts/connected_overview_tiles.py'
LAYERS = ['streets', 'water', 'green', 'places']


def inputs(root):
    c = config(root)
    main = verify_render(root)
    folder = base(root)/'render'
    feature_manifest = json.loads((folder/'features-manifest.json').read_text(encoding='utf-8'))
    features_hash = digest(folder/'features.sqlite')
    extract_hash = digest(base(root)/'extracted/coverage.osm.pbf')
    if (feature_manifest['identity'] != identity(root) or feature_manifest['sha256'] != features_hash
            or feature_manifest['extract_sha256'] != extract_hash):
        raise RuntimeError('Overview geometry database identity mismatch')
    if main['minzoom'] != 6 or c['tiles']['sourceLayers'] != LAYERS:
        raise RuntimeError('Overview requires the preserved z6-13 basemap contract')
    if digest(root/c['source']['path']) != c['source']['sha256']:
        raise RuntimeError('Overview national source identity mismatch')
    return {'identity': identity(root), 'source_sha256': c['source']['sha256'],
        'extract_sha256': extract_hash, 'base_archive_sha256': main['artifact_sha256']['tiles.mbtiles'],
        'features_db_sha256': features_hash, 'script_sha256': digest(root/SCRIPT),
        'map_bbox': c['mapBbox'], 'minzoom': 0, 'maxzoom': 5,
        'source_layers': LAYERS, 'format': 'mvt', 'scheme': 'tms'}


def verify_overview(root=ROOT):
    root = Path(root)
    folder = base(root)/'render-overview'
    if (folder/'.incomplete').exists():
        raise RuntimeError('Connected overview is incomplete')
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 'connected-overview-tiles/v1':
        raise RuntimeError('Unsupported overview manifest')
    for key, value in inputs(root).items():
        if manifest.get(key) != value:
            raise RuntimeError(f'Connected overview identity mismatch: {key}')
    if (set(manifest.get('artifact_sha256', {})) != {'tiles.mbtiles'}
            or not verified_files(folder, manifest['artifact_sha256'])):
        raise RuntimeError('Connected overview archive checksum mismatch')
    if set(manifest.get('tile_counts', {})) != {str(z) for z in range(6)}:
        raise RuntimeError('Connected overview zoom coverage missing')
    return manifest


def tile_range(bbox, z):
    w, s = mercator(bbox[0], bbox[1])
    e, n = mercator(bbox[2], bbox[3])
    scale = 2**z
    size = 2*EXTENT/scale
    bound = lambda value: max(0, min(scale-1, math.floor(value)))
    return (range(bound((w+EXTENT)/size), bound((e+EXTENT)/size)+1),
            range(bound((EXTENT-n)/size), bound((EXTENT-s)/size)+1))


def encode_tile(db, z, x, y):
    import mapbox_vector_tile
    import shapely
    from shapely.geometry import box
    size = 2*EXTENT/(2**z)
    w, n = x*size-EXTENT, EXTENT-y*size
    e, s = w+size, n-size
    clip = box(w, s, e, n)
    layers = defaultdict(list)
    # Stored minzoom<=6 deliberately selects source arterials, water polygons,
    # cities/towns; smaller roads and villages retain the detailed base tiles.
    for fid, layer, wkb, props in db.execute(
        'SELECT f.id,f.layer,f.geometry,f.properties FROM features f JOIN bounds b ON f.id=b.id '
        'WHERE f.minzoom<=6 AND b.minx<=? AND b.maxx>=? AND b.miny<=? AND b.maxy>=?', (e,w,n,s)):
        if layer not in LAYERS:
            raise RuntimeError(f'Unexpected geometry source layer: {layer}')
        geometry = shapely.from_wkb(wkb).intersection(clip)
        if geometry.geom_type != 'Point':
            geometry = geometry.simplify(size/4096*.6, preserve_topology=True)
        if geometry.is_empty or geometry.geom_type not in (
                'Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'):
            continue
        layers[layer].append({'id': fid, 'geometry': geometry, 'properties': json.loads(props)})
    if not layers:
        return None
    return mapbox_vector_tile.encode([{'name': name, 'features': features}
        for name, features in sorted(layers.items())], default_options={
            'quantize_bounds': (w,s,e,n), 'extents': 4096})


def build(root=ROOT):
    root = Path(root)
    folder = base(root)/'render-overview'
    if (folder/'manifest.json').exists():
        result = verify_overview(root)
        print('REUSE verified Connected overview', flush=True)
        return result
    if folder.exists() and any(folder.iterdir()):
        raise RuntimeError('Refusing overwrite of existing/incomplete Connected overview')
    expected = inputs(root)
    preflight = guard('connected-overview')
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder/'.incomplete'
    marker.write_text('Connected overview real-geometry tile generation incomplete', encoding='utf-8')
    archive = folder/'tiles.mbtiles'
    db_path = base(root)/'render/features.sqlite'
    counts = {}
    with Monitor(.5) as monitor:
        with closing(sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro', uri=True)) as db:
            with closing(sqlite3.connect(archive)) as tiles:
                tiles.execute('CREATE TABLE metadata(name TEXT,value TEXT)')
                tiles.execute('CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,'
                              'tile_data BLOB,PRIMARY KEY(zoom_level,tile_column,tile_row))')
                metadata = {'name': 'Connected NVMR real OSM overview', 'format': 'pbf',
                    'minzoom': '0', 'maxzoom': '5', 'bounds': ','.join(map(str, expected['map_bbox'])),
                    'attribution': config(root)['source']['attribution']}
                tiles.executemany('INSERT INTO metadata VALUES(?,?)', metadata.items())
                for z in range(6):
                    xs, ys = tile_range(expected['map_bbox'], z)
                    count = 0
                    for x in xs:
                        for y in ys:
                            payload = encode_tile(db, z, x, y)
                            if payload is not None:
                                tiles.execute('INSERT INTO tiles VALUES(?,?,?,?)', (z,x,2**z-1-y,payload))
                                count += 1
                    tiles.commit()
                    counts[str(z)] = count
                    print(f'Connected overview z{z}: {count} real-geometry tiles', flush=True)
    if inputs(root) != expected:
        raise RuntimeError('Connected overview inputs changed during generation')
    manifest = {'schemaVersion': 'connected-overview-tiles/v1', **expected,
        'artifact_sha256': {'tiles.mbtiles': digest(archive)}, 'tile_counts': counts,
        'preflight': preflight, 'resources': monitor.result(),
        'derivation': 'Real source geometry minzoom<=6; Mercator tile clipping, topology-preserving 0.6-pixel simplification, MVT extent4096; no invented coordinates',
        'limitations': ['Overview selects source arterial roads, water polygons and city/town labels.',
            'Detailed green/small roads and waterways remain in preserved z6-13 tiles; no administrative borders are inferred.']}
    atomic_json(folder/'manifest.json', manifest)
    marker.unlink()
    return verify_overview(root)


if __name__ == '__main__':
    with heavy_lock():
        build()
