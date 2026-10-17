"""Isolated, write-once MOTORBIKE MLD build/reuse and inspected loopback service."""
import json
import shutil
import subprocess
import time
from pathlib import Path
import httpx
from backend.app.modes import resolve_mode, ROOT
from backend.app.regions import default_registry
from scripts.pipeline import execute, image_lock, refuse_existing, sha256, write_json
from scripts.region_pipeline import check_files, checked_manifest, profile_evidence


def run(settings,args):
    c=resolve_mode(default_registry(settings),args.region,'MOTORBIKE')
    if args.action not in ('routing','serve'):
        raise RuntimeError('MOTORBIKE reuses CAR verified extract/render; use --profile car for verify/extract/display')
    print(json.dumps({'region':c.id,'mode':'MOTORBIKE','identity':c.artifact_identity,'output':str(c.routing_dir)}))
    if args.dry_run:
        print('PREFLIGHT: read-only existing CAR inputs; isolated MOTORBIKE graph/service 5002; no writes');return 0
    # Do not mutate/rebuild shared CAR source or render artifacts.
    from backend.app.dataset import artifact_status,pbf_status
    if not pbf_status(c.base)['format_verified'] or not artifact_status(c.base)['map_ready']:
        raise RuntimeError('Verified shared source/extract/render required')
    directory=c.routing_dir
    image=image_lock(settings.osrm_image,False)
    dependencies=profile_evidence(image)
    dependencies['/profiles/motorbike.lua']=sha256(ROOT/'profiles/motorbike.lua')
    manifest=directory/'manifest.json'
    incomplete=directory/'.incomplete'
    graph=f'/data/{c.graph_basename}.osrm'
    mount=f'type=bind,source={directory},target=/data'
    profile_mount=f'type=bind,source={ROOT / "profiles"},target=/profiles,readonly'
    if args.action=='routing' and not manifest.exists():
        refuse_existing([incomplete,*directory.glob('*')])
        directory.mkdir(parents=True,exist_ok=True)
        incomplete.write_text('MLD preprocessing incomplete')
        target=directory/f'{c.graph_basename}.osm.pbf'
        shutil.copyfile(c.extracted_path,target)
        if sha256(target)!=sha256(c.extracted_path):
            raise RuntimeError('Copied graph input differs from verified extract')
        base=['docker','run','--rm','--memory','2g','--cpus','4','--mount',mount,'--mount',profile_mount,image]
        for tool,params in [('osrm-extract',['-p','/profiles/motorbike.lua',f'/data/{target.name}']),
                            ('osrm-partition',[graph]),('osrm-customize',[graph])]:
            execute(base+[tool,*params])
        artifacts=list(directory.glob(f'{c.graph_basename}.osrm.*'))
        if len(artifacts)<20 or any(p.stat().st_size<=0 for p in artifacts):raise RuntimeError('Incomplete graph')
        source=json.loads((c.map_path.parent.parent/'source-verification.json').read_text())
        write_json(manifest,dict(identity=c.artifact_identity,profile='motorbike',algorithm='mld',
            profile_path='/profiles/motorbike.lua',profile_sha256=dependencies['/profiles/motorbike.lua'],
            profile_dependencies=dependencies,image_digest=image,
            osrm_version=execute(['docker','run','--rm',image,'osrm-routed','--version'],capture=True).strip(),
            source_sha256=source['sha256'],extract_sha256=sha256(c.extracted_path),routing_bbox=c.routing_bbox,
            artifact_sizes={p.name:p.stat().st_size for p in artifacts},artifact_sha256={p.name:sha256(p) for p in artifacts}))
        incomplete.unlink()
    data=checked_manifest(manifest,c.artifact_identity)
    if (incomplete.exists() or data['image_digest']!=image or data['profile_dependencies']!=dependencies
            or data['extract_sha256']!=sha256(c.extracted_path)):
        raise RuntimeError('Graph/profile/input identity mismatch; refusing overwrite')
    check_files(directory,data['artifact_sha256'])
    if args.action=='routing':print('REUSE verified MOTORBIKE MLD graph');return 0
    config=json.loads((ROOT/'config/regions/nvmr-hanoi-core-motorbike.json').read_text())
    name=config['container_name']; port='5002'
    existing=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
    cmd=['osrm-routed','--algorithm','mld',graph]
    if existing.returncode==0:
        d=json.loads(existing.stdout)[0]
        if (d['Config']['Image']!=image or d['Config']['Cmd']!=cmd
            or d['Config'].get('Labels',{}).get('nvmr-mode')!='MOTORBIKE'
            or not any(Path(m['Source']).resolve()==directory.resolve() and m['Destination']=='/data' and not m['RW'] for m in d['Mounts'])
            or d['HostConfig']['PortBindings'].get('5000/tcp')!=[{'HostIp':'127.0.0.1','HostPort':port}]):
            raise RuntimeError('Existing container belongs to different config; not replacing')
        if not d['State']['Running']:execute(['docker','start',name])
    else:
        execute(['docker','run','--detach','--name',name,'--label','gsm-map-sandbox=true','--label','nvmr-mode=MOTORBIKE',
            '--memory','1g','--cpus','2','-p',f'127.0.0.1:{port}:5000','--mount',mount+',readonly',image,*cmd])
    probes=[]
    for point in [c.viewport_center,(105.841,21.028),(105.832,21.039)]:
        for attempt in range(30):
            try:
                r=httpx.get(f'{c.osrm_base_url}/nearest/v1/driving/{point[0]},{point[1]}',timeout=3,trust_env=False)
                r.raise_for_status(); w=r.json()['waypoints'][0];break
            except (httpx.HTTPError,KeyError):
                if attempt==29:raise
                time.sleep(.5)
        probes.append(dict(point=point,location=w['location'],hint=w['hint']))
    write_json(directory/'router-evidence.json',dict(identity=c.artifact_identity,manifest_sha256=sha256(manifest),
        container=name,image_digest=image,probes=probes))
    print('Serving MOTORBIKE; NOT READY until independent validation.json passes')
    return 0


