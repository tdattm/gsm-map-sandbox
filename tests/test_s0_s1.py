"""Independent geometry, selected-booking compatibility, and runtime ownership."""
from copy import deepcopy
import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from backend.app.simulation import snapshot
from backend.app.simulation_details import booking_detail
from backend.app.simulation_jobs import JobStore, create_router, file_lock
from scripts.audit_route_fidelity import audit, locate
from test_m3 import run, vehicle, booking
from test_a3 import FixtureTravel, road


class CurvedTravel(FixtureTravel):
    async def route(self, start, end):
        value=road(start,end,10)
        # Directed L-shaped synthetic unit geometry; reverse is a different path.
        a,b=tuple(start),tuple(end)
        return value.model_copy(update={'coordinates':[a,(a[0],b[1]),b]})


@pytest.mark.parametrize('mode',['CAR','MOTORBIKE'])
def test_curves_timing_reuse_stationary_and_reverse_seek(mode):
    a=(105.8,21.);b=(105.801,21.001);c=(105.803,21.002)
    result=run([vehicle('v',mode,a)], [booking('b1',1,b,c,mode),booking('b2',30,c,b,mode)],
               {mode:CurvedTravel()},wait=100)
    assert result['assignments'][1]['pickupRouteRef'] is None
    report=audit(result,10)
    assert report['passed'],report['violations']
    assert report['maxDeviationMeters']<.02
    d=booking_detail(result,'b1')
    assert d['pickupLeg']['routeRef']!=d['tripLeg']['routeRef']
    assert d['routingIdentity']==result['routingIdentities'][mode]
    assert d['pickup']==list(b) and d['dropoff']==list(c)
    for t in (1,5,10,11,12,20,21,30,35,40,50):
        expected=snapshot(result,t)
        snapshot(result,50-t)
        assert snapshot(result,t)==expected


def test_metric_oracle_detects_chord_shortcut_and_near_zero_route():
    coords=[[105.8,21],[105.8,21.001],[105.801,21.001]]
    nearest,_=locate([105.8005,21.0005],coords)
    assert nearest[0]>50  # Chord midpoint is not on either directed road segment.
    a=[105.8,21.];b=[105.800000001,21.]
    assert locate(a,[a,b])[0][0]==0
    assert locate(b,[a,b])[0][0]<1e-8


def test_selected_detail_is_run_scoped_bounded_and_does_not_mutate():
    result=run()
    before=json.dumps(result,sort_keys=True)
    d=booking_detail(result,'B1')
    assert d['schemaVersion']=='gsm-simulation-booking-detail/v1'
    assert not any(key in d for key in ('events','routes','timelines','dispatchCandidates'))
    assert d['pickupDeadlineSeconds']==300
    assert json.dumps(result,sort_keys=True)==before
    with pytest.raises(HTTPException) as e: booking_detail(result,'other')
    assert e.value.status_code==404
    old=deepcopy(result);del old['timelines']
    with pytest.raises(HTTPException) as e: booking_detail(old,'B1')
    assert e.value.detail['code']=='HISTORICAL_DETAIL_UNAVAILABLE'


def test_detail_and_runtime_endpoints_preserve_snapshot_and_final_gate(tmp_path):
    store=JobStore(tmp_path)
    from backend.app.simulation import SimulationConfig
    job=store.create(SimulationConfig(fleetSize=1,carCount=1,bookingCount=1))
    app=FastAPI();app.include_router(create_router(store));client=TestClient(app)
    root=f'/api/v3/simulation/jobs/{job["id"]}'
    assert client.get(root+'/bookings/B1').status_code==409
    result=run();result['runId']=job['id']
    for route in result['routes'].values():route['runId']=job['id']
    store.claim();store.finish(job['id'],result)
    response=client.get(root+'/bookings/B1')
    assert response.status_code==200 and response.json()['runId']==job['id']
    assert client.get(root+'/snapshot?timeSeconds=5').json()==snapshot(result,5)
    runtime=client.get('/api/v3/simulation/jobs/runtime').json()
    assert runtime['store']==str(tmp_path.resolve()) and runtime['worker']=='offline'
    with file_lock(tmp_path/'.worker.lock',blocking=False):
        assert store.runtime()['worker']=='locked'
    assert store.runtime()['worker']=='offline'
