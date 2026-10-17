"""Allowlisted Hanoi CAR pilot pipeline; legacy HCM commands remain in pipeline.py.

Every output stage is write-once and content verified on reuse. Incomplete or
stale artifacts require a deliberately chosen new namespace/config, never overwrite.
"""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from backend.app.regions import default_registry
from scripts.pipeline import ROOT, Osmium, execute, image_lock, refuse_existing, sha256, write_json


def checked_manifest(path, identity):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("identity") != identity:
        raise RuntimeError(f"Artifact identity/config/version mismatch: {path}")
    return data


def check_files(directory, hashes):
    if not hashes:
        raise RuntimeError("Empty artifact hash manifest")
    for name, digest in hashes.items():
        if Path(name).name != name or not (directory/name).is_file() or sha256(directory/name) != digest:
            raise RuntimeError(f"Missing/corrupt artifact: {name}")


def profile_evidence(image):
    # Pin all profile dependencies, not only car.lua. Image digest also pins binaries.
    raw = execute(["docker", "run", "--rm", image, "sh", "-c",
        "find /opt -type f -name '*.lua' -exec sha256sum {} + | sort"], capture=True)
    return dict((line.split(None, 1)[1], line.split()[0]) for line in raw.splitlines())


def run(settings, args):
    c = default_registry(settings).resolve(args.region)
    identity, dry = c.artifact_identity, args.dry_run
    base = c.map_path.parent.parent
    extracted, graph_dir = c.extracted_path, c.routing_dir
    meta_path = extracted.with_suffix('.metadata.json')
    source_path = base/'source-verification.json'
    graph_pbf = graph_dir/f'{c.graph_basename}.osm.pbf'
    manifest_path, incomplete = graph_dir/'manifest.json', graph_dir/'.incomplete'
    config = json.loads((ROOT/'config/regions/nvmr-hanoi-core.json').read_text(encoding='utf-8'))
    print(json.dumps({'region': c.id, 'profile': args.profile, 'identity': identity,
        'source': str(c.pbf_path), 'outputs': str(base), 'operating': c.operating_bbox,
        'display': c.region.display_bbox, 'routing': c.routing_bbox, 'render': c.render_bbox}, ensure_ascii=False), flush=True)
    if dry:
        print(f'PREFLIGHT {args.action}: input read-only; outputs isolated; no Docker/data reads or writes')
        print(f'osmium smart extract {c.routing_bbox}; render {c.render_bbox}; OSRM /opt/car.lua MLD; port 5001')
        return 0
    if execute(['docker','info','--format','{{.OSType}}'], capture=True).strip() != 'linux':
        raise RuntimeError('Linux Docker required')
    now = datetime.now(timezone.utc).isoformat()
    if args.action == 'verify':
        osmium = Osmium(settings, False)
        digest = sha256(c.pbf_path)
        if source_path.exists():
            old = checked_manifest(source_path, identity)
            stat = c.pbf_path.stat()
            if old['sha256'] == digest:
                # Relocation/mtime changes may refresh the cached path/stat only
                # after verifying the exact original content; never accept new bytes.
                if old['mtime_ns'] != stat.st_mtime_ns or old['path'] != str(c.pbf_path):
                    old.update(path=str(c.pbf_path),mtime_ns=stat.st_mtime_ns,size_bytes=stat.st_size)
                    write_json(source_path,old)
                print('REUSE verified source'); return 0
            raise RuntimeError('Source changed; refusing stale verification reuse')
        info = json.loads(osmium.run(['fileinfo','-e','-j',c.pbf_path], capture=True))
        boxes = info['header']['boxes']
        w,s,e,n = c.routing_bbox
        if not any(b[0] <= w < e <= b[2] and b[1] <= s < n <= b[3] for b in boxes):
            raise RuntimeError('National source does not cover requested graph')
        stat = c.pbf_path.stat()
        write_json(source_path, dict(identity=identity, path=str(c.pbf_path), size_bytes=stat.st_size,
            mtime_ns=stat.st_mtime_ns, sha256=digest, format_verified=True, fileinfo=info,
            osmium_image=osmium.image, source_url=c.region.source_url, attribution=c.region.attribution, created_utc=now))
        return 0
    source = checked_manifest(source_path, identity)
    if sha256(c.pbf_path) != source['sha256']:
        raise RuntimeError('Source checksum mismatch')
    if args.action == 'extract':
        if extracted.exists() and meta_path.exists():
            old = checked_manifest(meta_path, identity)
            if old['source_sha256'] == source['sha256'] and old['extract_sha256'] == sha256(extracted):
                print('REUSE verified region extract'); return 0
        refuse_existing([extracted, meta_path])
        osmium = Osmium(settings, False)
        osmium.run(['extract','--bbox',','.join(map(str,c.routing_bbox)), '--strategy','smart',
            '-S','types=multipolygon,restriction','--set-bounds','-o',extracted,c.pbf_path],extracted.parent)
        osmium.run(['check-refs', extracted])
        info = json.loads(osmium.run(['fileinfo','-e','-j',extracted], capture=True))
        write_json(meta_path, dict(identity=identity, source_sha256=source['sha256'], extract_sha256=sha256(extracted),
            routing_bbox=c.routing_bbox, strategy='smart', relation_types='multipolygon,restriction',
            fileinfo=info, osmium_image=osmium.image, created_utc=now))
        return 0
    meta = checked_manifest(meta_path, identity)
    if meta['extract_sha256'] != sha256(extracted) or meta['source_sha256'] != source['sha256']:
        raise RuntimeError('Extract/source mismatch')
    if args.action == 'display':
        from scripts.render_data import prepare_display
        prepare_display(c, extracted, Osmium(settings, False), False)
        return 0
    image = image_lock(settings.osrm_image, False)
    mount = f'type=bind,source={graph_dir},target=/data'
    profile = profile_evidence(image)
    if args.action == 'routing':
        if manifest_path.exists() and not incomplete.exists():
            old = checked_manifest(manifest_path, identity)
            if old['extract_sha256'] != meta['extract_sha256'] or old['image_digest'] != image or old['profile_dependencies'] != profile:
                raise RuntimeError('Graph inputs/profile changed')
            check_files(graph_dir, old['artifact_sha256'])
            print('REUSE verified CAR MLD graph'); return 0
        refuse_existing([manifest_path,incomplete,graph_pbf,*graph_dir.glob(f'{c.graph_basename}.osrm*')])
        graph_dir.mkdir(parents=True,exist_ok=True)
        incomplete.write_text('preprocessing incomplete',encoding='utf-8')
        shutil.copyfile(extracted,graph_pbf)
        command=['docker','run','--rm','--memory','2g','--cpus','4','--mount',mount,image]
        for tool,params in [('osrm-extract',['-p','/opt/car.lua',f'/data/{graph_pbf.name}']),
                            ('osrm-partition',[f'/data/{c.graph_basename}.osrm']),
                            ('osrm-customize',[f'/data/{c.graph_basename}.osrm'])]:
            execute(command+[tool,*params])
        artifacts=sorted(graph_dir.glob(f'{c.graph_basename}.osrm.*'))
        if len(artifacts)<20 or any(p.stat().st_size<=0 for p in artifacts):
            raise RuntimeError('Incomplete MLD graph')
        write_json(manifest_path,dict(identity=identity,region_id=c.id,algorithm='mld',profile='car',
            profile_path='/opt/car.lua',profile_sha256=profile['/opt/car.lua'],profile_dependencies=profile,
            image_digest=image,osrm_version=execute(['docker','run','--rm',image,'osrm-routed','--version'],capture=True).strip(),
            routing_bbox=c.routing_bbox,extract_sha256=meta['extract_sha256'],input_sha256=sha256(graph_pbf),
            source_sha256=source['sha256'],artifact_sizes={p.name:p.stat().st_size for p in artifacts},
            artifact_sha256={p.name:sha256(p) for p in artifacts},created_utc=now))
        incomplete.unlink()
        return 0
    graph=checked_manifest(manifest_path,identity)
    if (incomplete.exists() or graph['image_digest']!=image or graph['profile_dependencies']!=profile
            or graph['extract_sha256']!=meta['extract_sha256'] or graph['source_sha256']!=source['sha256']
            or graph['routing_bbox']!=list(c.routing_bbox) or graph['input_sha256']!=sha256(graph_pbf)):
        raise RuntimeError('Graph incomplete or wrong profile/image')
    check_files(graph_dir,graph['artifact_sha256'])
    name=config['container_name']
    existing=subprocess.run(['docker','container','inspect',name],capture_output=True,text=True,encoding='utf-8')
    if existing.returncode==0:
        container=json.loads(existing.stdout)[0]
        if (container['Config'].get('Labels',{}).get('nvmr-region')!=c.id
                or container['Config']['Image']!=image
                or container['Config']['Cmd']!=['osrm-routed','--algorithm','mld',f'/data/{c.graph_basename}.osrm']
                or not any(Path(m['Source']).resolve()==graph_dir.resolve() and m['Destination']=='/data' and not m['RW'] for m in container['Mounts'])
                or container['HostConfig']['PortBindings'].get('5000/tcp')!=[{'HostIp':'127.0.0.1','HostPort':'5001'}]):
            raise RuntimeError('Container identity/mount/port mismatch; not replacing it')
        if not container['State']['Running']:
            execute(['docker','start',name])
    else:
        execute(['docker','run','--detach','--name',name,'--label',f'nvmr-region={c.id}',
            '--label','gsm-map-sandbox=true','--memory','1g','--cpus','2','-p','127.0.0.1:5001:5000',
            '--mount',mount+',readonly',image,'osrm-routed','--algorithm','mld',f'/data/{c.graph_basename}.osrm'])
    # Graph-specific hints (OSRM graph checksum) and positions bind readiness to this
    # inspected image/read-only mount, rather than any /nearest HTTP success.
    import httpx
    import time
    probes=[]
    for point in [c.viewport_center,(105.841,21.028),(105.832,21.039)]:
        for attempt in range(30):
            try:
                response=httpx.get(f'{c.osrm_base_url}/nearest/v1/driving/{point[0]},{point[1]}',trust_env=False,timeout=3)
                response.raise_for_status(); waypoint=response.json()['waypoints'][0]; break
            except (httpx.HTTPError,KeyError):
                if attempt==29: raise
                time.sleep(.5)
        probes.append({'point':point,'location':waypoint['location'],'hint':waypoint['hint']})
    proof=dict(identity=identity,manifest_sha256=sha256(manifest_path),container=name,image_digest=image,probes=probes)
    evidence_path=graph_dir/'router-evidence.json'
    if evidence_path.exists():
        previous=json.loads(evidence_path.read_text(encoding='utf-8'))
        # Restarting an unchanged graph must preserve its historical proof bytes.
        if any(previous.get(k)!=json.loads(json.dumps(v)) for k,v in proof.items()):
            raise RuntimeError('Existing router evidence differs; refusing to overwrite historical CAR evidence')
        print('REUSE unchanged graph-specific router evidence')
    else:
        write_json(evidence_path,{**proof,'created_utc':now})
    print('SERVING verified local CAR graph; backend also checks artifacts and graph-specific probes')
    return 0
