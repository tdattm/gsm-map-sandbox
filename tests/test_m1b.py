"""M1b strict identities/pipeline fixtures; no synthetic bytes claimed as GIS."""
import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from backend.app.dataset import artifact_status, router_status
from backend.app.main import create_app
from fastapi.testclient import TestClient
from backend.app.integrity import digest, region_integrity
from scripts.region_pipeline import check_files, checked_manifest, run
from test_regions import registry, write_json


def strict_context(registry):
    c = replace(registry.resolve('nvmr-hanoi-core'), artifact_config_sha256='synthetic-config')
    identity = c.artifact_identity
    c.extracted_path.parent.mkdir(parents=True)
    c.extracted_path.write_bytes(b'SYNTHETIC EXTRACT')
    source = {'identity':identity,'sha256':digest(c.pbf_path)}
    write_json(c.extracted_path.with_suffix('.metadata.json'), dict(identity=identity,
        source_sha256=source['sha256'],routing_bbox=c.routing_bbox,extract_sha256=digest(c.extracted_path)))
    render = json.loads((c.map_path.parent/'manifest.json').read_text())
    render.update(identity=identity,render_bbox=list(c.render_bbox),extract_sha256=digest(c.extracted_path))
    for n,entry in render['layers'].items(): entry['sha256'] = digest(c.map_path.parent/n)
    graph=json.loads((c.routing_dir/'manifest.json').read_text())
    graph.update(identity=identity,source_sha256=source['sha256'],extract_sha256=digest(c.extracted_path),
        profile_path='/opt/car.lua',profile_dependencies={'/opt/car.lua':'synthetic-profile','/opt/lib/access.lua':'synthetic'},
        artifact_sha256={n:digest(c.routing_dir/n) for n in graph['artifact_sizes']})
    return c, source, render, graph


def test_manifest_identity_corruption_and_partial_outputs_fail_closed(registry):
    c,source,render,graph = strict_context(registry)
    assert region_integrity(c,source,render,graph) == (True,True)
    assert region_integrity(c,source,render,None) == (True,False)  # Offline map doesn't require graph.
    wrong={**graph,'identity':{**c.artifact_identity,'region_id':'hcm-center'}}
    assert region_integrity(c,source,render,wrong) == (True,False)
    assert region_integrity(c,source,{**render,'identity':None},graph) == (False,True)
    path=next(c.routing_dir.glob('*.osrm.cells'))
    path.write_bytes(b'X'*path.stat().st_size)  # Same size corruption, hash/stat cache must notice.
    assert region_integrity(c,source,render,graph) == (True,False)
    c.pbf_path.write_bytes(b'CHANGED SOURCE')
    assert region_integrity(c,source,render,graph) == (False,False)


def test_graph_checks_profile_and_complete_asset_set(registry):
    c,source,render,graph = strict_context(registry)
    for replacement in [{'profile_path':'/opt/bicycle.lua'}, {'profile_dependencies':{}}, {'artifact_sha256':{}}]:
        assert region_integrity(c,source,render,{**graph,**replacement}) == (True,False)
    assert region_integrity(c,source,{**render,'layers':{}},graph) == (False,True)


def test_pipeline_reuse_verifies_hash_and_identity(tmp_path):
    path=tmp_path/'manifest.json'
    write_json(path,{'identity':{'region':'hcm'}})
    with pytest.raises(RuntimeError): checked_manifest(path,{'region':'hanoi'})
    artifact=tmp_path/'one'; artifact.write_bytes(b'test')
    check_files(tmp_path,{'one':digest(artifact)})
    for hashes in [{},{'one':'wrong'},{'../escape':'wrong'},{'missing':'wrong'}]:
        with pytest.raises(RuntimeError): check_files(tmp_path,hashes)


def test_pipeline_dry_run_does_not_invoke_tools(monkeypatch):
    from backend.app.config import Settings
    monkeypatch.setattr('scripts.region_pipeline.execute',lambda *a,**kw:pytest.fail('Dry run invoked Docker'))
    for action in ('verify','extract','display','routing','serve'):
        assert run(Settings(),SimpleNamespace(region='nvmr-hanoi-core',profile='car',dry_run=True,action=action)) == 0


def test_wrong_live_graph_hints_fail_identity_probe(registry,monkeypatch):
    c=replace(registry.resolve('nvmr-hanoi-core'),artifact_config_sha256='fixture')
    write_json(c.routing_dir/'router-evidence.json',dict(identity=c.artifact_identity,
        manifest_sha256=digest(c.routing_dir/'manifest.json'),
        probes=[{'point':list(c.viewport_center),'hint':'expected-graph-checksum','location':list(c.viewport_center)}]*3))
    real=httpx.AsyncClient
    async def handler(request):
        return httpx.Response(200,json={'code':'Ok','waypoints':[{'hint':'other-graph','location':list(c.viewport_center)}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    assert asyncio.run(router_status(c))['state']=='identity_mismatch'


@pytest.mark.parametrize('case,code,status', [('NoRoute','NOROUTE',422),('NoSegment','NOSEGMENT',422),
    ('snap','SNAP_TOO_FAR',422),('outside','ROUTE_OUTSIDE_REGION',502),
    ('timeout','ROUTER_TIMEOUT',503),('badmetrics','ROUTER_BAD_RESPONSE',502)])
def test_scoped_car_errors_never_fabricate_route(registry,monkeypatch,case,code,status):
    c=registry.resolve('nvmr-hanoi-core'); a,b=(105.76,21.06),(105.77,21.07)
    real=httpx.AsyncClient
    async def handler(request):
        if '/nearest/' in request.url.path:
            return httpx.Response(200,json={'code':'Ok','waypoints':[{'location':a,'distance':0}]})
        if case in ('NoRoute','NoSegment'): return httpx.Response(400,json={'code':case})
        if case=='timeout': raise httpx.ReadTimeout('Fixture timeout',request=request)
        points=[a,(106.7,10.77),b] if case=='outside' else [a,b]
        return httpx.Response(200,json={'code':'Ok','waypoints':[{'location':a,'distance':101 if case=='snap' else 0},
            {'location':b,'distance':0}],'routes':[{'distance':0 if case=='badmetrics' else 1000,'duration':100,
            'geometry':{'type':'LineString','coordinates':points}}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    response=TestClient(create_app(registry=registry)).post(f'/api/regions/{c.id}/route',json={'start':a,'end':b})
    assert response.status_code==status and response.json()['error']['code']==code
    assert 'coordinates' not in response.json()
