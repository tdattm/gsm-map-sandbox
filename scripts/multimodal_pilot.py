"""Live local CAR/MOTORBIKE pilot; synthetic demand, real separately built routers."""
import asyncio
import json
import sys
import socket
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.config import Settings
from backend.app.regions import default_registry
from backend.app.regions import RegionRegistry
from backend.app.modes import resolve_mode
from backend.app.dataset import router_status
import httpx
from scripts.pipeline import write_json


def run(write=True):
    app=create_app();prefix='/api/v2/regions/nvmr-hanoi-core'
    config=dict(seed='hanoi-multimodal-m2',fleetSize=10,bookingCount=20,horizonSeconds=1800,
        maxWaitSeconds=300,preset='Medium',vehicleTypes=['CAR','MOTORBIKE']*5,serviceTypes=['CAR','MOTORBIKE']*10)
    def semantic(raw):return {**raw,'plan':{k:v for k,v in raw['plan'].items() if k not in ('createdAt','preparationMilliseconds')}}
    with TestClient(app) as client:
        modes=client.get(prefix+'/modes').json()
        assert all(m['ready'] for m in modes['modes']),modes
        raw=[]
        for _ in range(2):
            response=client.post(prefix+'/booking-simulation/prepare',json=config)
            assert response.status_code==200,response.text
            raw.append(response.json())
        assert semantic(raw[0])==semantic(raw[1]),'Semantic outcome drift'
        plan=raw[0]['plan'];vehicles={v['id']:v['vehicleType'] for v in plan['vehicles']};demand={b['id']:b['serviceType'] for b in plan['demand']}
        ends={};counts={'CAR':0,'MOTORBIKE':0}
        for a in plan['assignments']:
            mode=vehicles[a['vehicleId']]
            assert mode==demand[a['bookingId']]==a['vehicleType']==a['routingIdentity']['vehicleType']
            assert all(vehicles[c['vehicleId']]==mode for c in a['dispatchCandidates'])
            assert a['assignedAtSeconds']>=ends.get(a['vehicleId'],0)
            ends[a['vehicleId']]=a['dropoffAtSeconds'];counts[mode]+=1
        single=[]
        for mode in ('CAR','MOTORBIKE'):
            r=client.post(prefix+f'/modes/{mode}/route',json={'start':[105.841,21.028],'end':[105.832,21.039]})
            assert r.status_code==200,r.text
            single.append(r.json())
        assert single[0]['routingIdentity']['graphManifestSha256']!=single[1]['routingIdentity']['graphManifestSha256']
        assert single[0]['routingIdentity']['profileSha256']!=single[1]['routingIdentity']['profileSha256']
        def concurrent(mode):
            r=client.post(prefix+f'/modes/{mode}/route',json={'start':[105.841,21.028],'end':[105.832,21.039]})
            assert r.status_code==200,(r.status_code,r.text)
            return r.json()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(concurrent,['CAR','MOTORBIKE']*4))
        assert all(r['routingIdentity']['vehicleType']==m for r,m in zip(results,['CAR','MOTORBIKE']*4))
        hcm=client.post('/api/route',json={'start':[106.698,10.772],'end':[106.703,10.777]})
        assert hcm.status_code==200,hcm.text
    context=resolve_mode(default_registry(Settings()),'nvmr-hanoi-core','MOTORBIKE')
    wrong=asyncio.run(router_status(replace(context,osrm_base_url='http://127.0.0.1:5001')))
    assert wrong['state']=='identity_mismatch'
    # A real connection failure in a private immutable CAR context, without
    # stopping either actual router or changing the server's allowlist/config.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0)); closed_port=probe.getsockname()[1]
    registry=default_registry(Settings())
    car=replace(registry.resolve('nvmr-hanoi-core'),osrm_base_url=f'http://127.0.0.1:{closed_port}')
    isolated=RegionRegistry({**registry.contexts,car.id:car})
    with TestClient(create_app(registry=isolated)) as negative:
        body={'start':[105.841,21.028],'end':[105.832,21.039]}
        failure=negative.post(prefix+'/modes/CAR/route',json=body)
        still_motor=negative.post(prefix+'/modes/MOTORBIKE/route',json=body)
        assert failure.status_code==503 and failure.json()['error']['code']=='ROUTER_UNAVAILABLE'
        assert still_motor.status_code==200 and still_motor.json()['routingIdentity']['vehicleType']=='MOTORBIKE'
    from backend.app.multimodal import mode_catalog
    points=[c['coordinate'] for c in mode_catalog(context)['candidates']]
    with httpx.Client(trust_env=False,timeout=10) as router:
        nearest=[router.get(context.osrm_base_url+'/nearest/v1/driving/'+','.join(map(str,p)),params={'radiuses':'100'}).json() for p in points]
        assert all(n['code']=='Ok' and n['waypoints'][0]['distance']<=100 for n in nearest)
        table=router.get(context.osrm_base_url+'/table/v1/driving/'+';'.join(','.join(map(str,p)) for p in points),
                         params={'annotations':'duration','radiuses':';'.join('100' for _ in points)}).json()
        assert table['code']=='Ok'
    candidate_audit={'count':len(points),'maxSnapMeters':max(n['waypoints'][0]['distance'] for n in nearest),
        'directedNonSelfPairs':len(points)*(len(points)-1),
        'unreachablePairs':sum(v is None for i,row in enumerate(table['durations']) for j,v in enumerate(row) if i!=j),
        'nearest':nearest,'table':table}
    summary={'status':'PASS','schemaVersion':'gsm-multimodal-scenario/v1','config':config,
        'assignedByMode':counts,'completed':sum(e['type']=='TRIP_COMPLETED' for e in plan['events']),
        'unserved':sum(e['type']=='BOOKING_UNSERVED' for e in plan['events']),
        'repeatableSemantic':True,'wrongCarRouterRejected':True,'hcmLiveRoute':True,
        'carOutageIsolatedFromMotorbike':True,'motorbikeCandidateCount':len(points),
        'routingIdentities':raw[0]['routingIdentities'],'singleTrips':single,
        'assumptions':'Synthetic potential, static OSM estimates; not observed GSM riders or calibrated traffic'}
    if write:
        output=ROOT/'docs/nvmr/m2-evidence';output.mkdir(exist_ok=True)
        write_json(output/'mixed-plan.json',raw[0]);write_json(output/'pilot-summary.json',summary)
        write_json(output/'motorbike-candidates.json',candidate_audit)
    return summary


if __name__=='__main__':print(json.dumps(run(),ensure_ascii=True))
