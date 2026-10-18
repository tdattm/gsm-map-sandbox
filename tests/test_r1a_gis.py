"""Artifact-free regional namespace and cross-region provenance regressions."""
import json
from dataclasses import replace
from types import SimpleNamespace
import pytest
from backend.app.config import Settings
from backend.app.dataset import artifact_status
from backend.app.integrity import digest
from backend.app.modes import resolve_mode, motor_artifacts
from backend.app.regions import default_registry, RegionRegistry
from scripts.regional_resources import decision, GIB
from test_regions import registry, write_json
from test_m1b import strict_context


def test_motorbike_serve_reuses_identical_proof_without_touching_historical_bytes(tmp_path):
    from scripts.motorbike_pipeline import preserve_router_evidence
    path = tmp_path/'router-evidence.json'
    proof = {'identity': {'region_id':'nvmr-hanoi-core'}, 'probes':[{'point':(105.84,21.03)}]}
    preserve_router_evidence(path, proof)
    before = path.read_bytes(), path.stat().st_mtime_ns
    preserve_router_evidence(path, proof)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_motorbike_serve_refuses_changed_proof_without_overwriting(tmp_path):
    from scripts.motorbike_pipeline import preserve_router_evidence
    path = tmp_path/'router-evidence.json'
    preserve_router_evidence(path, {'manifest_sha256':'old'})
    before = path.read_bytes(), path.stat().st_mtime_ns
    with pytest.raises(RuntimeError, match='refusing overwrite'):
        preserve_router_evidence(path, {'manifest_sha256':'changed'})
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize('duration,response,valid', [
    (12.3, {'code':'Ok','routes':[{'duration':12.3}]}, True),
    (None, {'code':'NoRoute'}, True),
    (12.3, {'code':'NoRoute'}, False),
    (None, {'code':'Ok','routes':[{'duration':12.3}]}, False),
    (12.3, {'code':'Ok','routes':[{'duration':12.4}]}, False),
    (None, {'code':'NoSegment'}, False),
])
def test_directed_table_route_consistency_fails_on_reachability_or_metric_mismatch(duration,response,valid):
    from scripts.validate_regional_routing import assert_table_route_consistency
    if valid:
        assert_table_route_consistency(duration,response)
    else:
        with pytest.raises(RuntimeError):
            assert_table_route_consistency(duration,response)


def test_bac_ninh_namespaces_never_alias_hanoi_and_preserve_historical_identity():
    reg = default_registry(Settings())
    contexts = [resolve_mode(reg,r,m) for r in ('nvmr-hanoi-core','nvmr-bac-ninh-core') for m in ('CAR','MOTORBIKE')]
    assert len({c.routing_dir for c in contexts}) == len({c.osrm_base_url for c in contexts}) == 4
    hanoi,bac = contexts[0],contexts[2]
    assert hanoi.artifact_identity['pipeline_version'] == 'hanoi-car-pilot/v1'
    assert contexts[1].artifact_identity['version'] == 'hanoi-electric-motorcycle/v1'
    assert bac.artifact_identity['pipeline_version'] == 'nvmr-regional-car-pilot/v1'
    for c in contexts[2:]:
        assert c.id == 'nvmr-bac-ninh-core'
        assert 'bac-ninh' in c.graph_basename and c.routing_bbox != hanoi.routing_bbox
        w,s,e,n = c.routing_bbox
        assert w < c.operating_bbox[0] < c.operating_bbox[2] < e
        assert s < c.operating_bbox[1] < c.operating_bbox[3] < n


def test_bac_ninh_dry_run_never_invokes_preflight_docker_or_data(monkeypatch):
    from scripts.pipeline import main
    monkeypatch.setattr('scripts.pipeline.execute', lambda *a,**kw:pytest.fail('Unexpected Docker/data access'))
    monkeypatch.setattr('scripts.regional_resources.preflight', lambda *a:pytest.fail('Dry-run preflight writes'))
    for action in ('verify','extract','display','routing','serve'):
        assert main([action,'--region','nvmr-bac-ninh-core','--dry-run']) == 0
    for action in ('routing','serve'):
        assert main([action,'--region','nvmr-bac-ninh-core','--profile','motorbike','--dry-run']) == 0


@pytest.mark.parametrize('physical,commit,allowed', [(2,2,True),(1.99,3,False),(3,1.99,False)])
def test_heavy_gis_guard_preserves_two_gib_floor(physical,commit,allowed):
    assert decision({'availablePhysicalBytes':int(physical*GIB),'systemCommitAvailableBytes':int(commit*GIB)}) == allowed


