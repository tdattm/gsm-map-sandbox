"""Check full merged-province relation-member extents directly in pinned local PBF.

This is an OSM coverage audit, not certification of official polygons. Technical
operating membership is deliberately independent of mutable OSM admin tags.
"""
import json
from collections import defaultdict
from scripts.connected_gis import ROOT,config,verify_source,base,identity
from scripts.pipeline import write_json


def audit():
    import osmium
    source=verify_source();c=config()
    selected={1903516:'hanoi',1902690:'bac-ninh',1901032:'hung-yen',1902930:'phu-tho',1902967:'thai-nguyen'}
    members={};names={};subrelations=[]
    class Relations(osmium.SimpleHandler):
        def relation(self,r):
            if r.id not in selected:return
            names[r.id]=dict(r.tags)
            members[r.id]={m.ref for m in r.members if m.type=='w' and m.role in ('outer','inner','')}
            subrelations.extend(m.ref for m in r.members if m.type=='r' and m.role in ('outer','inner',''))
    with osmium.io.Reader(str(source),osmium.osm.osm_entity_bits.RELATION) as reader:
        osmium.apply(reader,osmium.filter.IdFilter(selected),Relations())
    if set(members)!=set(selected) or subrelations:raise RuntimeError('Missing selected relations or unsupported nested boundaries')
    way_owners=defaultdict(set)
    for relation,ways in members.items():
        for way in ways:way_owners[way].add(relation)
    node_owners=defaultdict(set);found_ways=set()
    class Ways(osmium.SimpleHandler):
        def way(self,w):
            if w.id not in way_owners:return
            found_ways.add(w.id)
            for p in w.nodes:node_owners[p.ref].update(way_owners[w.id])
    with osmium.io.Reader(str(source),osmium.osm.osm_entity_bits.WAY) as reader:
        osmium.apply(reader,osmium.filter.IdFilter(way_owners),Ways())
    bounds={r:[180.,90.,-180.,-90.] for r in selected};found_nodes=set()
    class Nodes(osmium.SimpleHandler):
        def node(self,n):
            if n.id not in node_owners:return
            found_nodes.add(n.id);lon,lat=n.location.lon,n.location.lat
            for relation in node_owners[n.id]:
                b=bounds[relation];b[0]=min(b[0],lon);b[1]=min(b[1],lat);b[2]=max(b[2],lon);b[3]=max(b[3],lat)
    with osmium.io.Reader(str(source),osmium.osm.osm_entity_bits.NODE) as reader:
        osmium.apply(reader,osmium.filter.IdFilter(node_owners),Nodes())
    missing_ways=set(way_owners)-found_ways;missing_nodes=set(node_owners)-found_nodes
    w,s,e,n=c['mapBbox'];areas=[]
    for rid,zone in selected.items():
        b=bounds[rid]
        areas.append({'zoneId':zone,'relationId':rid,'osmName':names[rid].get('name'),'osmNameEn':names[rid].get('name:en'),'bbox':b,'boundaryWayCount':len(members[rid]),'fullyWithinMap':w<=b[0]<b[2]<=e and s<=b[1]<b[3]<=n,'sourceUrl':f'https://www.openstreetmap.org/relation/{rid}'})
    proof={'schemaVersion':'connected-coverage-audit/v1','identity':identity(),'sourceSha256':c['source']['sha256'],'mapBbox':c['mapBbox'],'routingBbox':c['routingBbox'],'areas':areas,'missingWays':sorted(missing_ways),'missingNodes':sorted(missing_nodes),'allFiveContained':not missing_ways and not missing_nodes and all(a['fullyWithinMap'] for a in areas),'limitations':['OSM labels in this snapshot are inconsistent with official 2025 province names; IDs/extent are audited, legal polygon status NOT claimed','Current-zone membership uses versioned nonoverlapping technical operating zones, never these mutable OSM tags']}
    write_json(base()/'coverage-evidence.json',proof);print(json.dumps(proof,ensure_ascii=False,indent=2))
    if not proof['allFiveContained']:raise RuntimeError('Map rectangle does not cover all selected province extents')


if __name__=='__main__':audit()
