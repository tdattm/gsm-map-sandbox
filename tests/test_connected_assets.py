"""Offline tile transport fixtures; no synthetic map is exposed by the app."""
import gzip
import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.connected_assets import create_connected_map_router


def fixture_archive(tmp_path, monkeypatch):
    from scripts import connected_gis
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root/'config/connected-nvmr.json').read_text(encoding='utf-8'))
    (tmp_path/'config').mkdir()
    (tmp_path/'config/connected-nvmr.json').write_text(json.dumps(cfg), encoding='utf-8')
    archive = tmp_path/cfg['tiles']['archive']
    archive.parent.mkdir(parents=True)
    payload = gzip.compress(b'fixture-only-vector-tile-transport')
    with sqlite3.connect(archive) as db:
        db.execute('CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB)')
        db.execute('INSERT INTO tiles VALUES(?,?,?,?)', (6, 50, 33, payload))
    (archive.parent/'manifest.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(connected_gis, 'verify_render', lambda root: {})
    app = FastAPI()
    app.include_router(create_connected_map_router(tmp_path))
    return app, archive


def test_xyz_to_tms_gzip_missing_and_invalid_tiles(tmp_path, monkeypatch):
    app, _ = fixture_archive(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get('/api/v5/connected/map/tiles/6/50/30.pbf')
        assert response.status_code == 200
        assert response.content == b'fixture-only-vector-tile-transport'
        assert response.headers['content-encoding'] == 'gzip'
        assert response.headers['content-type'] == 'application/vnd.mapbox-vector-tile'
        assert response.headers['etag']
        assert client.get('/api/v5/connected/map/tiles/6/50/31.pbf').status_code == 204
        for path in ('6/-1/0', '6/64/0', '23/0/0'):
            assert client.get('/api/v5/connected/map/tiles/'+path+'.pbf').status_code == 404


def test_missing_or_incomplete_map_returns_explicit_unavailable(tmp_path, monkeypatch):
    app, archive = fixture_archive(tmp_path, monkeypatch)
    from scripts import connected_gis
    def incomplete(root):
        raise RuntimeError('Basemap incomplete')
    monkeypatch.setattr(connected_gis, 'verify_render', incomplete)
    with TestClient(app) as client:
        status = client.get('/api/v5/connected/map/status').json()
        assert status['ready'] is False and 'incomplete' in status['reason']
        assert client.get('/api/v5/connected/map/tiles/6/50/30.pbf').status_code == 503
        archive.unlink()
        assert client.get('/api/v5/connected/map/status').json()['ready'] is False


def test_unreadable_archive_is_a_structured_service_error(tmp_path, monkeypatch):
    app, archive = fixture_archive(tmp_path, monkeypatch)
    archive.write_bytes(b'explicit malformed SQLite fixture')
    with TestClient(app) as client:
        response = client.get('/api/v5/connected/map/tiles/6/50/30.pbf')
        assert response.status_code == 503
        assert response.json()['detail']['code'] == 'CONNECTED_MAP_BAD_ARCHIVE'