@pytest.mark.parametrize('damage', ['none','hanoi-proof','stale-graph','wrong-region','failed-proof','pending','source-change'])
def test_motor_requires_own_regional_evidence_and_fails_closed(registry,tmp_path,monkeypatch,damage):
    c,source,render,car_graph = strict_context(registry)
    c = replace(c,id='nvmr-bac-ninh-core', pipeline_version='nvmr-regional-car-pilot/v1')
    identity = c.artifact_identity
    source.update(identity=identity)
    meta_path = c.extracted_path.with_suffix('.metadata.json')
    meta = json.loads(meta_path.read_text()); meta['identity'] = identity; write_json(meta_path,meta)
    render['identity'] = identity; car_graph['identity'] = identity
    source = {**json.loads((c.map_path.parent.parent/'source-verification.json').read_text()),**source}
    write_json(c.map_path.parent.parent/'source-verification.json',source)
    write_json(c.map_path.parent/'manifest.json',render); write_json(c.routing_dir/'manifest.json',car_graph)
    motor = resolve_mode(RegionRegistry({c.id:c}),c.id,'MOTORBIKE')
    motor.routing_dir.mkdir()
    files = {}
    for suffix in ('cells','partition','mldgr'):
        path = motor.routing_dir/f'{motor.graph_basename}.osrm.{suffix}'
        path.write_bytes(b'SYNTHETIC TEST GRAPH'); files[path.name] = digest(path)
    graph = {'identity':motor.artifact_identity,'profile':'motorbike','algorithm':'mld',
        'profile_sha256':motor.profile_sha256,'profile_dependencies':{
            **{f'/opt/lib/{i}.lua':'fixture' for i in range(24)},'/profiles/motorbike.lua':motor.profile_sha256},
        'extract_sha256':digest(c.extracted_path),'source_sha256':source['sha256'],
        'artifact_sha256':files,'artifact_sizes':{n:(motor.routing_dir/n).stat().st_size for n in files},
        'routing_bbox':list(c.routing_bbox)}
    manifest = motor.routing_dir/'manifest.json'; write_json(manifest,graph)
    isolated = tmp_path/'isolated'; validator = isolated/'scripts/validate_regional_routing.py'
    validator.parent.mkdir(parents=True); validator.write_text('SYNTHETIC REGIONAL VALIDATOR')
    evidence = isolated/'docs/nvmr/r1a-evidence/gis'/c.id
    proof = {'status':'PASS','regionId':c.id,'extractSha256':graph['extract_sha256'],
             'routingIdentities':{'MOTORBIKE':{'graphManifestSha256':digest(manifest)}}}
    write_json(evidence/'synthetic-validation.json',{'status':'PASS'})
    write_json(evidence/'regional-routing.json',proof)
    if damage == 'hanoi-proof':
        (evidence/'regional-routing.json').unlink()
        write_json(isolated/'docs/nvmr/m2-evidence/real-mode-cases.json',{'status':'PASS'})
    elif damage in ('wrong-region','stale-graph','failed-proof'):
        if damage == 'wrong-region': proof['regionId'] = 'nvmr-hanoi-core'
        if damage == 'stale-graph': proof['routingIdentities']['MOTORBIKE']['graphManifestSha256'] = 'other-region-graph'
        if damage == 'failed-proof': proof['status'] = 'FAIL'
        write_json(evidence/'regional-routing.json',proof)
    if damage != 'hanoi-proof':
        hashes = {p.name:digest(p) for p in evidence.glob('*.json')}
    else:
        hashes = {'synthetic-validation.json':digest(evidence/'synthetic-validation.json'),'regional-routing.json':'missing'}
    write_json(motor.routing_dir/'validation.json',{'status':'PASS','regionId':c.id,
        'manifest_sha256':digest(manifest),'validator_sha256':digest(validator),'evidence_sha256':hashes})
    monkeypatch.setattr('backend.app.modes.ROOT',isolated)
    if damage == 'pending': (motor.routing_dir/'.validation-incomplete').write_text('pending')
    if damage == 'source-change': c.pbf_path.write_bytes(b'ALTERED SOURCE')
    assert motor_artifacts(motor)['graph_ready'] == (damage == 'none')
    assert artifact_status(c)['graph_ready'] == (damage != 'source-change')
