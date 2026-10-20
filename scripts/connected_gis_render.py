"""Streaming real OSM into spatial SQLite, then viewport-sized offline MVT tiles."""
import json
import math
import sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from scripts.pipeline import sha256,write_json
from scripts.m3_resources import Monitor

EXTENT=20037508.342789244


def native_filters(osmium):
    """Filter callbacks after native location/area processing, preserving refs."""
    return [osmium.filter.KeyFilter('place').enable_for(osmium.osm.osm_entity_bits.NODE),
            osmium.filter.KeyFilter('highway','waterway').enable_for(osmium.osm.osm_entity_bits.WAY),
            osmium.filter.KeyFilter('natural','landuse','leisure','boundary').enable_for(osmium.osm.osm_entity_bits.AREA)]


def mercator(lon,lat):
    return lon*EXTENT/180,math.log(math.tan((90+lat)*math.pi/360))*EXTENT/math.pi


def build(action,extract,c,identity,out):
    import osmium
    import shapely
    from shapely.geometry import LineString,Point,box
    from shapely.ops import transform
    import mapbox_vector_tile
    folder=out/'render';folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'manifest.json';incomplete=folder/'.incomplete'
    if action=='render' and manifest.exists():
        from scripts.connected_gis import verify_render
        verify_render();print('REUSE verified basemap');return
    dbpath=folder/'features.sqlite'
    dbmanifest=folder/'features-manifest.json'
    if not dbmanifest.exists():
        if incomplete.exists() or dbpath.exists():raise RuntimeError('Incomplete geometry database; refusing overwrite')
        incomplete.write_text('native real-OSM geometry/MVT build incomplete')
        db=sqlite3.connect(dbpath)
        db.execute('CREATE TABLE features(id INTEGER PRIMARY KEY,layer TEXT,minzoom INTEGER,geometry BLOB,properties TEXT)')
        db.execute('CREATE VIRTUAL TABLE bounds USING rtree(id,minx,maxx,miny,maxy)')
        db.execute('CREATE TABLE anchors(zone TEXT,lon REAL,lat REAL,cell TEXT,PRIMARY KEY(zone,lon,lat))')
        counts=Counter();anchor_cells=Counter();errors=Counter();admin_extents=[];source_oneways=[];factory=osmium.geom.WKBFactory();frame=box(*c['mapBbox']);cell_degrees=c['distribution']['cellDegrees']
        def store(layer,geometry,properties,minzoom):
            if geometry.is_empty or not geometry.intersects(frame):return
            if not geometry.is_valid:geometry=shapely.make_valid(geometry)
            geometry=transform(mercator,geometry.intersection(frame))
            cursor=db.execute('INSERT INTO features(layer,minzoom,geometry,properties) VALUES(?,?,?,?)',(layer,minzoom,geometry.wkb,json.dumps(properties,ensure_ascii=False)))
            w,s,e,n=geometry.bounds;db.execute('INSERT INTO bounds VALUES(?,?,?,?,?)',(cursor.lastrowid,w,e,s,n));counts[layer]+=1
            if sum(counts.values())%100000==0:
                db.commit();print(f'OSM geometry features: {dict(counts)}',flush=True)
        class Handler(osmium.SimpleHandler):
            def node(self,node):
                if node.tags.get('place') and node.tags.get('name'):
                    store('places',Point(node.location.lon,node.location.lat),{'name':node.tags['name'],'place':node.tags['place']},6 if node.tags['place'] in ('city','town') else 11)
            def way(self,way):
                highway=way.tags.get('highway')
                if not highway and not way.tags.get('waterway'):return
                try:points=[(p.lon,p.lat) for p in way.nodes]
                except osmium.InvalidLocationError:errors['missing_way_location']+=1;return
                if len(points)<2:return
                props={k:way.tags[k] for k in ('name','highway','waterway') if k in way.tags}
                if highway:
                    if len(source_oneways)<64 and way.tags.get('oneway')=='yes' and highway in ('primary','secondary','tertiary','residential'):
                        w,s,e,n=c['operatingZones'][0]['bbox']
                        if all(w<lon<e and s<lat<n for lon,lat in points):source_oneways.append({'id':way.id,'nodes':[{'id':node.ref,'coordinate':point} for node,point in zip(way.nodes,points)],'tags':dict(way.tags)})
                    z=6 if highway in ('motorway','trunk','primary','motorway_link','trunk_link','primary_link') else 8 if highway in ('secondary','secondary_link') else 9 if highway in ('tertiary','tertiary_link') else 11 if highway in ('residential','unclassified','living_street') else 12
                    store('streets',LineString(points),props,z)
                    if highway in ('primary','secondary','tertiary','residential','unclassified','living_street','service'):
                        for lon,lat in points:
                            for zone in c['operatingZones']:
                                w,s,e,n=zone['bbox']
                                if w<=lon<e and s<=lat<n:
                                    cell=f'{math.floor(lon/cell_degrees)}:{math.floor(lat/cell_degrees)}';key=(zone['id'],cell)
                                    if anchor_cells[key]<c['distribution']['maxAnchorsPerCell']:
                                        inserted=db.execute('INSERT OR IGNORE INTO anchors VALUES(?,?,?,?)',(zone['id'],lon,lat,cell)).rowcount
                                        anchor_cells[key]+=inserted
                                    break
                else:store('water',LineString(points),props,8)
            def area(self,area):
                if area.tags.get('admin_level')=='4' and area.tags.get('boundary')=='administrative':
                    try:
                        g=shapely.from_wkb(bytes.fromhex(factory.create_multipolygon(area)))
                        admin_extents.append({'osmAreaId':area.id,'name':area.tags.get('name',''),'nameEn':area.tags.get('name:en',''),'bbox':list(g.bounds),'fullyWithinMap':frame.covers(g)})
                    except (RuntimeError,ValueError,shapely.errors.GEOSException):errors['invalid_admin_area']+=1
                water=area.tags.get('natural')=='water';green=area.tags.get('landuse') in ('forest','grass','recreation_ground') or area.tags.get('leisure') in ('park','garden') or area.tags.get('natural') in ('wood','scrub')
                if not(water or green):return
                try:
                    g=shapely.from_wkb(bytes.fromhex(factory.create_multipolygon(area)))
                    store('water' if water else 'green',g,{k:area.tags[k] for k in ('name','natural','landuse','leisure') if k in area.tags},6 if water else 8)
                except (RuntimeError,ValueError,shapely.errors.GEOSException):errors['invalid_area']+=1
        # Locations and AreaManager receive all required source references before
        # the entity-scoped native filters; avoid Python callbacks for millions
        # of untagged road/building nodes and irrelevant building-only areas.
        with Monitor(.5) as monitor:Handler().apply_file(str(extract),locations=True,idx='sparse_file_array',filters=native_filters(osmium))
        db.commit();db.close()
        write_json(folder/'osm-administrative-extents.json',{'sourceSha256':c['source']['sha256'],'extractSha256':sha256(extract),'note':'OSM descriptive extents for coverage audit; not authoritative legal boundaries or operating membership','areas':admin_extents})
        write_json(folder/'source-oneways.json',{'sourceSha256':c['source']['sha256'],'extractSha256':sha256(extract),'ways':source_oneways})
        write_json(dbmanifest,{'identity':identity,'extract_sha256':sha256(extract),'sha256':sha256(dbpath),'counts':dict(counts),'errors':dict(errors),'resources':monitor.result()})
    else:
        m=json.loads(dbmanifest.read_text(encoding='utf-8'))
        if m['identity']!=identity or m['extract_sha256']!=sha256(extract) or m['sha256']!=sha256(dbpath):raise RuntimeError('Geometry database input mismatch')
    db=sqlite3.connect(dbpath)
    if action=='anchors':
        path=out/'anchors/road-candidates.json'
        if path.exists():print('REUSE road anchor catalog');return
        # Round-robin cells avoids selecting only densely mapped urban streets.
        cells=defaultdict(list)
        for zone,lon,lat,cell in db.execute('SELECT zone,lon,lat,cell FROM anchors ORDER BY zone,cell,lon,lat'):
            cells[(zone,cell)].append([lon,lat])
        selected=[]
        for zone in c['operatingZones']:
            buckets=[v for (z,_),v in sorted(cells.items()) if z==zone['id']]
            target=12000 if zone['id']=='hanoi' else 2500
            for i in range(c['distribution']['maxAnchorsPerCell']):
                for bucket in buckets:
                    if i<len(bucket):selected.append({'zoneId':zone['id'],'coordinate':bucket[i]})
                if sum(x['zoneId']==zone['id'] for x in selected)>=target:break
        write_json(path,{'schemaVersion':'connected-road-candidates/v1','identity':identity,'sourceSha256':c['source']['sha256'],'extractSha256':sha256(extract),'boundaryVersion':c['boundaryVersion'],'candidates':selected,'provenance':'Real OSM road vertices, eligible highway classes; OSRM snap/access required per mode before simulation'})
        print(Counter(x['zoneId'] for x in selected));return
    archive=folder/'tiles.mbtiles'
    if archive.exists():raise RuntimeError('Refusing overwrite of tile archive')
    tile_db=sqlite3.connect(archive);tile_db.execute('CREATE TABLE metadata(name TEXT,value TEXT)');tile_db.execute('CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB,PRIMARY KEY(zoom_level,tile_column,tile_row))')
    tile_db.executemany('INSERT INTO metadata VALUES(?,?)',[(k,str(v)) for k,v in {'name':'Connected NVMR real OSM offline basemap','format':'pbf','minzoom':6,'maxzoom':13,'bounds':','.join(map(str,c['mapBbox'])),'attribution':c['source']['attribution']}.items()])
    bounds=[mercator(c['mapBbox'][0],c['mapBbox'][1]),mercator(c['mapBbox'][2],c['mapBbox'][3])];tile_counts={}
    with Monitor(.5) as monitor:
        for z in range(6,14):
            scale=2**z;size=2*EXTENT/scale
            x0=int((bounds[0][0]+EXTENT)/size);x1=int((bounds[1][0]+EXTENT)/size)
            y0=int((EXTENT-bounds[1][1])/size);y1=int((EXTENT-bounds[0][1])/size);count=0
            for x in range(x0,x1+1):
                for y in range(y0,y1+1):
                    w=x*size-EXTENT;e=w+size;n=EXTENT-y*size;s=n-size;clip=box(w,s,e,n);layers=defaultdict(list)
                    for fid,layer,wkb,props in db.execute('SELECT f.id,f.layer,f.geometry,f.properties FROM features f JOIN bounds b ON f.id=b.id WHERE f.minzoom<=? AND b.minx<=? AND b.maxx>=? AND b.miny<=? AND b.maxy>=?',(z,e,w,n,s)):
                        geometry=shapely.from_wkb(wkb).intersection(clip)
                        if geometry.is_empty:continue
                        # Scale-aware geometry simplification, preserving real geometry.
                        if geometry.geom_type!='Point':geometry=geometry.simplify(size/4096*.6,preserve_topology=True)
                        if geometry.geom_type not in ('Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon'):continue
                        layers[layer].append({'id':fid,'geometry':geometry,'properties':json.loads(props)})
                    if not layers:continue
                    payload=mapbox_vector_tile.encode([{'name':name,'features':features} for name,features in sorted(layers.items())],default_options={'quantize_bounds':(w,s,e,n),'extents':4096})
                    tile_db.execute('INSERT INTO tiles VALUES(?,?,?,?)',(z,x,scale-1-y,payload));count+=1
            tile_db.commit();tile_counts[str(z)]=count;print(f'MVT zoom {z}: {count} tiles',flush=True)
    tile_db.close();db.close()
    write_json(manifest,{'identity':identity,'source_sha256':c['source']['sha256'],'extract_sha256':sha256(extract),'map_bbox':c['mapBbox'],'minzoom':6,'maxzoom':13,'source_layers':c['tiles']['sourceLayers'],'format':'mvt','scheme':'tms','artifact_sha256':{'tiles.mbtiles':sha256(archive)},'tile_counts':tile_counts,'features':json.loads(dbmanifest.read_text(encoding='utf-8'))['counts'],'resources':monitor.result(),'attribution':c['source']['attribution'],'limitations':['OSM area assembly may skip invalid input areas; counters recorded','No buildings layer; all road classes available z12-13, detailed tiles overzoom above13','Technical operating rectangles are not administrative boundaries']})
    incomplete.unlink()
