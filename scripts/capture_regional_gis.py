"""Read-only artifact/runtime audit; writes only compact R1a evidence JSON."""
import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.config import Settings
from backend.app.dataset import public_region_status
from backend.app.integrity import digest
from backend.app.modes import resolve_mode, routing_identity
from backend.app.regions import default_registry
from scripts.m3_resources import memory
from scripts.pipeline import write_json


def main():
    registry = default_registry(Settings())
    c = registry.resolve('nvmr-bac-ninh-core')
    base = c.map_path.parent.parent
    result = {'capturedUtc':datetime.now(timezone.utc).isoformat(), 'regionId':c.id,
        'memoryPointSample':memory(),'coverage':{key:getattr(c,key) for key in ('operating_bbox','routing_bbox','render_bbox')},
        'viewport_bbox':c.region.display_bbox, 'administrativeBoundary':False,
        'boundaryVersion':'technical-rectangle/2026-10-18', 'source':{},'artifacts':{}, 'modes':{},'stageLogs':{}}
    result['source'] = json.loads((base/'source-verification.json').read_text(encoding='utf-8'))
    for directory in ('extracted','render','routing/car','routing/motorbike'):
        folder = base/directory
        result['artifacts'][directory] = {p.name:{'sizeBytes':p.stat().st_size,'sha256':digest(p)}
            for p in folder.glob('*') if p.is_file()}
    for mode in ('CAR','MOTORBIKE'):
        context = resolve_mode(registry,c.id,mode)
        status = asyncio.run(public_region_status(context))
        result['modes'][mode] = {'status':status}
        try: result['modes'][mode]['routingIdentity'] = routing_identity(context)
        except (OSError,ValueError,KeyError): pass
    for path in sorted((ROOT/'build').glob('r1a-gis-*.log')):
        raw = path.read_text(encoding='utf-8-sig',errors='replace')
        preflights = [json.loads(line)['regionalPreflight'] for line in raw.splitlines() if line.startswith('{"regionalPreflight"')]
        result['stageLogs'][path.name] = {'sha256':digest(path),'sizeBytes':path.stat().st_size,
            'preflights':preflights,'osrmToolPeakRamBytes':list(map(int,re.findall(r'RAM: peak bytes used: (\d+)',raw))),
            'resourceStops':[line for line in raw.splitlines() if 'RESOURCE_STOP:' in line]}
    # This is a post-GIS capture, not an invented before/after forensic inventory.
    preserved = []
    for pattern in ('data/regions/nvmr-hanoi-core/**/manifest.json','data/regions/nvmr-hanoi-core/**/validation.json',
                    'data/routing/manifest.json','config/regions/nvmr-hanoi*.json','profiles/motorbike.*'):
        preserved.extend(ROOT.glob(pattern))
    result['historicalArtifactPostCapture'] = {p.relative_to(ROOT).as_posix():{'sha256':digest(p),'mtimeNs':p.stat().st_mtime_ns} for p in preserved}
    result['preservationScope'] = ('Hanoi configuration/profile/validator files checked against Git; existing runtime artifacts were read only. '
        'Post-capture hashes support later audits; no pre-task full ignored-artifact hash inventory was taken by GIS agent.')
    result['gitChecks'] = subprocess.run(['git','diff','--exit-code','--','config/regions/nvmr-hanoi-core.json',
        'config/regions/nvmr-hanoi-core-motorbike.json','profiles/motorbike.lua','profiles/motorbike.json','scripts/validate_motorbike.py'],
        capture_output=True,text=True).returncode
    output = ROOT/'docs/nvmr/r1a-evidence/gis/artifact-audit.json'
    write_json(output,result)
    print(json.dumps({'output':str(output),'readiness':{m:v['status']['ready'] for m,v in result['modes'].items()}},ensure_ascii=True))


if __name__ == '__main__': main()
