"""Prepared oracle identity fixtures; these do not run the real OSRM oracle."""
import json
from pathlib import Path

import pytest
import httpx

from scripts import validate_connected_routing as module


@pytest.mark.parametrize('tamper',[False,True])
def test_prepared_oracle_reuse_requires_exact_current_provenance(tmp_path,monkeypatch,tamper):
    monkeypatch.setattr(module,'base',lambda:tmp_path)
    monkeypatch.setattr(module,'guard',lambda _:None)
    monkeypatch.setattr(module,'image_lock',lambda *_:module.OSRM_IMAGE)
    folder=tmp_path/'validation';folder.mkdir()
    path=folder/'synthetic-validation.json'
    profile=module.sha256(module.ROOT/'profiles/motorbike.lua')
    path.write_text(json.dumps({'status':'PASS','profile_sha256':profile}))
    proof={'profileSha256':profile,'generatorSha256':module.sha256(module.ROOT/'scripts/validate_motorbike.py'),
           'connectedValidatorSha256':module.sha256(Path(module.__file__)),
           'imageDigest':module.OSRM_IMAGE,'evidenceSha256':module.sha256(path)}
    (folder/'synthetic-current-proof.json').write_text(json.dumps(proof))
    if tamper:
        path.write_text(json.dumps({'status':'PASS','profile_sha256':profile,'changed':True}))
        with pytest.raises(RuntimeError,match='changed'):
            module.prepare_synthetic()
    else:
        module.prepare_synthetic()
        assert json.loads((folder/'synthetic-current-proof.json').read_text())==proof


@pytest.mark.parametrize('status,code,expected_reject',[(400,'NoSegment',True),(200,'NoRoute',True),
                                                     (500,'NoSegment',False),(400,'InvalidQuery',False)])
def test_snap_misses_are_domain_rejections_but_service_failures_abort(status,code,expected_reject):
    with httpx.Client(base_url='http://fixture',transport=httpx.MockTransport(
            lambda request:httpx.Response(status,json={'code':code}))) as client:
        anchor={'coordinate':[105.,21.],'zoneId':'hanoi'}
        if expected_reject:
            assert module.snap_candidate(client,anchor)==(anchor,{'code':code})
        else:
            with pytest.raises(httpx.HTTPStatusError):module.snap_candidate(client,anchor)


def test_http10_keepalive_reuses_only_explicit_bounded_keepalive_responses():
    import h11
    with module.http10_keepalive():
        conn=h11.Connection(h11.CLIENT)
        conn.send(h11.Request(method='GET',target='/nearest/v1/driving/105,21',headers=[('host','127.0.0.1'),('connection','keep-alive')]))
        conn.send(h11.EndOfMessage())
        conn.receive_data(b'HTTP/1.0 200 OK\r\nConnection: keep-alive\r\nContent-Length: 13\r\n\r\n{"code":"Ok"}')
        events=[conn.next_event(),conn.next_event(),conn.next_event()]
        assert isinstance(events[-1],h11.EndOfMessage)
        assert conn.states=={h11.CLIENT:h11.DONE,h11.SERVER:h11.DONE}
        conn.start_next_cycle()
        conn.send(h11.Request(method='GET',target='/nearest/v1/driving/105,21',headers=[('host','127.0.0.1'),('connection','close')]))
        conn.send(h11.EndOfMessage())
        assert conn.states[h11.CLIENT] is h11.MUST_CLOSE
