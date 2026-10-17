"""M2 synthetic contract/lifecycle tests; live proof is explicitly opt-in."""
import asyncio
import json
import os
import threading
from dataclasses import FrozenInstanceError, replace
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app.booking import PrepareRequest, InitialVehicle, build_plan, LocalTravel
from backend.app.config import Settings
from backend.app.main import create_app, meters
from backend.app.modes import resolve_mode
from backend.app.regions import default_registry
from backend.app.multimodal import MixedRequest
from test_a3 import FixtureTravel, CATALOG, demand, road
from test_regions import registry, write_json


def test_v1_strict_contract_unchanged_and_new_types_explicit():
    assert set(PrepareRequest.model_fields)=={'seed','fleetSize','bookingCount','horizonSeconds','maxWaitSeconds','preset'}
    for extra in ({'vehicleType':'MOTORBIKE'},{'vehicleTypes':['CAR']},{'regionId':'nvmr-hanoi-core'}):
        with pytest.raises(ValidationError):PrepareRequest(**extra)
    value=MixedRequest(vehicleTypes=['CAR']*5,serviceTypes=['MOTORBIKE']*20)
    assert value.fleetSize==5
    for update in ({'vehicleTypes':['BIKE']*5},{'serviceTypes':['CAR']},{'routerUrl':'https://example.org'}):
        with pytest.raises(ValidationError):MixedRequest(**{**value.model_dump(),**update})


def test_pinned_contexts_are_isolated_immutable_and_allowlisted():
    registry=default_registry(Settings())
    def resolve(pair):return resolve_mode(registry,*pair)
    pairs=[('hcm-center','CAR'),('nvmr-hanoi-core','CAR'),('nvmr-hanoi-core','MOTORBIKE')]*20
    with ThreadPoolExecutor(max_workers=8) as pool: contexts=list(pool.map(resolve,pairs))
    assert {c.osrm_base_url for c in contexts}=={'http://127.0.0.1:5000','http://127.0.0.1:5001','http://127.0.0.1:5002'}
    assert len({c.routing_dir for c in contexts})==3
    motor=contexts[2]
    with pytest.raises(FrozenInstanceError):motor.osrm_base_url='http://evil'
    for region,mode,code in [('bad','CAR','UNKNOWN_REGION'),('hcm-center','MOTORBIKE','MODE_NOT_READY'),('nvmr-hanoi-core','BIKE','UNKNOWN_VEHICLE_TYPE')]:
        with pytest.raises(HTTPException) as e:resolve_mode(registry,region,mode)
        assert e.value.detail['code']==code


def mixed_plan(bookings,vehicle_modes,booking_modes,travels):
    initial=[InitialVehicle(id=id,candidateId='fixture',initialPosition=(float(i),0.)) for i,id in enumerate(vehicle_modes)]
    return asyncio.run(build_plan(CATALOG,PrepareRequest(fleetSize=len(initial)),next(iter(travels.values())),
        inputs=bookings,initial=initial,vehicle_modes=vehicle_modes,booking_modes=booking_modes,mode_travel=travels))


def test_shared_dispatcher_filters_type_before_eta_and_never_substitutes():
    vehicles={'car':'CAR','moto':'MOTORBIKE'}
    modes={'B1':'CAR','B2':'MOTORBIKE'}
    plan=mixed_plan([demand('B1'),demand('B2')],vehicles,modes,
        {'CAR':FixtureTravel(lambda *_:30),'MOTORBIKE':FixtureTravel(lambda *_:1)})
    assert {a.bookingId:a.vehicleId for a in plan.assignments}=={'B1':'car','B2':'moto'}
    for a in plan.assignments:
        assert all(vehicles[c.vehicleId]==modes[a.bookingId] for c in a.dispatchCandidates)
    no_car=mixed_plan([demand('B1')],{'moto':'MOTORBIKE'},{'B1':'CAR'},
        {'CAR':FixtureTravel(),'MOTORBIKE':FixtureTravel()})
    assert not no_car.assignments
    assert no_car.events[-1].type=='BOOKING_UNSERVED'


