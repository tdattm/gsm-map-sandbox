"""Write-once Connected NVMR GIS stages. Run exactly one heavy stage at a time."""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.pipeline import Osmium, execute, image_lock, sha256, write_json
from scripts.region_pipeline import check_files, profile_evidence
from scripts.m3_resources import memory, Monitor
from backend.app.config import Settings
from backend.app.integrity import digest,verified_files
OSRM_IMAGE='ghcr.io/project-osrm/osrm-backend@sha256:855614a38f464b0558a2ad6eaa7cb8c139f39887da9b38b485ce453c6e6e6124'
CAR_PROFILE_SHA256='cb3df0546318665609606b746a1297f3d65ca3c2ff825f8a6f3c57247d86a2d3'


@contextmanager
def heavy_lock():
    path=ROOT/'build/connected-gis.lock';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0);stream.write(b'1');stream.flush();stream.seek(0)
        if sys.platform=='win32':
            import msvcrt
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc:raise RuntimeError('Another Connected GIS stage owns the heavy slot') from exc
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            stream.seek(0)
            if sys.platform=='win32':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)


def config(root=ROOT):
    return json.loads((root/'config/connected-nvmr.json').read_text(encoding='utf-8-sig'))


def identity(root=ROOT):
    c = config(root)
    return {'region_id':c['regionId'], 'config_sha256':sha256(root/'config/connected-nvmr.json'),
            'pipeline_version':c['pipelineVersion']}


def base(root=ROOT):
    return root/'data/regions/nvmr-connected'


def guard(action):
    m = memory()
    disk = shutil.disk_usage(ROOT)
    proof = {'action':action,'memory':m,'diskFreeBytes':disk.free}
    print(json.dumps({'preflight':proof}),flush=True)
    if min(m['availablePhysicalBytes'],m.get('systemCommitAvailableBytes',2**40)) < 2*1024**3:
        raise RuntimeError('RESOURCE_STOP: >=2GiB physical AND commit headroom required')
    if disk.free < 8*1024**3:
        raise RuntimeError('RESOURCE_STOP: >=8GiB free disk required')
    # Measured full-rectangle extraction exhausted physical headroom under the
    # historical floor. New extracts need 5GiB cap + 1GiB reserve; reuse does not.
    if action=='extract-fresh' and min(m['availablePhysicalBytes'],m.get('systemCommitAvailableBytes',2**40))<6*1024**3:
        raise RuntimeError('RESOURCE_STOP: fresh Connected smart extract requires >=6GiB available physical RAM AND commit after observed transient pressure; reuse verified extract when available')
    return proof


def verify_source(root=ROOT):
    c=config(root); path=root/c['source']['path']
    if sha256(path)!=c['source']['sha256']:
        raise RuntimeError('National source SHA256 differs from pinned R1a source')
    return path


def verify_render(root=ROOT):
    folder=base(root)/'render'; path=folder/'manifest.json'
    if (folder/'.incomplete').exists(): raise RuntimeError('Basemap incomplete')
    m=json.loads(path.read_text(encoding='utf-8'))
    if m['identity']!=identity(root):raise RuntimeError('Basemap config identity changed')
    if m['source_sha256']!=config(root)['source']['sha256']:raise RuntimeError('Basemap source mismatch')
    c=config(root)
    if (m['map_bbox']!=c['mapBbox'] or m['minzoom']!=c['tiles']['minZoom'] or m['maxzoom']!=c['tiles']['maxZoom'] or m['source_layers']!=c['tiles']['sourceLayers'] or set(m['artifact_sha256'])!={'tiles.mbtiles'}):raise RuntimeError('Wrong basemap coverage/format')
    extract=base(root)/'extracted/coverage.osm.pbf'
    if m['extract_sha256']!=digest(extract):raise RuntimeError('Basemap extract changed')
    if not verified_files(folder,m['artifact_sha256']):raise RuntimeError('Basemap content changed')
    return m


