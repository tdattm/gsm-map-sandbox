"""Bounded read-only GIS preflight; no settings changes or process termination."""
import json
import subprocess
from scripts.m3_resources import memory

GIB = 1024**3


def decision(current):
    # Preserve the existing heavy-work 2 GiB physical floor; also check commit.
    return (current['availablePhysicalBytes'] >= 2*GIB
            and current.get('systemCommitAvailableBytes', 2*GIB) >= 2*GIB)


def preflight(context, action):
    current = memory()
    if not decision(current):
        raise RuntimeError('RESOURCE_STOP: regional GIS requires >=2 GiB available RAM and commit headroom; '
                           f'physical={current["availablePhysicalBytes"]/GIB:.3f} GiB, '
                           f'commit={current.get("systemCommitAvailableBytes",0)/GIB:.3f} GiB; do not lower guards')
    info = subprocess.run(['docker','info','--format','{{.OSType}}'], check=True,
                          capture_output=True, text=True, timeout=15)
    if info.stdout.strip() != 'linux':
        raise RuntimeError('Linux Docker required')
    containers = subprocess.run(['docker','ps','--format','{{json .}}'], check=True,
                               capture_output=True, text=True, timeout=15)
    stats = subprocess.run(['docker','stats','--no-stream','--format','{{json .}}'], check=True,
                          capture_output=True, text=True, timeout=15)
    result = {'regionId': context.id, 'action': action, 'memory': current,
              'source': str(context.pbf_path), 'output': str(context.map_path.parent.parent),
              'containers': [json.loads(line) for line in containers.stdout.splitlines()],
              'dockerStats': [json.loads(line) for line in stats.stdout.splitlines()]}
    print(json.dumps({'regionalPreflight': result}, ensure_ascii=True), flush=True)
    return result
