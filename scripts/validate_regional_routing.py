"""Independent Bac Ninh source/node, directed OD and profile-fixture audit.

Requires local CAR and MOTORBIKE routers started by the identity-checking pipeline.
Generic generated access/barrier/turn cases are rerun into R1a evidence; historical
Hanoi evidence and validator bytes are never changed.
"""
import argparse
import asyncio
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from backend.app.config import Settings
from backend.app.dataset import router_status
from backend.app.fleet import candidate_catalog
from backend.app.integrity import digest
from backend.app.modes import resolve_mode, routing_identity
from backend.app.regions import default_registry
from scripts.pipeline import Osmium, write_json
from scripts.regional_resources import preflight

REGION = 'nvmr-bac-ninh-core'


def assert_table_route_consistency(table_duration, response):
    """Compare identical raw OD inputs without hiding snapping discrepancies."""
    if response['code'] == 'NoRoute':
        if table_duration is not None:
            raise RuntimeError('Directed Table/route reachability mismatch')
    elif response['code'] == 'Ok':
        if response['routes'][0]['duration'] != table_duration:
            raise RuntimeError('Directed Table/route duration mismatch; inspect raw inputs/snaps')
    else:
        raise RuntimeError('Unexpected bounded OD failure')


def source_oneways(context, output):
    streets = json.loads(context.map_path.read_text(encoding='utf-8'))
    candidates = []
    w,s,e,n = context.operating_bbox
    for feature in sorted(streets['features'], key=lambda x: str(x.get('id',''))):
        props = feature.get('properties', {})
        points = feature['geometry'].get('coordinates', [])
        if (props.get('oneway') == 'yes' and props.get('highway') in {'residential','tertiary','secondary','primary'}
                and feature['geometry']['type'] == 'LineString' and len(points) >= 2
                and all(w < p[0] < e and s < p[1] < n for p in points)):
            candidates.append(feature['id'])
        if len(candidates) >= 16:
            break
    if not candidates:
        raise RuntimeError('No source one-way candidates in operating area')
    raw = Osmium(Settings(),False).run(['getid',context.extracted_path,*candidates,'-r','-f','osm'],capture=True)
    (output/'source-oneway-ways.xml').write_text(raw,encoding='utf-8')
    tree = ET.fromstring(raw)
    nodes = {int(n.attrib['id']): [float(n.attrib['lon']),float(n.attrib['lat'])] for n in tree.findall('node')}
    return nodes, [way for way in tree.findall('way') if 'w'+way.attrib['id'] in candidates]