def verify_graph(mode,root=ROOT):
    folder=base(root)/'routing'/mode.lower()
    if (folder/'.incomplete').exists():raise RuntimeError('Graph incomplete')
    m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if m['identity']!=identity(root) or m['profile']!=mode.lower():raise RuntimeError('Wrong graph identity/mode')
    if m['source_sha256']!=config(root)['source']['sha256']:raise RuntimeError('Wrong graph source')
    c=config(root); expected=c['routing'][mode]['profilePath']
    if m['algorithm']!='mld' or m['routing_bbox']!=c['routingBbox'] or m['profile_path']!=expected or m['profile_dependencies'][expected]!=m['profile_sha256']:raise RuntimeError('Graph profile/coverage mismatch')
    if mode=='MOTORBIKE' and digest(root/'profiles/motorbike.lua')!=m['profile_sha256']:raise RuntimeError('Motorbike profile changed')
    if mode=='CAR' and m['profile_sha256']!=CAR_PROFILE_SHA256:raise RuntimeError('CAR profile differs from pinned verified profile')
    if m['image_digest']!=OSRM_IMAGE:raise RuntimeError('OSRM binary/profile image changed')
    if digest(root/c['source']['path'])!=c['source']['sha256']:raise RuntimeError('National source bytes changed')
    if m['extract_sha256']!=digest(base(root)/'extracted/coverage.osm.pbf'):raise RuntimeError('Graph extract changed')
    if not {'connected.osrm.partition','connected.osrm.cells','connected.osrm.mldgr'}<=set(m['artifact_sha256']):raise RuntimeError('Missing MLD files')
    if set(m['artifact_sha256'])!=set(m['artifact_sizes']) or any((folder/n).stat().st_size!=s for n,s in m['artifact_sizes'].items()):raise RuntimeError('Graph size manifest mismatch')
    if not verified_files(folder,m['artifact_sha256']):raise RuntimeError('Graph content changed')
    return m


