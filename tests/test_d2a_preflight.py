"""D2a preparation tests. 5K tests generate INPUTS ONLY, never execute a job.

Generated fixture anchors below are explicitly synthetic; real GIS membership
evidence comes only from the offline preflight report, not this test fixture.
"""
from copy import deepcopy
import hashlib
import json

import pytest

from scripts import preflight_nvmr_5k as preflight
from backend.app.connected_simulation import connected_inputs, load_zones
from backend.app.simulation_resources import resource_decision
from test_connected_domain import fixture_anchors, run as fixture_run


@pytest.fixture(scope='module')
def config():
    return preflight.validate_preset()[0]


def test_contract_explicit_defaults_and_checksum(config):
    _, report = preflight.validate_preset()
    assert report['status'] == 'PASS'
    assert report['fleetAllocations'] == preflight.FLEET
    assert report['demandAllocations'] == preflight.DEMAND
    assert config.seed == preflight.PRESET_ID
    assert (config.horizonSeconds, config.maxWaitSeconds, config.workload) == (900, 300, 'typical')
    assert config.onlineFraction == .8 and config.onlineSchedule == ()


@pytest.mark.parametrize('field,value', [('fleetSize', 4999), ('bookingCount', 1749),
    ('unexpectedMetadata', 'forbidden'), ('fleetAllocations', None), ('seed', 'retuned')])
def test_reject_invalid_or_changed_frozen_preset(tmp_path, field, value):
    raw = json.loads(preflight.PRESET.read_text())
    raw[field] = value
    path = tmp_path/'preset.json'
    path.write_text(json.dumps(raw))
    manifest = json.loads(preflight.MANIFEST.read_text())
    other = path.with_suffix('.manifest.json')
    other.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        preflight.validate_preset(path, other)