def test_mode_routes_fail_without_substitution_and_conserve_lifecycle():
    class NoRoute(FixtureTravel):
        async def route(self,*args):raise HTTPException(422,{'code':'NOROUTE'})
    args=([demand('B1'),demand('B2')],{'car':'CAR','moto':'MOTORBIKE'},
          {'B1':'CAR','B2':'MOTORBIKE'},{'CAR':FixtureTravel(),'MOTORBIKE':NoRoute()})
    a=mixed_plan(*args);b=mixed_plan(*args)
    assert [x.bookingId for x in a.assignments]==['B1']
    assert a.events[-1].payload=={'failureReason':'NOROUTE'}
    assert a.events==b.events and a.assignments==b.assignments
    class Outage(FixtureTravel):
        async def route(self,*args):raise HTTPException(503,{'code':'ROUTER_UNAVAILABLE'})
    with pytest.raises(HTTPException) as e:
        mixed_plan([demand('B2')],{'moto':'MOTORBIKE'},{'B2':'MOTORBIKE'},{'MOTORBIKE':Outage()})
    assert e.value.status_code==503


def test_mode_cache_and_direction_isolation():
    registry=default_registry(Settings());calls=[]
    async def run():
        adapters=[]
        for mode in ('CAR','MOTORBIKE'):
            context=resolve_mode(registry,'nvmr-hanoi-core',mode)
            async def fetch(req,mode=mode):
                calls.append((mode,req.start,req.end));return road(req.start,req.end,10 if mode=='CAR' else 20)
            adapters.append(LocalTravel(context,fetch,meters))
        a,b=(105.84,21.03),(105.845,21.031)
        for t in adapters:
            await t.route(a,b);await t.route(a,b);await t.route(b,a)
        assert (await adapters[0].route(a,b)).duration==10
        assert (await adapters[1].route(a,b)).duration==20
    asyncio.run(run())
    assert len(calls)==4 and calls[0][1:]==calls[2][1:]


def test_mode_hashes_are_pinned_not_read_again_mid_request(monkeypatch):
    context=resolve_mode(default_registry(Settings()),'nvmr-hanoi-core','MOTORBIKE')
    identity=context.artifact_identity
    monkeypatch.setattr('backend.app.modes.digest',lambda _: 'different-files-after-resolution')
    assert context.artifact_identity==identity


def test_cold_integrity_reads_leave_event_loop_available(monkeypatch):
    """A pending OSRM callback must run while another request reads graph bytes."""
    from backend.app.dataset import dataset_status
    started,release=threading.Event(),threading.Event()
    blocked=[]
    def cold_pbf(_):
        started.set()
        if not release.wait(1):blocked.append(True)
        return {'format_verified':True,'state':'present_verified'}
    monkeypatch.setattr('backend.app.dataset.pbf_status',cold_pbf)
    monkeypatch.setattr('backend.app.dataset.artifact_status',lambda _:{'map_ready':True,'graph_ready':True})
    async def router(_):return {'state':'connected'}
    monkeypatch.setattr('backend.app.dataset.router_status',router)
    async def check():
        async def callback():
            while not started.is_set():await asyncio.sleep(0)
            release.set()
        status,_=await asyncio.gather(dataset_status(Settings()),callback())
        assert status['ready']
    asyncio.run(check())
    assert not blocked,'Synchronous integrity work prevented the OSRM callback from running'


