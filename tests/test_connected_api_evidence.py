"""Validator contract fixtures only: no live API, real OSRM, or jobs are created."""
import json
from types import SimpleNamespace

import httpx
import pytest

from backend.app.connected_simulation import ConnectedScenarioConfig, connected_snapshot
from backend.app.simulation_details import booking_detail
from scripts import validate_connected_api as validator
from test_connected_domain import run


def fixture_result(online=0):
    result = run(ConnectedScenarioConfig(fleetSize=20, carCount=8, bookingCount=20,
        onlineFraction=online, distribution={'nearestNeighborSampleSize': 0}))
    # Mock HTTP contract descriptors only; these are not persisted live evidence.
    # Real graph verification is an independent GIS acceptance boundary.
    for mode, identity in result['routingIdentities'].items():
        identity.update(algorithm='mld', profile=mode.lower())
    return result


def mock_client(result, statuses):
    pending = iter(statuses)
    def respond(request):
        path = request.url.path
        if path.endswith('/result'):
            body = result
        elif path.endswith('/snapshot'):
            body = connected_snapshot(result, float(request.url.params['timeSeconds']))
        elif '/bookings/' in path:
            body = booking_detail(result, path.rsplit('/',1)[1])
        elif '/routes/' in path:
            body = result['routes'][path.rsplit('/',1)[1]]
        else:
            body = next(pending)
        return httpx.Response(200, json=body)
    return httpx.Client(transport=httpx.MockTransport(respond))


@pytest.fixture(autouse=True)
def no_runtime_actions(monkeypatch):
    monkeypatch.setattr(validator, 'memory', lambda: {
        'availablePhysicalBytes': 123456, 'systemCommitAvailableBytes': 654321})
    monkeypatch.setattr(validator.time, 'sleep', lambda _: None)
    monkeypatch.setattr(validator.subprocess, 'run', lambda *a, **k:
        SimpleNamespace(returncode=0, stdout='', stderr=''))


def test_all_unserved_is_valid_and_completed_reopen_never_samples_stale_worker_pid(monkeypatch):
    result = fixture_result()
    assert not result['assignments'] and result['counts']['unserved'] == 20
    assert {b['serviceType'] for b in result['bookings']} == {'CAR','MOTORBIKE'}
    monkeypatch.setattr(validator, 'process_memory', lambda _: pytest.fail('Historical PID must not be sampled'))
    with mock_client(result, [{'status':'COMPLETED','workerPid':999999}]) as client:
        report = validator.validate(client, 'http://127.0.0.1', result['runId'], 10)
    assert report['status'] == 'PASS' and report['selected'] == []
    assert {mode: evidence['status'] for mode,evidence in report['modeJourneyEvidence'].items()} == {
        'CAR':'NO_ASSIGNMENT','MOTORBIKE':'NO_ASSIGNMENT'}
    resources = report['resources']
    assert resources['observedStatuses'] == ['COMPLETED']
    assert resources['workerSampleCount'] == 0 and resources['sampledWorkerPids'] == []
    assert resources['workerPeakRssSampledBytes'] is None
    assert resources['workerLifetimePeakRssBytes'] is None
    assert 'replay audit' in report['auditScope'] and 'no RUNNING' in report['auditScope']


def test_explicit_journey_requirement_rejects_all_unserved_without_changing_result(monkeypatch):
    result = fixture_result()
    before = json.dumps(result, sort_keys=True)
    monkeypatch.setattr(validator, 'process_memory', lambda _: pytest.fail('No active worker'))
    with mock_client(result, [{'status':'COMPLETED','workerPid':42}]) as client:
        with pytest.raises(ValueError, match='No CAR assignment'):
            validator.validate(client, 'http://127.0.0.1', result['runId'], 10, require_mode_journeys=True)
    assert json.dumps(result, sort_keys=True) == before


def test_running_worker_memory_sampling_excludes_queued_and_completed_pids(monkeypatch):
    result = fixture_result()
    sampled = []
    def process_memory(pid):
        sampled.append(pid)
        return {'rssBytes':111,'lifetimePeakRssBytes':222}
    monkeypatch.setattr(validator, 'process_memory', process_memory)
    with mock_client(result, [
        {'status':'QUEUED','workerPid':11},
        {'status':'RUNNING','workerPid':22},
        {'status':'COMPLETED','workerPid':33}]) as client:
        report = validator.validate(client, 'http://127.0.0.1', result['runId'], 10)
    assert sampled == [22]
    assert report['resources']['observedStatuses'] == ['QUEUED','RUNNING','COMPLETED']
    assert report['resources']['sampledWorkerPids'] == [22]
    assert report['resources']['workerPeakRssSampledBytes'] == 111
    assert report['resources']['workerLifetimePeakRssBytes'] == 222
    assert 'not a per-run peak' in report['resources']['workerMemoryScope']


def test_explicit_journey_requirement_accepts_both_persisted_mode_routes(monkeypatch):
    result = fixture_result(online=1)
    assert {a['vehicleType'] for a in result['assignments']} == {'CAR','MOTORBIKE'}
    monkeypatch.setattr(validator, 'process_memory', lambda _: pytest.fail('No active worker'))
    with mock_client(result, [{'status':'COMPLETED'}]) as client:
        report = validator.validate(client, 'http://127.0.0.1', result['runId'], 10, require_mode_journeys=True)
    assert report['requireModeJourneys'] is True
    assert {mode: evidence['status'] for mode,evidence in report['modeJourneyEvidence'].items()} == {
        'CAR':'PASS','MOTORBIKE':'PASS'}
    assert all(selected['routeRefs'] for selected in report['selected'])


@pytest.mark.parametrize('flag', ['--require-mode-journeys','--cross-zone-proof'])
def test_cli_enables_both_mode_journey_requirement(tmp_path, monkeypatch, flag):
    observed = []
    def validate(*args, **kwargs):
        observed.append(kwargs['require_mode_journeys'])
        return {'status':'PASS','crossZoneDispatchExamples':[
            {'vehicleZoneAtAssignment':'bac-ninh','pickupZoneId':'hanoi'}]}
    monkeypatch.setattr(validator, 'validate', validate)
    monkeypatch.setattr(validator.sys, 'argv', ['validate_connected_api', '--job-id','existing-id',
        flag,'--output',str(tmp_path/'audit.json')])
    assert validator.main() == 0
    assert observed == [True]
