"""Small geometry fixtures for the separate low-zoom real-MVT derivative."""
import json
from pathlib import Path
import sqlite3

import mapbox_vector_tile
import pytest
from shapely.geometry import LineString, Point, box
from shapely.ops import transform

from scripts import connected_overview_tiles as overview
from scripts.connected_gis import identity
from scripts.connected_gis_render import mercator
from scripts.pipeline import sha256


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path
    folder = root/'data/regions/nvmr-connected/render'
    folder.mkdir(parents=True)
    (root/'scripts').mkdir()
    (root/overview.SCRIPT).write_bytes(Path(overview.__file__).read_bytes())
    national = root/'source.pbf'
    national.write_bytes(b'fixture source identity, not a real PBF')
    extract = folder.parent/'extracted/coverage.osm.pbf'
    extract.parent.mkdir()
    extract.write_bytes(b'fixture extract identity')
    bbox = [104.35,20.06,107.25,22.85]
    c = {'regionId': 'nvmr-connected', 'pipelineVersion': 'fixture/v1',
         'mapBbox': bbox, 'source': {'path': 'source.pbf', 'sha256': sha256(national),
                                    'attribution': 'OpenStreetMap contributors'},
         'tiles': {'minZoom': 6, 'maxZoom': 13, 'sourceLayers': overview.LAYERS}}
    save(root/'config/connected-nvmr.json', c)
    (folder/'tiles.mbtiles').write_bytes(b'preserved base fixture')
    save(folder/'manifest.json', {'identity': identity(root), 'source_sha256': sha256(national),
        'extract_sha256': sha256(extract), 'map_bbox': bbox, 'minzoom': 6, 'maxzoom': 13,
        'source_layers': overview.LAYERS, 'artifact_sha256': {'tiles.mbtiles': sha256(folder/'tiles.mbtiles')}})
    with sqlite3.connect(folder/'features.sqlite') as db:
        db.execute('CREATE TABLE features(id INTEGER PRIMARY KEY,layer TEXT,minzoom INTEGER,geometry BLOB,properties TEXT)')
        db.execute('CREATE VIRTUAL TABLE bounds USING rtree(id,minx,maxx,miny,maxy)')
        values = [('streets',6,LineString([(104.5,20.2),(106,21.5),(107,22.7)]),{'highway':'primary'}),
                  ('streets',11,LineString([(105,21),(106,21)]),{'highway':'residential'}),
                  ('water',6,box(105,20.5,106,21.5),{'natural':'water'}),
                  ('places',6,Point(105.84,21.02),{'place':'city','name':'Hà Nội'})]
        for layer, zoom, shape, props in values:
            g = transform(mercator, shape)
            cursor = db.execute('INSERT INTO features(layer,minzoom,geometry,properties) VALUES(?,?,?,?)',
                               (layer,zoom,g.wkb,json.dumps(props)))
            w,s,e,n = g.bounds
            db.execute('INSERT INTO bounds VALUES(?,?,?,?,?)',(cursor.lastrowid,w,e,s,n))
    save(folder/'features-manifest.json', {'identity': identity(root),
        'extract_sha256': sha256(extract), 'sha256': sha256(folder/'features.sqlite')})
    monkeypatch.setattr(overview, 'guard', lambda action: {'fixtureOnly': True, 'action': action})
    return root


def test_overview_is_real_mvt_at_all_low_zooms_and_preserves_base(source):
    base = overview.base(source)/'render'
    before = {name: (base/name).read_bytes() for name in ('features.sqlite','tiles.mbtiles','manifest.json')}
    manifest = overview.build(source)
    assert manifest['minzoom'] == 0 and manifest['maxzoom'] == 5
    assert all(manifest['tile_counts'][str(z)] > 0 for z in range(6))
    assert not (overview.base(source)/'render-overview/.incomplete').exists()
    for name, raw in before.items():
        assert (base/name).read_bytes() == raw
    detailed_labels, detailed_roads = [], []
    with sqlite3.connect(overview.base(source)/'render-overview/tiles.mbtiles') as db:
        for z,x,tms,payload in db.execute('SELECT zoom_level,tile_column,tile_row,tile_data FROM tiles'):
            y = 2**z-1-tms
            xs, ys = overview.tile_range(manifest['map_bbox'], z)
            assert x in xs and y in ys
            decoded = mapbox_vector_tile.decode(payload)
            assert set(decoded) <= set(overview.LAYERS)
            if z == 5:
                detailed_labels.extend(f['properties']['name'] for f in decoded.get('places', {}).get('features', []))
                detailed_roads.extend(decoded.get('streets', {}).get('features', []))
            for layer in decoded.values():
                assert layer['extent'] == 4096
                for feature in layer['features']:
                    assert feature['properties'].get('highway') != 'residential'
                    def coordinates(value):
                        if value and isinstance(value[0], (int,float)):
                            assert all(0 <= number <= 4096 for number in value)
                        else:
                            for item in value:
                                coordinates(item)
                    coordinates(feature['geometry']['coordinates'])
    assert 'Hà Nội' in detailed_labels and detailed_roads
    assert overview.verify_overview(source) == manifest
    assert overview.build(source) == manifest


@pytest.mark.parametrize('target', ['source.pbf', 'scripts/connected_overview_tiles.py',
    'data/regions/nvmr-connected/render/features.sqlite',
    'data/regions/nvmr-connected/render/tiles.mbtiles',
    'data/regions/nvmr-connected/render-overview/tiles.mbtiles'])
def test_overview_reuse_rejects_changed_inputs_or_output(source, target):
    overview.build(source)
    with (source/target).open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(RuntimeError):
        overview.verify_overview(source)


def test_incomplete_overview_cannot_be_reused_or_overwritten(source):
    folder = overview.base(source)/'render-overview'
    folder.mkdir()
    (folder/'.incomplete').write_text('interrupted')
    with pytest.raises(RuntimeError, match='incomplete'):
        overview.verify_overview(source)
    with pytest.raises(RuntimeError, match='Refusing overwrite'):
        overview.build(source)


def test_overview_guard_failure_creates_no_output(source, monkeypatch):
    def blocked(_):
        raise RuntimeError('RESOURCE_STOP')
    monkeypatch.setattr(overview, 'guard', blocked)
    with pytest.raises(RuntimeError, match='RESOURCE_STOP'):
        overview.build(source)
    assert not (overview.base(source)/'render-overview').exists()
