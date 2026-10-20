"""Verify/restore a research bundle, or serve it with the existing API read-only.

python -m scripts.connected_replay restore bundle.zip --destination build/d2c/restored
GSM_REPLAY_BUNDLE=<restored absolute path> uvicorn scripts.connected_replay:create_app --factory
"""
import argparse
import json
import os
from pathlib import Path
import zipfile

from backend.app.replay_bundle import bundle_file, verify_bundle, portable_map_status


def restore(archive, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Restore destination already exists; never overwrite a store')
    with zipfile.ZipFile(archive) as source:
        names = [item.filename for item in source.infolist()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive member')
        for item in source.infolist():
            bundle_file(destination, item.filename)
            if item.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError('Symlink archive member')
        source.extractall(destination)
    manifest = verify_bundle(destination)
    portable_map_status(destination)
    return manifest


def create_app():
    root = Path(os.environ['GSM_REPLAY_BUNDLE']).resolve()
    verify_bundle(root)
    portable_map_status(root)
    os.environ['GSM_SIMULATION_STORE'] = str(root/'jobs')
    from backend.app.main import create_app as existing_app
    from fastapi.responses import JSONResponse
    app = existing_app(connected_map_root=root)

    @app.middleware('http')
    async def read_only(request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            return JSONResponse(status_code=405, content={'error': {'code': 'REPLAY_READ_ONLY', 'message': 'Completed research replay is read-only.'}})
        return await call_next(request)
    # Same-origin static replay needs only this API process on a compatible host.
    # API routes are registered first; no worker, Node server or router is started.
    frontend = Path(__file__).resolve().parents[1]/'frontend/dist'
    if (frontend/'index.html').is_file():
        from fastapi.staticfiles import StaticFiles
        app.mount('/', StaticFiles(directory=frontend, html=True), name='replay-frontend')
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'restore'])
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.action == 'restore':
        if args.destination is None:
            parser.error('--destination is required')
        manifest = restore(args.bundle, args.destination)
    else:
        manifest = verify_bundle(args.bundle)
        portable_map_status(args.bundle)
    print(json.dumps({'status': 'PASS', 'jobId': manifest['jobId'], 'files': len(manifest['files'])}))


if __name__ == '__main__':
    main()
