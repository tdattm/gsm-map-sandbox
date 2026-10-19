"""Small filter-order regression, not a real-world map acceptance test."""
import pytest
import json
import sqlite3

from scripts.connected_gis_render import build, native_filters


def test_native_filters_preserve_untagged_references_for_ways_and_areas(tmp_path):
    osmium = pytest.importorskip('osmium')
    source = tmp_path/'native-reference-fixture.osm'
    source.write_text('''<osm version="0.6">
      <node id="1" lon="105.0" lat="21.0"/>
      <node id="2" lon="105.001" lat="21.0"/>
      <node id="3" lon="105.001" lat="21.001"/>
      <node id="4" lon="105.0" lat="21.001"/>
      <node id="5" lon="105.002" lat="21.0"><tag k="place" v="town"/><tag k="name" v="Fixture"/></node>
      <way id="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/></way>
      <way id="2"><nd ref="1"/><nd ref="2"/><nd ref="3"/></way>
      <way id="3"><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
      <relation id="1"><member type="way" ref="2" role="outer"/><member type="way" ref="3" role="outer"/><tag k="type" v="multipolygon"/><tag k="natural" v="water"/></relation>
    </osm>''', encoding='utf-8')
    nodes, ways, areas = [], [], []

    class Handler(osmium.SimpleHandler):
        def node(self, node):
            nodes.append(node.id)

        def way(self, way):
            ways.append((way.id, [(node.lon, node.lat) for node in way.nodes]))

        def area(self, area):
            areas.append((area.orig_id(), area.tags.get('natural'),
                          [[(node.lon, node.lat) for node in ring] for ring in area.outer_rings()]))

    Handler().apply_file(str(source), locations=True, idx='sparse_file_array', filters=native_filters(osmium))
    assert nodes == [5]
    assert ways == [(1, [(105.0, 21.0), (105.001, 21.0)])]
    assert len(areas) == 1
    assert areas[0][:2] == (1, 'water')
    assert len(areas[0][2][0]) == 5


def test_tiny_osm_builds_viewport_tiles_and_road_candidates(tmp_path):
    pytest.importorskip('osmium')
    decoder = pytest.importorskip('mapbox_vector_tile')
    source = tmp_path/'tiny.osm'
    source.write_text('''<osm version="0.6">
      <node id="1" lon="105.0" lat="21.0"/>
      <node id="2" lon="105.001" lat="21.0"/>
      <node id="3" lon="105.001" lat="21.001"/>
      <node id="4" lon="105.0" lat="21.001"/>
      <node id="5" lon="105.0005" lat="21.0005"><tag k="place" v="town"/><tag k="name" v="Fixture"/></node>
      <way id="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/></way>
      <way id="2"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="natural" v="water"/></way>
      <way id="3"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="leisure" v="park"/></way>
    </osm>''', encoding='utf-8')
    c = {'mapBbox': [104.999,20.999,105.002,21.002],
         'source': {'sha256':'fixture-source','attribution':'Explicit synthetic fixture'},
         'operatingZones':[{'id':'hanoi','bbox':[104.999,20.999,105.002,21.002]}],
         'distribution': {'maxAnchorsPerCell':100,'cellDegrees':.005},
         'tiles': {'sourceLayers':['streets','water','green','places']},
         'boundaryVersion':'synthetic-fixture'}
    build('render',source,c,{'fixture':True},tmp_path)
    manifest = json.loads((tmp_path/'render/manifest.json').read_text())
    assert manifest['features'] == {'places':1,'streets':1,'water':1,'green':1}
    assert set(manifest['tile_counts']) == {str(z) for z in range(6,14)}
    assert not (tmp_path/'render/.incomplete').exists()
    with sqlite3.connect(tmp_path/'render/tiles.mbtiles') as db:
        tile = db.execute('SELECT tile_data FROM tiles WHERE zoom_level=13 LIMIT 1').fetchone()[0]
    assert set(decoder.decode(tile)) == {'places','streets','water','green'}
    build('anchors',source,c,{'fixture':True},tmp_path)
    anchors = json.loads((tmp_path/'anchors/road-candidates.json').read_text())
    assert anchors['candidates'] == [{'zoneId':'hanoi','coordinate':[105.,21.]},
                                    {'zoneId':'hanoi','coordinate':[105.001,21.]}]
