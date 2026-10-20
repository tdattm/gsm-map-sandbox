"""Reproducible opt-in live CAR audit. Requires both verified local routers.

Writes raw API plans and a compact summary; uses real local HTTP OSRM, never a
mock transport for routing. Potential demand/price response remain synthetic.
"""
import argparse
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import httpx
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.fleet import candidate_catalog
from backend.app.integrity import digest
from backend.app.main import create_app, meters
from backend.app.regions import default_registry, RegionRegistry
from backend.app.voucher import stable_draw
from scripts.pipeline import write_json, Osmium


def audit_oneway_nodes(c, output):
    """Compare real OSRM node annotations to independent source way directions."""
    import xml.etree.ElementTree as ET
    way_ids=('408818507','684044681')
    osmium=Osmium(Settings(),False)
    raw=osmium.run(['getid',c.extracted_path,*('w'+w for w in way_ids),'-r','-f','osm'],capture=True)
    tree=ET.fromstring(raw)
    nodes={int(n.attrib['id']):[float(n.attrib['lon']),float(n.attrib['lat'])] for n in tree.findall('node')}
    records=[]
    with httpx.Client(trust_env=False,timeout=10) as router:
        for way in tree.findall('way'):
            if way.attrib['id'] not in way_ids: continue
            tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
            assert tags['oneway']=='yes'
            refs=[int(n.attrib['ref']) for n in way.findall('nd')]
            forbidden={(b,a) for a,b in zip(refs,refs[1:])}
            results=[]
            for start,end in [(nodes[refs[0]],nodes[refs[-1]]),(nodes[refs[-1]],nodes[refs[0]])]:
                response=router.get(c.osrm_base_url+'/route/v1/driving/'+ ';'.join(','.join(map(str,p)) for p in [start,end]),
                    params={'annotations':'nodes','overview':'full','geometries':'geojson','radiuses':'100;100'}).json()
                assert response['code']=='Ok'
                route_nodes=response['routes'][0]['legs'][0]['annotation']['nodes']
                assert not (set(zip(route_nodes,route_nodes[1:])) & forbidden),'Illegal reversed source one-way edge'
                results.append({'start':start,'end':end,'annotatedNodes':route_nodes,'distance':response['routes'][0]['distance']})
            assert any(edge in set(zip(results[0]['annotatedNodes'],results[0]['annotatedNodes'][1:])) for edge in zip(refs,refs[1:])), 'Forward route must exercise the source way'
            records.append(dict(osm_way=way.attrib['id'],tags=tags,sourceNodes=refs,routes=results,illegalReversedEdges=0))
    assert len(records)==2
    evidence=dict(status='PASS',extract_sha256=digest(c.extracted_path),cases=records,
        limitation='Validates OSM one-way interpretation, not current physical signs or traffic conditions')
    write_json(output/'osm-oneway-nodes.json',evidence)
    return evidence['status']


def semantic(value):
    if isinstance(value,dict):
        return {k:semantic(v) for k,v in value.items() if k not in {'createdAt','preparationMilliseconds'}}
    if isinstance(value,list): return [semantic(v) for v in value]
    return value


def check_plan(plan):
    ends={}
    for a in plan['assignments']:
        assert a['assignedAtSeconds']>=ends.get(a['vehicleId'],0)
        assert a['assignedAtSeconds']<=a['pickupAtSeconds']<=a['dropoffAtSeconds']
        ends[a['vehicleId']]=a['dropoffAtSeconds']
    assert sum(e['type']=='TRIP_COMPLETED' for e in plan['events'])==len(plan['assignments'])
    assert sum(e['type'] in ('TRIP_COMPLETED','BOOKING_UNSERVED') for e in plan['events'])==len(plan['demand'])


