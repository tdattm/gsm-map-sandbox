"""D1.5 read-only aggregation agrees with persisted replay; no routing requests."""
from copy import deepcopy
import pytest
from backend.app.connected_analytics import fleet_state_series, STATES
from backend.app.connected_simulation import connected_snapshot, ConnectedScenarioConfig
from backend.app.simulation_jobs import JobStore
from test_connected_api import app, complete


def test_sweep_matches_snapshot_with_equal_timestamps_and_does_not_read_routes():
    raw={'runId':'same-time','config':{'fleetSize':2},'simulationDurationSeconds':20,
         'vehicles':[{'id':'a'},{'id':'b'}], 'timelines':{
             'a':[{'time':0,'state':'OFFLINE'},{'time':5,'state':'IDLE'},{'time':5,'state':'ASSIGNED'},{'time':10,'state':'ON_TRIP'},{'time':15,'state':'IDLE'}],
             'b':[{'time':0,'state':'IDLE'},{'time':5,'state':'OFFLINE'}]}}
    original=deepcopy(raw)
    series=fleet_state_series(raw)
    assert raw==original
    assert series['points'][1]=={'timeSeconds':5,'OFFLINE':1,'IDLE':0,'ASSIGNED':1,'ON_TRIP':0}
    assert series['points'][-1]=={'timeSeconds':20,'OFFLINE':1,'IDLE':1,'ASSIGNED':0,'ON_TRIP':0}
    assert not series['sampled']
    for row in series['points']:
        assert sum(row[state] for state in STATES)==2


def test_downsamples_real_checkpoints_without_interpolation_and_preserves_endpoints():
    raw={'runId':'many','config':{'fleetSize':1},'simulationDurationSeconds':300,
         'vehicles':[{'id':'a'}], 'timelines':{'a':[{'time':t,'state':'IDLE' if t%2 else 'OFFLINE'} for t in range(301)]}}
    series=fleet_state_series(raw)
    assert len(series['points'])==120 and series['sampled']
    assert series['points'][0]['timeSeconds']==0 and series['points'][-1]['timeSeconds']==300
    for row in series['points']:
        assert row['timeSeconds'] in range(301)
        assert row['OFFLINE']==(row['timeSeconds']%2==0)
        assert sum(row[state] for state in STATES)==1


def test_endpoint_completed_only_cached_and_independent_snapshot_oracle(tmp_path,monkeypatch):
    store=JobStore(tmp_path);client=app(store)
    config=ConnectedScenarioConfig(fleetSize=20,carCount=8,bookingCount=5,distribution={'nearestNeighborSampleSize':0})
    run_id=client.post('/api/v5/simulation/jobs',json=config.model_dump(mode='json')).json()['id']
    prefix='/api/v5/simulation/jobs/'+run_id
    assert client.get(prefix+'/analytics/fleet-states').status_code==409
    result=complete(store,config,run_id)
    calls=[]
    def aggregate(raw):
        calls.append(raw['runId']);return fleet_state_series(raw)
    monkeypatch.setattr('backend.app.connected_jobs.fleet_state_series',aggregate)
    series=client.get(prefix+'/analytics/fleet-states').json()
    assert client.get(prefix+'/analytics/fleet-states').json()==series
    assert calls==[run_id]
    weighted=client.get(prefix+'/analytics/fleet-states?aggregation=time-weighted').json()
    assert weighted['aggregation']=='time-weighted-mean/v1'
    assert weighted['bucketCount']==120 and len(weighted['points'])==121
    assert all(sum(row[s] for s in STATES)==pytest.approx(20) for row in weighted['points'])
    assert client.get(prefix+'/analytics/fleet-states?aggregation=unknown').status_code==422
    assert not {'routes','vehicles','timelines','moving'} & series.keys()
    for row in series['points']:
        expected=connected_snapshot(result,row['timeSeconds'])['counts']
        assert [row[s] for s in STATES]==[expected[s] for s in ['offline','idle','assigned','onTrip']]
    assert client.get(prefix+'/result?summary=true').json()['schemaVersion']=='gsm-nvmr-connected-result/v1'
    assert client.get('/api/v5/simulation/jobs/missing/analytics/fleet-states').status_code==404
    def unavailable(_raw):
        raise ValueError('Missing initial vehicle state')
    monkeypatch.setattr('backend.app.connected_jobs.fleet_state_series',unavailable)
    response=app(store).get(prefix+'/analytics/fleet-states')
    assert response.status_code==422
    assert response.json()['detail']['code']=='CONNECTED_ANALYTICS_UNAVAILABLE'


def test_missing_timeline_is_unavailable_without_fabricating_states():
    with pytest.raises(ValueError,match='Missing initial'):
        fleet_state_series({'runId':'bad','config':{'fleetSize':1},'simulationDurationSeconds':5,'vehicles':[{'id':'a'}],'timelines':{}})
