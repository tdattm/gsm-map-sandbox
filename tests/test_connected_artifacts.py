"""Fail-closed connected catalog/validation proofs without live GIS or Docker."""
from copy import deepcopy
import asyncio
import hashlib
import json
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from backend.app import connected_jobs
from backend.app.connected_jobs import read_anchor_catalog, validate_anchor_catalog, verify_routing_validation
from backend.app.connected_simulation import load_zones
from backend.app.connected_simulation import ConnectedScenarioConfig


def catalog_fixture(tmp_path, monkeypatch):
    zones = load_zones()
    config = {'regionId': 'nvmr-connected', 'pipelineVersion': 'connected-nvmr-gis/v1',
        'source': {'sha256': 'source-fixture'}, 'boundaryVersion': 'technical-fixture/v1',
        'operatingZones': zones, 'anchorCatalog': 'anchors/road-candidates.json',
        'snappedAnchorCatalog': 'anchors/snapped-anchors.json'}
    (tmp_path/'config').mkdir()
    config_bytes = json.dumps(config).encode()
    (tmp_path/'config/connected-nvmr.json').write_bytes(config_bytes)
    config_hash = hashlib.sha256(config_bytes).hexdigest()
    identities = {mode: {'regionId': 'nvmr-connected', 'vehicleType': mode,
        'graphManifestSha256': f'{mode}-fixture', 'extractSha256': 'extract-fixture',
        'sourceSha256': 'source-fixture'} for mode in ('CAR', 'MOTORBIKE')}
    raw = {'schemaVersion': 'connected-road-candidates/v1',
        'identity': {'region_id': config['regionId'], 'config_sha256': config_hash, 'pipeline_version': config['pipelineVersion']},
        'sourceSha256': 'source-fixture', 'extractSha256': 'extract-fixture',
        'boundaryVersion': config['boundaryVersion'],
        'candidates': [{'zoneId': z['id'], 'coordinate': z['probe']} for z in zones]}
    folder = tmp_path/'anchors'
    folder.mkdir()
    path = folder/'road-candidates.json'
    path.write_text(json.dumps(raw))
    manifest = {'identity': raw['identity'], 'source_sha256': raw['sourceSha256'],
        'extract_sha256': raw['extractSha256'], 'artifact_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}}
    (folder/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(connected_jobs, 'PROJECT_ROOT', tmp_path)
    return config, config_hash, identities, raw, folder


def test_verified_raw_catalog_reuses_mode_pools_and_records_content_digest(tmp_path, monkeypatch):
    config, config_hash, identities, raw, folder = catalog_fixture(tmp_path, monkeypatch)
    pools, provenance = read_anchor_catalog(identities)
    assert pools['CAR'] == pools['MOTORBIKE'] == [entry['coordinate'] for entry in raw['candidates']]
    assert provenance['preSnapped'] is False
    assert provenance['catalogSha256'] == hashlib.sha256((folder/'road-candidates.json').read_bytes()).hexdigest()
    (folder/'.incomplete').write_text('unfinished')
    with pytest.raises(HTTPException) as caught:
        read_anchor_catalog(identities)
    assert caught.value.detail['code'] == 'ANCHORS_INCOMPLETE'


@pytest.mark.parametrize('key', ['identity', 'sourceSha256', 'extractSha256', 'boundaryVersion'])
def test_catalog_provenance_cannot_be_relabelled(key, tmp_path, monkeypatch):
    config, config_hash, identities, raw, _ = catalog_fixture(tmp_path, monkeypatch)
    tampered = deepcopy(raw)
    tampered[key] = 'wrong'
    with pytest.raises(ValueError, match='identity mismatch'):
        validate_anchor_catalog(tampered, identities, config, config_hash, False)


def test_catalog_checksum_detects_changed_road_coordinates(tmp_path, monkeypatch):
    _, _, identities, raw, folder = catalog_fixture(tmp_path, monkeypatch)
    raw['candidates'][0]['coordinate'][0] += .001
    (folder/'road-candidates.json').write_text(json.dumps(raw))
    with pytest.raises(HTTPException) as caught:
        read_anchor_catalog(identities)
    assert caught.value.detail['code'] == 'ANCHOR_IDENTITY_MISMATCH'


def test_snapped_catalog_requires_active_mode_graph_identity_and_zone_geometry(tmp_path, monkeypatch):
    config, config_hash, identities, raw, _ = catalog_fixture(tmp_path, monkeypatch)
    raw['modes'] = {mode: deepcopy(raw['candidates']) for mode in identities}
    raw['routingIdentities'] = deepcopy(identities)
    with pytest.raises(ValueError, match='schema'):
        validate_anchor_catalog(raw, identities, config, config_hash, True)
    raw['schemaVersion'] = 'connected-snapped-anchors/v1'
    assert len(validate_anchor_catalog(raw, identities, config, config_hash, True)['CAR']) == 5
    raw['routingIdentities']['MOTORBIKE']['graphManifestSha256'] = 'wrong-graph'
    with pytest.raises(ValueError, match='different routing graph'):
        validate_anchor_catalog(raw, identities, config, config_hash, True)
    raw['routingIdentities'] = identities
    raw['modes']['CAR'][0]['zoneId'] = 'bac-ninh'
    with pytest.raises(ValueError, match='attributed'):
        validate_anchor_catalog(raw, identities, config, config_hash, True)


def test_routing_validation_requires_current_validator_evidence_and_complete_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(connected_jobs, 'PROJECT_ROOT', tmp_path)
    (tmp_path/'scripts').mkdir()
    validator = tmp_path/'scripts/validate_connected_routing.py'
    validator.write_text('# explicit fixture validator')
    (tmp_path/'profiles').mkdir()
    profile = tmp_path/'profiles/motorbike.lua'
    profile.write_text('-- explicit synthetic fixture profile')
    folder = tmp_path/'graph'
    folder.mkdir()
    evidence = folder/'routing-validation.json'
    identity = {'graphManifestSha256': 'manifest-fixture', 'vehicleType': 'CAR', 'regionId': 'nvmr-connected'}
    actual = {'status': 'PASS', 'routingIdentity': identity, 'mode': 'CAR'}
    evidence.write_text(json.dumps(actual))
    synthetic = folder/'synthetic-validation.json'
    synthetic.write_text(json.dumps({'status': 'PASS', 'fixtureOnly': True, 'profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest()}))
    proof = {'status': 'PASS', 'regionId': 'nvmr-connected', 'manifest_sha256': 'manifest-fixture',
        'validator_sha256': hashlib.sha256(validator.read_bytes()).hexdigest(),
        'evidence_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (evidence, synthetic)}}
    (folder/'validation.json').write_text(json.dumps(proof))
    context = SimpleNamespace(routing_dir=folder)
    assert verify_routing_validation(context, identity) == proof
    actual['mode'] = 'MOTORBIKE'
    evidence.write_text(json.dumps(actual))
    proof['evidence_sha256'][evidence.name] = hashlib.sha256(evidence.read_bytes()).hexdigest()
    (folder/'validation.json').write_text(json.dumps(proof))
    with pytest.raises(ValueError, match='routing identity/mode'):
        verify_routing_validation(context, identity)
    actual['mode'] = 'CAR'
    evidence.write_text(json.dumps(actual))
    proof['evidence_sha256'][evidence.name] = hashlib.sha256(evidence.read_bytes()).hexdigest()
    (folder/'validation.json').write_text(json.dumps(proof))
    profile.write_text('-- changed profile invalidates generated oracle')
    with pytest.raises(ValueError, match='current motorcycle profile'):
        verify_routing_validation(context, identity)
    profile.write_text('-- explicit synthetic fixture profile')
    (folder/'.validation-incomplete').write_text('unfinished')
    with pytest.raises(ValueError, match='incomplete'):
        verify_routing_validation(context, identity)
    (folder/'.validation-incomplete').unlink()
    validator.write_text('# changed validator invalidates acceptance')
    with pytest.raises(ValueError, match='identity mismatch'):
        verify_routing_validation(context, identity)


def test_readiness_message_surfaces_each_mode_cause_for_basic_api_clients(monkeypatch):
    def unavailable(mode):
        raise ValueError(f'{mode} fixture graph proof missing')
    monkeypatch.setattr(connected_jobs, 'connected_context', unavailable)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(connected_jobs.connected_readiness(ConnectedScenarioConfig()))
    detail = caught.value.detail
    assert caught.value.status_code == 503
    assert detail['code'] == 'CONNECTED_NOT_READY'
    assert 'CAR: CAR fixture graph proof missing' in detail['message']
    assert 'MOTORBIKE: MOTORBIKE fixture graph proof missing' in detail['message']
    assert {entry['vehicleType'] for entry in detail['modes']} == {'CAR', 'MOTORBIKE'}
