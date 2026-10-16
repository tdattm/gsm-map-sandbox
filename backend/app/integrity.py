"""Content checks cached by immutable file stat, scoped by absolute artifact path."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=256)
def _digest(path, size, mtime, ctime):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(path):
    path = Path(path).resolve()
    stat = path.stat()
    return _digest(path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def verified_files(directory, entries):
    return bool(entries) and all(Path(name).name == name and digest(directory/name) == value for name,value in entries.items())


def region_integrity(context, source, render, graph):
    """Additional M1b checks only; never reinterpret the HCM v1 manifests."""
    identity = context.artifact_identity
    if identity is None:
        return True, True
    try:
        source_ok = (source['identity'] == identity and digest(context.pbf_path) == source['sha256'])
        extract = json.loads(context.extracted_path.with_suffix('.metadata.json').read_text(encoding='utf-8'))
        extract_ok = (extract['identity'] == identity and extract['source_sha256'] == source['sha256']
                      and extract['routing_bbox'] == list(context.routing_bbox)
                      and digest(context.extracted_path) == extract['extract_sha256'])
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return False, False
    try:
        render_ok = (source_ok and extract_ok and render['identity'] == identity
            and render['extract_sha256'] == extract['extract_sha256']
            and render['render_bbox'] == list(context.render_bbox)
            and set(render['layers']) == {f'{s}.geojson' for s in ('streets','water','green','buildings','places')}
            and verified_files(context.map_path.parent,{n:e['sha256'] for n,e in render['layers'].items()}))
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        render_ok = False
    try:
        graph_ok = (source_ok and extract_ok and graph['identity'] == identity
            and graph['extract_sha256'] == extract['extract_sha256'] and graph['source_sha256'] == source['sha256']
            and graph['profile_path'] == '/opt/car.lua'
            and graph['profile_dependencies']['/opt/car.lua'] == graph['profile_sha256']
            and len(graph['profile_dependencies']) > 1
            and set(graph['artifact_sha256']) == set(graph['artifact_sizes'])
            and verified_files(context.routing_dir, graph['artifact_sha256']))
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        graph_ok = False
    return bool(render_ok), bool(graph_ok)