def oneway_audit(context, nodes, ways, client):
    records = []
    for way in ways:
        refs = [int(n.attrib['ref']) for n in way.findall('nd')]
        if len(refs) < 2:
            continue
        tags = {t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
        forbidden = {(b,a) for a,b in zip(refs,refs[1:])}
        forward_edges = set(zip(refs,refs[1:]))
        # Interior source-node pair, so short source way directions get exercised.
        a,b = max(zip(refs,refs[1:]), key=lambda p: sum((x-y)**2 for x,y in zip(nodes[p[0]],nodes[p[1]])))
        start = [x*.8+y*.2 for x,y in zip(nodes[a],nodes[b])]
        end = [x*.2+y*.8 for x,y in zip(nodes[a],nodes[b])]
        result = []
        exercised = False
        for origin,destination in ((start,end),(end,start)):
            coords = ';'.join(','.join(map(str,p)) for p in (origin,destination))
            raw = client.get(context.osrm_base_url+'/route/v1/driving/'+coords,
                params={'radiuses':'2;2','annotations':'nodes','overview':'full','geometries':'geojson'}).json()
            edges = set()
            if raw['code'] == 'Ok':
                sequence = raw['routes'][0]['legs'][0]['annotation']['nodes']
                edges = set(zip(sequence,sequence[1:]))
                if edges & forbidden:
                    raise RuntimeError(f'Forbidden source one-way edge: {context.id} {way.attrib["id"]}')
                exercised = exercised or bool(edges & forward_edges)
            result.append(raw)
        if exercised:
            records.append({'osmWay': way.attrib['id'], 'tags':tags, 'sourceNodes':refs,
                            'forbiddenReversedEdges':0, 'routes':result})
        if len(records) == 2:
            break
    if len(records) < 2:
        raise RuntimeError('Need two exercised source one-way examples per mode')
    return records


def boundary_audit(context, destination, client):
    """Exercise actual street vertices nearest all four operating-area corners."""
    collection = json.loads(context.map_path.read_text(encoding='utf-8'))
    w,s,e,n = context.operating_bbox
    vertices = [p for f in collection['features']
        if f.get('geometry',{}).get('type') == 'LineString'
        and f.get('properties',{}).get('highway') in {'primary','secondary','tertiary','residential','unclassified'}
        for p in f['geometry']['coordinates'] if w < p[0] < e and s < p[1] < n]
    if not vertices:
        raise RuntimeError('No source vertices inside operating boundary')
    records = []
    for corner in ((w,s),(w,n),(e,s),(e,n)):
        origin = min(vertices, key=lambda p: sum((x-y)**2 for x,y in zip(p,corner)))
        coords = ';'.join(','.join(map(str,p)) for p in (origin,destination))
        response = client.get(context.osrm_base_url+'/route/v1/driving/'+coords,
            params={'radiuses':';'.join([str(context.max_snap_meters)]*2),
                    'overview':'full','geometries':'geojson'}).json()
        if response['code'] == 'Ok':
            route = response['routes'][0]
            rw,rs,re,rn = context.routing_bbox
            if not (0 < route['distance'] < math.inf and 0 < route['duration'] < math.inf
                    and len(route['geometry']['coordinates']) >= 2
                    and all(rw <= p[0] <= re and rs <= p[1] <= rn for p in route['geometry']['coordinates'])
                    and all(p['distance'] <= context.max_snap_meters for p in response['waypoints'])):
                raise RuntimeError('Invalid near-operating-boundary route')
        elif response['code'] not in {'NoRoute','NoSegment'}:
            raise RuntimeError('Unexpected near-operating-boundary route failure')
        records.append({'operatingCorner':corner,'sourceVertex':origin,'destination':destination,'response':response})
    if sum(r['response']['code']=='Ok' for r in records) < 3:
        raise RuntimeError('Need at least three reachable near-boundary route samples per mode')
    return records


def audit(contexts, output):
    nodes, ways = source_oneways(contexts['CAR'], output)
    result = {'regionId':REGION, 'extractSha256':digest(contexts['CAR'].extracted_path),
              'routingIdentities':{}, 'modes':{}, 'scope':'static OSM source interpretation; no traffic or legal signage claim'}
    with httpx.Client(trust_env=False,timeout=10) as client:
        for mode,context in contexts.items():
            if asyncio.run(router_status(context))['state'] != 'connected':
                raise RuntimeError(f'Router identity not connected: {mode}')
            catalog = candidate_catalog(context)
            points = [c['coordinate'] for c in catalog['candidates']]
            if len(points) < 12:
                raise RuntimeError('Insufficient geographically spread road anchors')
            snaps = []
            for point in points:
                raw = client.get(context.osrm_base_url+'/nearest/v1/driving/'+','.join(map(str,point)),
                                 params={'radiuses':str(context.max_snap_meters)}).json()
                if raw['code'] != 'Ok' or raw['waypoints'][0]['distance'] > context.max_snap_meters:
                    raise RuntimeError(f'Candidate exceeds snap threshold: {mode} {point}')
                snaps.append(raw['waypoints'][0])
            coords = ';'.join(','.join(map(str,p)) for p in points)
            table = client.get(context.osrm_base_url+'/table/v1/driving/'+coords,
                               params={'annotations':'duration,distance',
                                       'radiuses':';'.join([str(context.max_snap_meters)]*len(points))}).json()
            if table['code'] != 'Ok':
                raise RuntimeError('Directed table unavailable')
            nulls = sum(v is None for row in table['durations'] for v in row)
            routes, unreachable = [], []
            for i in range(min(12,len(points))):
                a,b = points[i],points[-1-i]
                coords = ';'.join(','.join(map(str,p)) for p in (a,b))
                raw = client.get(context.osrm_base_url+'/route/v1/driving/'+coords,
                                 params={'radiuses':';'.join([str(context.max_snap_meters)]*2),
                                         'overview':'full','geometries':'geojson'}).json()
                assert_table_route_consistency(table['durations'][i][-1-i], raw)
                if raw['code'] != 'Ok':
                    if raw['code'] != 'NoRoute':
                        raise RuntimeError('Unexpected bounded OD failure')
                    # Explicit disconnected-component evidence, never a fabricated line.
                    unreachable.append({'origin':a,'destination':b,'response':raw})
                    continue
                route = raw['routes'][0]
                w,s,e,n = context.routing_bbox
                valid = (0 < route['distance'] < math.inf and 0 < route['duration'] < math.inf
                         and len(route['geometry']['coordinates']) >= 2
                         and all(w <= p[0] <= e and s <= p[1] <= n for p in route['geometry']['coordinates']))
                if not valid:
                    raise RuntimeError('Invalid metrics/geometry or route outside routing coverage')
                routes.append({'origin':a,'destination':b,'response':raw})
            if len(routes) < 10:
                raise RuntimeError('Need at least ten reachable directed full-geometry samples per mode')
            nosegment = client.get(context.osrm_base_url+'/route/v1/driving/0,0;0.001,0.001',
                                   params={'radiuses':'1;1'}).json()
            if nosegment['code'] != 'NoSegment':
                raise RuntimeError('Expected bounded-snap NoSegment')
            result['routingIdentities'][mode] = routing_identity(context)
            result['modes'][mode] = {'candidateCount':len(points), 'snaps':snaps,
                'directedTablePairs':len(points)*(len(points)-1), 'nullPairs':nulls,
                'unreachableRatio':nulls/(len(points)*(len(points)-1)),
                'unreachableReason':'OSM graph components / bounded snapping; no graph or mode fallback',
                'table':table,'tableRouteConsistencySamples':min(12,len(points)),
                'fullGeometryRoutes':routes,'noRouteCases':unreachable,
                'operatingBoundaryRoutes':boundary_audit(context,points[0],client),
                'oneWaySourceCases':oneway_audit(context,nodes,ways,client), 'noSegment':nosegment}
    result.update(status='PASS', notVerified=['Full administrative province coverage',
        'Observed traffic ETA calibration or current official signs',
        'All possible OD pairs beyond the directed candidate table and selected route samples',
        'Exhaustive real-world turn/barrier/conditional-access restrictions outside sampled source ways'])
    write_json(output/'regional-routing.json',result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-synthetic', action='store_true', help='Reuse verified R1a profile fixture evidence only')
    args = parser.parse_args()
    registry = default_registry(Settings())
    contexts = {mode:resolve_mode(registry,REGION,mode) for mode in ('CAR','MOTORBIKE')}
    preflight(contexts['CAR'],'independent-validation')
    output = ROOT/'docs/nvmr/r1a-evidence/gis'/REGION
    output.mkdir(parents=True,exist_ok=True)
    pending = contexts['MOTORBIKE'].routing_dir/'.validation-incomplete'
    pending.write_text('Independent regional validation pending',encoding='utf-8')
    if not args.skip_synthetic:
        from scripts.validate_motorbike import synthetic
        synthetic(output)
    fixture = json.loads((output/'synthetic-validation.json').read_text(encoding='utf-8'))
    if fixture['status'] != 'PASS' or fixture['profile_sha256'] != digest(ROOT/'profiles/motorbike.lua'):
        raise RuntimeError('Independent generated profile fixture evidence stale or failed')
    audit(contexts,output)
    write_json(contexts['MOTORBIKE'].routing_dir/'validation.json', {
        'status':'PASS','regionId':REGION,'manifest_sha256':digest(contexts['MOTORBIKE'].routing_dir/'manifest.json'),
        'validator_sha256':digest(Path(__file__)),
        'evidence_sha256': {name:digest(output/name) for name in ('synthetic-validation.json','regional-routing.json')},
        'scope':'Independent generated access/oneway/turn/barrier fixtures plus local Bac Ninh directed source-node/OD audit'})
    pending.unlink()
    print('PASS independent Bac Ninh routing validation')


if __name__ == '__main__':
    main()
