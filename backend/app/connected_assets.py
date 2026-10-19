"""Viewport-only offline vector tiles. Historical GeoJSON APIs stay unchanged."""
import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import threading

from fastapi import APIRouter, HTTPException, Response

from .config import PROJECT_ROOT
from .integrity import digest

_verification_lock = threading.Lock()


def map_status(root=PROJECT_ROOT):
    root = Path(root)
    config_path = root/'config/connected-nvmr.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    archive = root/config['tiles']['archive']
    manifest_path = archive.parent/'manifest.json'
    ready, reason, manifest = False, 'Offline Connected NVMR tiles have not been built.', None
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        # The pipeline's complete identity is verified before serving any bytes.
        from scripts.connected_gis import verify_render
        # Avoid duplicate cold checksum reads from simultaneous viewport tiles.
        with _verification_lock:
            verify_render(root=root)
        ready, reason = True, ''
    except (OSError, ValueError, KeyError, RuntimeError, sqlite3.Error) as exc:
        reason = str(exc)
    return {'schemaVersion': 'gsm-nvmr-connected-map/v1', 'ready': ready,
        'reason': reason, 'bounds': config['mapBbox'],
        'minZoom': config['tiles']['minZoom'], 'maxZoom': config['tiles']['maxZoom'],
        'tileUrl': config['tiles']['urlTemplate'], 'sourceLayers': config['tiles']['sourceLayers'],
        'attribution': config['source']['attribution'],
        'sourceSha256': config['source']['sha256'], 'configSha256': digest(config_path),
        'manifest': manifest if ready else None}


def create_connected_map_router(root=PROJECT_ROOT):
    root = Path(root)
    router = APIRouter(prefix='/api/v5/connected/map', tags=['Connected offline map'])

    @router.get('/status')
    async def status():
        return await asyncio.to_thread(map_status, root)

    @router.get('/tiles/{z}/{x}/{y}.pbf')
    async def tile(z: int, x: int, y: int):
        if z < 0 or z > 22 or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
            raise HTTPException(404, {'code': 'TILE_OUTSIDE_RANGE', 'message': 'Invalid XYZ tile.'})

        def read():
            state = map_status(root)
            if not state['ready']:
                raise HTTPException(503, {'code': 'CONNECTED_MAP_NOT_READY', 'message': state['reason']})
            if not state['minZoom'] <= z <= state['maxZoom']:
                return None, None
            config = json.loads((root/'config/connected-nvmr.json').read_text(encoding='utf-8'))
            archive = root/config['tiles']['archive']
            # Read-only SQLite connection per request; XYZ -> MBTiles TMS row.
            try:
                with closing(sqlite3.connect(archive.resolve().as_uri()+'?mode=ro', uri=True)) as database:
                    row = database.execute('SELECT tile_data FROM tiles WHERE zoom_level=? '
                        'AND tile_column=? AND tile_row=?', (z, x, 2**z-1-y)).fetchone()
            except sqlite3.Error as exc:
                raise HTTPException(503, {'code': 'CONNECTED_MAP_BAD_ARCHIVE', 'message': str(exc)}) from exc
            return row[0] if row else None, digest(archive)

        raw, identity = await asyncio.to_thread(read)
        if raw is None:
            return Response(status_code=204)
        headers = {'Cache-Control': 'public, max-age=3600', 'ETag': f'"{identity}-{z}-{x}-{y}"'}
        if raw[:2] == b'\x1f\x8b':
            headers['Content-Encoding'] = 'gzip'
        return Response(raw, media_type='application/vnd.mapbox-vector-tile', headers=headers)

    return router