def check_experiment(e):
    assert e['baseline']['plan']['vehicles']==e['treatment']['plan']['vehicles']
    for p in e['potential']:
        assert p['randomDraw']==stable_draw(e['seed'],e['datasetFingerprint'],p['passengerId'])
    for name in ('baseline','treatment'):
        arm=e[name]; check_plan(arm['plan'])
        assert {d['potentialId'] for d in arm['decisions'] if d['accepted']}=={d['id'] for d in arm['plan']['demand']}
        reserved={}; spent=0
        for event in arm['ledger']:
            key=event['bookingId']; amount=event['amountVnd']
            if event['type']=='RESERVED': assert key not in reserved; reserved[key]=amount
            if event['type'] in ('SETTLED','RELEASED'):
                assert reserved.pop(key)==amount
                if event['type']=='SETTLED': spent+=amount
            assert event['reserved']==sum(reserved.values())
            assert event['total']==event['available']+event['reserved']+event['spent']
        assert not reserved and spent==e['final'][name]['voucherSpendVnd']
        m=e['final'][name]
        assert m['grossFareVnd']==m['riderPaymentsVnd']+m['voucherSpendVnd']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/regions/nvmr-hanoi-core/pilot')
    args=parser.parse_args(); output=args.output
    registry=default_registry(Settings()); c=registry.resolve('nvmr-hanoi-core')
    client=TestClient(create_app(registry=registry)); base='/api/regions/nvmr-hanoi-core'
    summary={'kind':'live local CAR; synthetic modeled demand, not GSM observations','checks':{},'routes':[]}
    summary['checks']['osmOneWayNodeAnnotations']=audit_oneway_nodes(c,output)
    def post(path,config):
        r=client.post(base+path,json=config); assert r.status_code==200,(path,r.status_code,r.text)
        return r.json()
    for region_id in registry.contexts:
        r=client.get(f'/api/regions/{region_id}/dataset/status').json()
        assert r['ready'],r
    summary['checks']['bothRegionsReady']='PASS'
    cat=candidate_catalog(c); coords=[p['coordinate'] for p in cat['candidates']]
    snaps=[]
    with httpx.Client(trust_env=False,timeout=10) as router:
        for p in cat['candidates']:
            w=router.get(c.osrm_base_url+'/nearest/v1/driving/'+','.join(map(str,p['coordinate']))).json()['waypoints'][0]
            assert w['distance']<=c.max_snap_meters
            assert meters(p['coordinate'],w['location'])<=c.max_snap_meters+1
            snaps.append({'candidateId':p['id'],'location':w['location'],'distance':w['distance']})
        data=router.get(c.osrm_base_url+'/table/v1/driving/'+';'.join(','.join(map(str,p)) for p in coords)).json()
        assert data['code']=='Ok' and len(data['durations'])==len(coords)
        nulls=sum(v is None for row in data['durations'] for v in row)
        assert nulls==0,'Disconnected candidate OD pairs'
    write_json(output/'candidate-audit.json',dict(datasetFingerprint=cat['datasetFingerprint'],snaps=snaps,
        directedTablePairs=len(coords)*(len(coords)-1),nullPairs=nulls,provenance=cat['provenance']))
    # Expected one-way direction comes from the OSM feature tag/vertex order,
    # independently of OSRM route output. These are technical checks of OSM
    # interpretation, not authoritative real-world traffic restriction validation.
    streets=json.loads(c.map_path.read_text(encoding='utf-8'))
    for osm_id in ('w408818507','w684044681'):
        f=next(f for f in streets['features'] if f['id']==osm_id)
        assert f['properties']['oneway']=='yes'
        points=f['geometry']['coordinates']
        a=[points[0][i]*.8+points[1][i]*.2 for i in range(2)]
        b=[points[-2][i]*.2+points[-1][i]*.8 for i in range(2)]
        forward=post('/route',{'start':a,'end':b}); reverse=post('/route',{'start':b,'end':a})
        assert reverse['distance']>forward['distance']*1.1,(osm_id,forward['distance'],reverse['distance'])
        summary['routes'].append(dict(osm_id=osm_id,name=f['properties']['name'],oneway='yes',start=a,end=b,
            expected='reverse detours; OSM oneway=yes',forwardMeters=forward['distance'],reverseMeters=reverse['distance']))
        write_json(output/f'{osm_id}-forward.json',forward); write_json(output/f'{osm_id}-reverse.json',reverse)
    for i in range(10):
        route=post('/route',{'start':coords[i],'end':coords[23-i]})
        assert route['distance']>0 and route['duration']>0 and len(route['coordinates'])>2
        write_json(output/f'od-{i:02}.json',route)
    # Outside display, within buffered graph: Single Trip must accept it.
    route=post('/route',{'start':[105.790,21.030],'end':coords[0]})
    assert any(p[0]<c.region.display_bbox[0] for p in route['coordinates'])
    write_json(output/'outside-viewport-route.json',route)
    for config,code in [({'start':[181,21],'end':coords[0]},'INVALID_COORDINATES'),
                        ({'start':[106.7,10.77],'end':coords[0]},'OUTSIDE_ROUTING_REGION'),
                        ({'start':coords[0],'end':coords[0]},'IDENTICAL_POINTS'),
                        ({'start':[105.85,21.07],'end':coords[0]},'NOSEGMENT')]:
        r=client.post(base+'/route',json=config)
        assert r.status_code==422 and r.json()['error']['code']==code,(config,r.status_code,r.text)
    summary['checks']['directedRoutesAndBoundaries']='PASS'
    config={'seed':'hanoi-car-m1b-2026','fleetSize':5,'bookingCount':20}
    plan=post('/booking-simulation/prepare',config); check_plan(plan)
    assert semantic(plan)==semantic(post('/booking-simulation/prepare',config))
    write_json(output/'booking.json',plan)
    config={'seed':'hanoi-car-m1b-2026','fleetSize':5,'potentialCount':20}
    e=post('/voucher-experiment/prepare',config); check_experiment(e)
    assert semantic(e)==semantic(post('/voucher-experiment/prepare',config))
    write_json(output/'voucher.json',e)
    zero=post('/voucher-experiment/prepare',{**config,'campaignBudget':0}); check_experiment(zero)
    for key in ('demand','vehicles','assignments','events'):
        assert zero['baseline']['plan'][key]==zero['treatment']['plan'][key]
    assert not zero['treatment']['ledger']
    write_json(output/'zero-policy.json',zero)
    stress=post('/voucher-experiment/prepare',{**config,'maxWaitSeconds':10})
    check_experiment(stress)
    assert stress['final']['treatment']['voucherCounts']['RELEASED']>0
    write_json(output/'short-wait-release.json',stress)
    summary['shortWaitTreatment']=stress['final']['treatment']
    summary['checks']['repeatabilityPairingLedgerLifecycleZeroPolicy']='PASS'
    # Explicit wrong graph/outage, using local contexts only; never mutate global selection.
    for url,code in [('http://127.0.0.1:5000','ROUTER_IDENTITY_MISMATCH'),('http://127.0.0.1:5998','ROUTER_UNAVAILABLE')]:
        wrong=replace(c,osrm_base_url=url)
        alternate=RegionRegistry({**registry.contexts,c.id:wrong})
        r=TestClient(create_app(registry=alternate)).post(base+'/route',json={'start':coords[0],'end':coords[1]})
        assert r.status_code==503 and r.json()['error']['code']==code,r.text
    async def concurrent():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(registry=registry)),base_url='http://test') as api:
            async def prepare(region_id):
                prefix=f'/api/regions/{region_id}'
                cat=(await api.get(prefix+'/fleet/candidates')).json()
                body={'start':cat['candidates'][0]['coordinate'],'end':cat['candidates'][1]['coordinate']}
                route,experiment=await asyncio.gather(api.post(prefix+'/route',json=body),api.post(prefix+'/voucher-experiment/prepare',json={'fleetSize':5,'potentialCount':10}))
                assert route.status_code==experiment.status_code==200,(route.text,experiment.text)
                value=experiment.json(); check_experiment(value)
                assert value['datasetFingerprint']==cat['datasetFingerprint']
                assert value['provenance'].get('region_id','hcm-center')==region_id
                w,s,e,n=registry.resolve(region_id).routing_bbox
                assert all(w<=x<=e and s<=y<=n for x,y in route.json()['coordinates'])
                return cat['datasetFingerprint']
            return await asyncio.gather(prepare('hcm-center'),prepare(c.id))
    fingerprints=asyncio.run(concurrent()); assert fingerprints[0]!=fingerprints[1]
    summary.update(datasetFingerprint=cat['datasetFingerprint'],candidateCount=len(coords),directedTablePairs=552,
        booking=dict(assignments=len(plan['assignments']),requests=len(plan['demand'])),final=e['final'],comparison=e['comparison'],
        manifestHashes={str(p.relative_to(c.map_path.parent.parent)):digest(p) for p in [c.map_path.parent/'manifest.json',c.routing_dir/'manifest.json']})
    summary['checks']['liveConcurrencyWrongGraphOutage']='PASS'
    summary['notVerified']=['live NoRoute case not deliberately manufactured; fixture coverage exists',
        'OSM restrictions not compared to current official road signage; no live traffic ETA calibration',
        'Hanoi portable replay v2 is deferred to M5']
    write_json(output/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=True,indent=2))


if __name__=='__main__': main()