def run(action,mode='CAR'):
    c=config(); out=base(); out.mkdir(parents=True,exist_ok=True)
    settings=Settings(); extract=out/'extracted/coverage.osm.pbf'
    preflight=guard(action)
    if action=='verify':
        source=verify_source(); osmium=Osmium(settings,False)
        info=json.loads(osmium.run(['fileinfo','-e','-j',source],capture=True))
        timestamp=info['header'].get('option',{}).get('osmosis_replication_timestamp')
        if timestamp!=c['source']['timestamp']:raise RuntimeError(f'Source timestamp mismatch {timestamp}')
        w,s,e,n=c['routingBbox']
        if not any(b[0]<=w<e<=b[2] and b[1]<=s<n<=b[3] for b in info['header']['boxes']):raise RuntimeError('Source coverage missing')
        target=out/'source-verification.json'
        proof={'identity':identity(),'sha256':sha256(source),'size_bytes':source.stat().st_size,
               'timestamp':timestamp,'fileinfo':info,'osmium_image':osmium.image,'preflight':preflight}
        if target.exists():
            old=json.loads(target.read_text(encoding='utf-8'))
            if old['identity']!=proof['identity'] or old['sha256']!=proof['sha256']:raise RuntimeError('Source proof mismatch')
            print('REUSE verified source');return
        write_json(target,proof);return
    source=json.loads((out/'source-verification.json').read_text(encoding='utf-8'))
    if source['identity']!=identity() or source['sha256']!=c['source']['sha256']:raise RuntimeError('Verified source/config required')
    if action=='extract':
        meta=extract.with_suffix('.metadata.json'); incomplete=extract.parent/'.incomplete'
        if meta.exists() and not incomplete.exists():
            old=json.loads(meta.read_text(encoding='utf-8'))
            if old['identity']==identity() and old['extract_sha256']==sha256(extract):print('REUSE extract');return
            raise RuntimeError('Extract proof mismatch')
        if extract.exists() or incomplete.exists():raise RuntimeError('Refusing overwrite of incomplete extract')
        guard('extract-fresh')
        verify_source(); extract.parent.mkdir(parents=True,exist_ok=True);incomplete.write_text('extract incomplete')
        osmium=Osmium(settings,False)
        with Monitor(.5) as monitor:
            osmium.run(['extract','--bbox',','.join(map(str,c['routingBbox'])),'--strategy','smart','-S','types=multipolygon,restriction','--set-bounds','-o',extract,ROOT/c['source']['path']],extract.parent)
            osmium.run(['check-refs',extract])
        write_json(meta,{'identity':identity(),'source_sha256':source['sha256'],'extract_sha256':sha256(extract),'routing_bbox':c['routingBbox'],'resources':monitor.result()})
        incomplete.unlink();return
    meta=json.loads(extract.with_suffix('.metadata.json').read_text(encoding='utf-8'))
    if meta['identity']!=identity() or meta['extract_sha256']!=sha256(extract):raise RuntimeError('Extract identity mismatch')
    if action in ('render','anchors'):
        from scripts.connected_gis_render import build
        return build(action,extract,c,identity(),out)
    directory=out/'routing'/mode.lower(); manifest=directory/'manifest.json';incomplete=directory/'.incomplete'
    image=image_lock(settings.osrm_image,False);deps=profile_evidence(image)
    if image!=OSRM_IMAGE:raise RuntimeError('Configured OSRM binary differs from pinned Connected image; refusing build/serve')
    if deps.get('/opt/car.lua')!=CAR_PROFILE_SHA256:raise RuntimeError('Resolved CAR profile differs from pinned Connected profile; refusing build/serve')
    if mode=='MOTORBIKE':deps['/profiles/motorbike.lua']=sha256(ROOT/'profiles/motorbike.lua')
    profile=c['routing'][mode]['profilePath'];graph='/data/connected.osrm'
    mount=f'type=bind,source={directory},target=/data'
    if action=='routing':
        if manifest.exists():
            old=verify_graph(mode)
            if old['profile_dependencies']!=deps or old['image_digest']!=image or old['extract_sha256']!=meta['extract_sha256']:raise RuntimeError('Graph inputs changed')
            print('REUSE graph');return
        if directory.exists() and any(directory.iterdir()):raise RuntimeError('Refusing overwrite of graph artifacts')
        directory.mkdir(parents=True,exist_ok=True);incomplete.write_text('OSRM MLD preprocessing incomplete')
        shutil.copyfile(extract,directory/'connected.osm.pbf')
        command=['docker','run','--rm','--memory','2g','--cpus','4','--mount',mount]
        if mode=='MOTORBIKE':command+=['--mount',f'type=bind,source={ROOT / "profiles"},target=/profiles,readonly']
        stages=[]
        for tool,params in [('osrm-extract',['--threads','2','-p',profile,'/data/connected.osm.pbf']),('osrm-partition',['--threads','2',graph]),('osrm-customize',['--threads','2',graph])]:
            started=time.time()
            import threading
            stop=threading.Event();samples=[]
            def sample_docker():
                while not stop.is_set():
                    try:
                        r=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}'],capture_output=True,text=True,timeout=12)
                        samples.append({'unix':time.time(),'stats':[json.loads(x) for x in r.stdout.splitlines()],'exitCode':r.returncode,'stderr':r.stderr.strip()})
                    except (OSError,subprocess.TimeoutExpired,ValueError) as exc:
                        samples.append({'unix':time.time(),'unavailableError':str(exc)})
                    stop.wait(2)
            thread=threading.Thread(target=sample_docker,daemon=True);thread.start()
            try:
                with Monitor(.5) as monitor:
                    result=subprocess.run(command+[image,tool,*params],capture_output=True,text=True,encoding='utf-8')
            finally:
                stop.set();thread.join()
            log=directory/f'{tool}.log';log.write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
            stages.append({'stage':tool,'exitCode':result.returncode,'resources':monitor.result(),'log':log.name,'startedUnix':started,'dockerSamples':samples})
            write_json(directory/'build-resources.json',{'preflight':preflight,'stages':stages})
            print(json.dumps({k:v for k,v in stages[-1].items() if k!='dockerSamples'}),flush=True)
            result.check_returncode()
        artifacts=sorted(directory.glob('connected.osrm.*'))
        if len(artifacts)<20 or any(p.stat().st_size==0 for p in artifacts):raise RuntimeError('Incomplete MLD graph')
        write_json(manifest,{'identity':identity(),'region_id':c['regionId'],'profile':mode.lower(),'algorithm':'mld','profile_path':profile,'profile_sha256':deps[profile],'profile_dependencies':deps,'image_digest':image,'source_sha256':source['sha256'],'extract_sha256':meta['extract_sha256'],'routing_bbox':c['routingBbox'],'artifact_sha256':{p.name:sha256(p) for p in artifacts},'artifact_sizes':{p.name:p.stat().st_size for p in artifacts},'resources':stages})
        incomplete.unlink();return
    m=verify_graph(mode)
    if image!=m['image_digest'] or deps!=m['profile_dependencies']:raise RuntimeError('Runtime binary/profile differs from graph manifest; refusing router startup')
    name=c['routing'][mode]['containerName'];port=c['routing'][mode]['baseUrl'].rsplit(':',1)[1]
    # Verified in the pinned v5.27.1 binary's actual --help. Map immutable
    # full-coverage graph files instead of copying ~1.7GB into each router heap.
    command=['osrm-routed','--algorithm','mld','--mmap=1',graph,'--max-table-size','256']
    existing=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
    if existing.returncode==0:
        d=json.loads(existing.stdout)[0]
        if (d['Config']['Image']!=image or d['Config']['Cmd']!=command or d['Config']['Labels'].get('nvmr-region')!=c['regionId'] or not any(Path(x['Source']).resolve()==directory.resolve() and not x['RW'] and x['Destination']=='/data' for x in d['Mounts']) or d['HostConfig']['PortBindings'].get('5000/tcp')!=[{'HostIp':'127.0.0.1','HostPort':port}]):raise RuntimeError('Router identity mismatch')
        if not d['State']['Running']:execute(['docker','start',name])
    else:
        execute(['docker','run','--detach','--name',name,'--label',f'nvmr-region={c["regionId"]}','--label',f'nvmr-mode={mode}','--memory','1g','--cpus','2','-p',f'127.0.0.1:{port}:5000','--mount',mount+',readonly',image,*command])
    import httpx
    probes=[]
    for zone in c['operatingZones']:
        p=zone['probe']
        for attempt in range(40):
            try:
                r=httpx.get(f'{c["routing"][mode]["baseUrl"]}/nearest/v1/driving/{p[0]},{p[1]}',timeout=3,trust_env=False);r.raise_for_status();w=r.json()['waypoints'][0];break
            except (httpx.HTTPError,KeyError):
                if attempt==39:raise
                time.sleep(.5)
        probes.append({'point':p,'location':w['location'],'hint':w['hint'],'zoneId':zone['id']})
    proof={'identity':identity(),'manifest_sha256':sha256(manifest),'container':name,'image_digest':image,'command':command,'memoryMappedReadOnly':True,'probes':probes}
    target=directory/'router-evidence.json'
    if target.exists():
        if json.loads(target.read_text(encoding='utf-8'))!=proof:raise RuntimeError('Router evidence mismatch')
    else:write_json(target,proof)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['verify','extract','render','anchors','routing','serve']);p.add_argument('--mode',choices=['CAR','MOTORBIKE'],default='CAR');a=p.parse_args()
    with heavy_lock():run(a.action,a.mode)