def test_exact_5k_inputs_full_spatial_temporal_determinism_and_no_runtime(config, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Input preflight must not execute simulation, HTTP, or JobStore create')
    import backend.app.simulation as simulation
    import backend.app.simulation_jobs as jobs
    import backend.app.connected_simulation as connected
    import httpx
    monkeypatch.setattr(simulation, 'simulate', forbidden)
    monkeypatch.setattr(connected, 'simulate', forbidden)
    monkeypatch.setattr(connected, 'simulate_connected', forbidden)
    monkeypatch.setattr(jobs.JobStore, 'create', forbidden)
    monkeypatch.setattr(httpx.AsyncClient, 'request', forbidden)
    monkeypatch.setattr(httpx.Client, 'request', forbidden)
    zones = load_zones()
    result = preflight.input_diagnostics(config, fixture_anchors(zones, per_zone=4000), zones)
    assert result['fleet']['vehicleCount'] == 5000
    assert result['fleet']['byZone'] == preflight.FLEET
    assert result['fleet']['duplicateVehicles'] == 0
    assert result['fleet']['maximumVehiclesPerPosition'] == 1
    assert all(result['demand'][z]['pickup']['count'] == preflight.DEMAND[z] for z in preflight.ZONE_IDS)
    assert sum(result['actualDemandModes'].values()) == 1750
    assert sum(result['temporal']['oneMinuteBuckets']) == 1750
    assert sum(result['temporal']['fiveMinuteBuckets']) == 1750
    assert result['temporal']['latestSeconds']-result['temporal']['earliestSeconds'] > 800
    assert result['determinism']['firstSha256'] == result['determinism']['secondSha256']
    assert all(row['shortfall'] == 0 for row in result['anchorCapacity'])


def test_capacity_shortfall_is_mode_and_zone_specific(config):
    rows = preflight.capacity(config, fixture_anchors(per_zone=100), load_zones())
    assert rows[0]['zoneId'] == 'hanoi' and rows[0]['mode'] == 'CAR'
    assert rows[0]['shortfall'] == 1300
    with pytest.raises(ValueError, match='Insufficient verified anchors'):
        preflight.input_diagnostics(config, fixture_anchors(per_zone=100), load_zones())


@pytest.mark.parametrize('target', ['position', 'requestTimeSeconds', 'pickupZoneId', 'vehicleId', 'bookingId', 'duplicatePosition'])
def test_input_audit_rejects_corruption(config, monkeypatch, target):
    zones = load_zones()
    pools = fixture_anchors(zones, per_zone=4000)
    original = connected_inputs(config, pools, zones)
    vehicles, bookings, vm, bm = original
    if target == 'position':
        vehicles[0] = vehicles[0].model_copy(update={'position': (0., 0.)})
    elif target == 'requestTimeSeconds':
        bookings[0] = bookings[0].model_copy(update={'requestTimeSeconds': 901.})
    elif target == 'pickupZoneId':
        bm[bookings[0].id]['pickupZoneId'] = 'outside-operating-zones'
    elif target == 'vehicleId':
        vehicles[0] = vehicles[0].model_copy(update={'id': vehicles[1].id})
    elif target == 'bookingId':
        bookings[0] = bookings[0].model_copy(update={'id': bookings[1].id})
    else:
        vehicles[0] = vehicles[0].model_copy(update={'position': vehicles[1].position})
    monkeypatch.setattr(preflight, 'connected_inputs', lambda *_: original)
    with pytest.raises(ValueError):
        preflight.input_diagnostics(config, pools, zones)


def test_resource_preflight_is_read_only_and_never_rewrites_preset(config, tmp_path, monkeypatch):
    before = config.model_dump_json(), preflight.PRESET.read_bytes()
    low = {'availablePhysicalBytes': 100*1024**2, 'systemCommitAvailableBytes': 100*1024**2}
    monkeypatch.setattr(preflight, 'memory', lambda: low)
    monkeypatch.setattr(preflight, 'command_read', lambda *_: {'status': 'NOT_RUN'})
    store = tmp_path/'nonexistent-store'
    result = preflight.resource_report(config, store)
    assert not result['admission']['allowed']
    assert not store.exists()
    assert before == (config.model_dump_json(), preflight.PRESET.read_bytes())
    assert resource_decision(config, {'availablePhysicalBytes': 1024**3,
        'systemCommitAvailableBytes': 2*1024**3})['allowed']


def test_missing_artifacts_fail_closed_without_store_mutation(tmp_path, monkeypatch):
    import scripts.connected_gis as gis
    def missing(*args, **kwargs):
        raise FileNotFoundError('explicit missing artifact fixture')
    for name in ('verify_source', 'verify_graph', 'verify_render'):
        monkeypatch.setattr(gis, name, missing)
    monkeypatch.setattr(preflight, 'resource_report', lambda *_: {'admission': {'allowed': True}})
    output = tmp_path/'preflight.json'
    store = tmp_path/'no-store'
    report = preflight.run(output=output, store=store)
    assert report['conclusion'] == 'BLOCKED' and report['blockers']
    assert report['inputs']['status'] == 'NOT_RUN'
    assert output.is_file() and not store.exists()
    assert report['simulationJobsCreated'] == 0 and report['routingCalls'] == 0


@pytest.fixture(scope='module')
def persistence_fixture():
    # Existing small domain fixture, no live job/API/OSRM. Never uses the 5K preset.
    result = fixture_run()
    result['config'] = json.loads(json.dumps(result['config']))
    result['provenance'] = {'catalogSha256': 'fixture-only', 'source': {'sha256': 'fixture-only'},
                            'boundaryVersion': 'fixture-only'}
    prepared = {k: deepcopy(result[k]) for k in ('config', 'vehicles', 'bookings', 'routingIdentities', 'operatingZones', 'provenance')}
    manifest = {'config': deepcopy(result['config']), 'inputHash': hashlib.sha256(
        json.dumps(result['config'], sort_keys=True).encode()).hexdigest()}
    return result, prepared, manifest


def test_persistence_replay_kpi_and_area_chart(persistence_fixture):
    original = deepcopy(persistence_fixture)
    report = preflight.persistence_check(*persistence_fixture)
    assert report['status'] == 'PASS' and report['chartCheckpoints'] > 2
    assert persistence_fixture == original


@pytest.mark.parametrize('field', ['timelines', 'routes', 'provenance', 'kpis', 'distributionQuality'])
def test_persistence_missing_fields_block(persistence_fixture, field):
    result, prepared, manifest = deepcopy(persistence_fixture)
    del result[field]
    with pytest.raises(ValueError, match='Missing persisted'):
        preflight.persistence_check(result, prepared, manifest)