@pytest.mark.parametrize('damage',['graph','profile','identity','validation','marker','evidence'])
def test_motor_artifact_fail_closed_without_disabling_car(registry,tmp_path,monkeypatch,damage):
    from test_m1b import strict_context
    from backend.app.dataset import artifact_status
    from backend.app.integrity import digest
    from backend.app.modes import motor_artifacts
    from backend.app.regions import RegionRegistry
    c,source,render,car_graph=strict_context(registry)
    source={**json.loads((c.map_path.parent.parent/'source-verification.json').read_text()),**source}
    write_json(c.map_path.parent.parent/'source-verification.json',source)
    write_json(c.map_path.parent/'manifest.json',render)
    write_json(c.routing_dir/'manifest.json',car_graph)
    motor=resolve_mode(RegionRegistry({**registry.contexts,c.id:c}),c.id,'MOTORBIKE')
    motor.routing_dir.mkdir()
    files={f'{motor.graph_basename}.osrm.{s}':b'SYNTHETIC TEST GRAPH' for s in ('cells','partition','mldgr')}
    for n,raw in files.items():(motor.routing_dir/n).write_bytes(raw)
    graph=dict(identity=motor.artifact_identity,profile='motorbike',algorithm='mld',profile_sha256=motor.profile_sha256,
        profile_dependencies={**{f'/opt/lib/test-{i}.lua':'fixture' for i in range(24)},'/profiles/motorbike.lua':motor.profile_sha256},
        source_sha256=source['sha256'],extract_sha256=digest(c.extracted_path),routing_bbox=list(c.routing_bbox),
        artifact_sizes={n:len(b) for n,b in files.items()},artifact_sha256={n:digest(motor.routing_dir/n) for n in files})
    write_json(motor.routing_dir/'manifest.json',graph)
    isolated=tmp_path/'validation-fixture';(isolated/'scripts').mkdir(parents=True)
    (isolated/'scripts/validate_motorbike.py').write_text('SYNTHETIC VALIDATOR')
    evidence=isolated/'docs/nvmr/m2-evidence'
    names={'synthetic_sha256':'synthetic-validation.json','real_oneway_sha256':'osm-oneway-nodes.json','directed_cases_sha256':'real-mode-cases.json'}
    for n in names.values():write_json(evidence/n,{'status':'PASS','fixture':True})
    write_json(motor.routing_dir/'validation.json',dict(status='PASS',manifest_sha256=digest(motor.routing_dir/'manifest.json'),
        validator_sha256=digest(isolated/'scripts/validate_motorbike.py'),**{k:digest(evidence/n) for k,n in names.items()}))
    monkeypatch.setattr('backend.app.modes.ROOT',isolated)
    assert artifact_status(c)['graph_ready'] and motor_artifacts(motor)['graph_ready']
    if damage=='graph':(motor.routing_dir/next(iter(files))).write_bytes(b'X'*len(next(iter(files.values()))))
    elif damage=='marker':(motor.routing_dir/'.validation-incomplete').write_text('not validated')
    elif damage=='evidence':write_json(evidence/'real-mode-cases.json',{'status':'FAIL'})
    elif damage=='validation':write_json(motor.routing_dir/'validation.json',{'status':'FAIL'})
    else:
        graph['profile' if damage=='profile' else 'identity']='car' if damage=='profile' else {'region_id':'hcm-center'}
        write_json(motor.routing_dir/'manifest.json',graph)
    assert not motor_artifacts(motor)['graph_ready']
    assert artifact_status(c)['graph_ready']


def test_motor_not_ready_does_not_change_car_api(monkeypatch):
    async def status(c):return {'ready':getattr(c,'vehicle_type','CAR')=='CAR','readinessReason':'fixture unavailable','osrm':{'state':'unavailable'}}
    monkeypatch.setattr('backend.app.main.public_region_status',status)
    monkeypatch.setattr('backend.app.main.routing_identity',lambda c:{'vehicleType':getattr(c,'vehicle_type','CAR')})
    client=TestClient(create_app())
    result=client.get('/api/v2/regions/nvmr-hanoi-core/modes').json()
    assert [m['ready'] for m in result['modes']]==[True,False]
    r=client.post('/api/v2/regions/nvmr-hanoi-core/modes/MOTORBIKE/route',json={'start':[105.84,21.03],'end':[105.85,21.03]})
    assert r.status_code==503
    assert client.get('/api/v2/regions/unknown/modes').status_code==404


@pytest.mark.skipif(os.environ.get('RUN_REAL_DATA')!='1',reason='opt-in local OSRM and verified artifacts')
def test_real_multimodal_repeatability_and_graph_identity():
    from scripts.multimodal_pilot import run
    result=run(write=False)
    assert result['status']=='PASS' and result['assignedByMode']=={'CAR':10,'MOTORBIKE':10}
    from backend.app.multimodal import mode_catalog
    registry=default_registry(Settings())
    for mode in ('CAR','MOTORBIKE'):
        catalog=mode_catalog(resolve_mode(registry,'nvmr-hanoi-core',mode))
        assert catalog['provenance']['profile']==('car' if mode=='CAR' else 'motorbike')
        assert 'router_url' not in catalog['provenance']
