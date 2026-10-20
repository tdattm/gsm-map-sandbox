"""Independent local connected graph probes, profile oracle and bounded anchors."""
import argparse
import concurrent.futures
import contextlib
import json
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import httpx
from scripts.connected_gis import config,base,identity,verify_graph,heavy_lock,guard,OSRM_IMAGE
from scripts.pipeline import sha256,write_json,image_lock
from backend.app.config import Settings
from scripts.validate_regional_routing import assert_table_route_consistency
from scripts.validate_regional_routing import oneway_audit


def routing_identity(mode,m):
    return {'regionId':'nvmr-connected','vehicleType':mode,'profile':m['profile'],'profileSha256':m['profile_sha256'],
            'graphManifestSha256':sha256(base()/'routing'/mode.lower()/'manifest.json'),'sourceSha256':m['source_sha256'],
            'extractSha256':m['extract_sha256'],'algorithm':'mld'}


def snap_candidate(client,anchor,max_snap_meters=100):
    """Treat OSRM's bounded snap miss as data, preserving real service failures."""
    lon,lat=anchor['coordinate']
    for attempt in range(3):
        try:
            response=client.get(f'/nearest/v1/driving/{lon},{lat}',params={'radiuses':max_snap_meters})
            break
        except httpx.RemoteProtocolError:
            if attempt==2:raise
    data=response.json()
    if response.status_code in (200,400) and data.get('code') in ('NoSegment','NoRoute'):
        return anchor,data
    response.raise_for_status()
    if data.get('code')!='Ok':raise RuntimeError(f'Unexpected nearest response: {data}')
    return anchor,data


def prepare_synthetic():
    """Run the small fresh oracle before admitting memory-mapped full routers."""
    guard('profile-oracle')
    evidence=base()/'validation';evidence.mkdir(parents=True,exist_ok=True)
    oracle_path=evidence/'synthetic-validation.json';sidecar=evidence/'synthetic-current-proof.json'
    expected={'profileSha256':sha256(ROOT/'profiles/motorbike.lua'),
              'generatorSha256':sha256(ROOT/'scripts/validate_motorbike.py'),
              'connectedValidatorSha256':sha256(Path(__file__)),
              'imageDigest':image_lock(Settings().osrm_image,False)}
    if expected['imageDigest']!=OSRM_IMAGE:raise RuntimeError('Fresh oracle image differs from pinned Connected OSRM binary')
    if oracle_path.exists() and sidecar.exists():
        saved=json.loads(sidecar.read_text(encoding='utf-8'))
        oracle=json.loads(oracle_path.read_text(encoding='utf-8'))
        if saved!={**expected,'evidenceSha256':sha256(oracle_path)} or oracle['status']!='PASS' or oracle['profile_sha256']!=expected['profileSha256']:
            raise RuntimeError('Prepared current oracle changed; refusing reuse/overwrite')
        print('REUSE fresh current-profile oracle with pinned generator/binary/evidence identity',flush=True);return
    if oracle_path.exists() or sidecar.exists():raise RuntimeError('Incomplete oracle proof; preserve before safe retry')
    from scripts import validate_motorbike as oracle_module
    workspace=evidence/'oracle-workspace';profiles=workspace/'profiles';profiles.mkdir(parents=True,exist_ok=True)
    for source in (ROOT/'profiles').iterdir():
        if source.is_file():shutil.copyfile(source,profiles/source.name)
    historical_root=oracle_module.ROOT
    try:
        oracle_module.ROOT=workspace
        oracle_module.synthetic(evidence)
    finally:oracle_module.ROOT=historical_root
    oracle=json.loads(oracle_path.read_text(encoding='utf-8'))
    if oracle['status']!='PASS' or oracle['profile_sha256']!=expected['profileSha256']:raise RuntimeError('Fresh oracle did not verify current MOTORBIKE profile')
    write_json(sidecar,{**expected,'evidenceSha256':sha256(oracle_path)})


def validate(skip_synthetic=False):
    c=config();out=base();guard('routing-validation');manifests={mode:verify_graph(mode) for mode in c['routing']}
    evidence=out/'validation';evidence.mkdir(parents=True,exist_ok=True)
    for mode in manifests:(out/'routing'/mode.lower()/'.validation-incomplete').write_text('independent routing validation incomplete')
    if skip_synthetic:
        previous=ROOT/'docs/nvmr/r1a-evidence/gis/nvmr-bac-ninh-core/synthetic-validation.json'
        oracle=json.loads(previous.read_text(encoding='utf-8'))
        if oracle['status']!='PASS' or oracle['profile_sha256']!=sha256(ROOT/'profiles/motorbike.lua'):raise RuntimeError('Historical profile oracle no longer matches current profile')
        write_json(evidence/'synthetic-validation.json',{**oracle,'reuseNote':'Reused R1a profile semantics oracle, current local profile digest matched. New graph is independently checked below.','reusedEvidenceSha256':sha256(previous)})
    else:
        prepare_synthetic()
    all_results={}
    for mode,m in manifests.items():
        url=c['routing'][mode]['baseUrl'];probes=[];results=[]
        with httpx.Client(base_url=url,trust_env=False,timeout=30) as client:
            for zone in c['operatingZones']:
                p=zone['probe'];r=client.get(f'/nearest/v1/driving/{p[0]},{p[1]}',params={'radiuses':100});r.raise_for_status();data=r.json()
                if data['code']!='Ok':raise RuntimeError(f'{mode} no nearby road in {zone["id"]}')
                w=data['waypoints'][0]
                if w['distance']>100:raise RuntimeError('Snap exceeds100m')
                probes.append({'zoneId':zone['id'],'coordinate':w['location'],'distance':w['distance'],'hint':w['hint']})
            coords=';'.join(','.join(map(str,p['coordinate'])) for p in probes)
            table=client.get('/table/v1/driving/'+coords,params={'annotations':'duration,distance','radiuses':';'.join(['10']*len(probes))}).json()
            if table['code']!='Ok':raise RuntimeError('Global probe Table failed')
            for i,origin in enumerate(probes):
                for j,destination in enumerate(probes):
                    if i==j:continue
                    p=';'.join(','.join(map(str,a['coordinate'])) for a in (origin,destination))
                    route=client.get('/route/v1/driving/'+p,params={'radiuses':'10;10','overview':'full','geometries':'geojson','annotations':'nodes'}).json()
                    assert_table_route_consistency(table['durations'][i][j],route)
                    if route['code']=='NoRoute' and (i==0 or j==0):raise RuntimeError(f'Required Hanoi hub pair disconnected for {mode}: {origin["zoneId"]}->{destination["zoneId"]}')
                    if route['code']=='Ok':
                        r=route['routes'][0]
                        if not(math.isfinite(r['duration']) and r['duration']>0 and math.isfinite(r['distance']) and r['distance']>0 and len(r['geometry']['coordinates'])>=2):raise RuntimeError('Invalid routed metrics/geometry')
                        if abs(r['distance']-table['distances'][i][j])>max(.11,r['distance']*1e-4):raise RuntimeError('Identical-input Table/Route distance mismatch')
                        w,s,e,n=c['routingBbox']
                        if not all(w<=x<=e and s<=y<=n for x,y in r['geometry']['coordinates']):raise RuntimeError('Route escapes routing rectangle')
                    results.append({'origin':origin['zoneId'],'destination':destination['zoneId'],'tableDuration':table['durations'][i][j],'response':route})
            # Two local points per zone exercise local trips separately from hub routes.
            local=[]
            raw=json.loads((out/'anchors/road-candidates.json').read_text(encoding='utf-8'))
            for zone in c['operatingZones']:
                lon,lat=zone['probe'];attempts=[]
                destinations=[p['coordinate'] for p in raw['candidates'] if p['zoneId']==zone['id'] and .001<abs(p['coordinate'][0]-lon)+abs(p['coordinate'][1]-lat)<.015][:12]
                for destination in destinations:
                    pair=f'{lon},{lat};{destination[0]},{destination[1]}'
                    response=client.get('/route/v1/driving/'+pair,params={'radiuses':'100;100','overview':'full','geometries':'geojson'}).json();attempts.append({'destination':destination,'response':response})
                    if response['code']=='Ok':
                        r=response['routes'][0]
                        if not(math.isfinite(r['distance']) and r['distance']>0 and math.isfinite(r['duration']) and r['duration']>0 and len(r['geometry']['coordinates'])>=2):raise RuntimeError('Invalid local route metrics/geometry')
                        break
                    if response['code'] not in ('NoRoute','NoSegment'):raise RuntimeError('Unexpected local route error')
                else:raise RuntimeError(f'No successful bounded local zone sample {zone["id"]} {mode}')
                local.append({'zoneId':zone['id'],'attempts':attempts,'response':response})
            sourceways=json.loads((out/'render/source-oneways.json').read_text(encoding='utf-8'))
            nodes={};ways=[]
            for record in sourceways['ways']:
                way=ET.Element('way',id=str(record['id']))
                for p in record['nodes']:nodes[p['id']]=p['coordinate'];ET.SubElement(way,'nd',ref=str(p['id']))
                for key,value in record['tags'].items():ET.SubElement(way,'tag',k=key,v=value)
                ways.append(way)
            one_way_cases=oneway_audit(SimpleNamespace(id='nvmr-connected',osrm_base_url=url),nodes,ways,client)
            # A disconnected component is searched for, never invented or forced.
            no_route_observation={'status':'NOT_OBSERVED','sampleCount':0}
            snapped_path=out/'anchors/snapped-anchors.json'
            if snapped_path.exists():
                anchors=json.loads(snapped_path.read_text(encoding='utf-8'))['modes'][mode]
                sample=anchors[::max(1,len(anchors)//100)][:100]
                points=[probes[0]['coordinate'],*[a['coordinate'] for a in sample]]
                coordinates=';'.join(','.join(map(str,p)) for p in points)
                raw_table=client.get('/table/v1/driving/'+coordinates,params={'sources':';'.join(map(str,range(1,len(points)))),'destinations':'0','radiuses':';'.join(['10']*len(points))}).json()
                if raw_table['code']!='Ok':raise RuntimeError('Negative connectivity sample Table failed')
                no_route_observation['sampleCount']=len(sample)
                for k,row in enumerate(raw_table['durations']):
                    if row[0] is None:
                        pair=';'.join(','.join(map(str,p)) for p in (points[k+1],points[0]))
                        raw_route=client.get('/route/v1/driving/'+pair,params={'radiuses':'10;10','overview':'full','geometries':'geojson'}).json()
                        assert_table_route_consistency(None,raw_route)
                        no_route_observation={'status':'OBSERVED','sampleCount':len(sample),'origin':points[k+1],'destination':points[0],'response':raw_route};break
            nosegment=client.get('/nearest/v1/driving/0,0',params={'radiuses':10}).json()
            if nosegment['code']!='NoSegment':raise RuntimeError('Remote bounded snap should be NoSegment')
        proof={'status':'PASS','mode':mode,'routingIdentity':routing_identity(mode,m),'probes':probes,'crossZoneRoutes':results,'localRoutes':local,'oneWaySourceCases':one_way_cases,'noSegment':nosegment,'realNoRouteObservation':no_route_observation,'connectedPairs':sum(r['response']['code']=='Ok' for r in results),'noRoutePairs':sum(r['response']['code']=='NoRoute' for r in results),'limitations':['Hub samples do not prove all OD connectivity; NoRoute remains a real graph failure','Mode/turn restrictions oracle is a separate generated network, not exhaustive real-world legal verification']}
        all_results[mode]=proof
        directory=out/'routing'/mode.lower();write_json(directory/'routing-validation.json',proof)
        shutil.copyfile(evidence/'synthetic-validation.json',directory/'synthetic-validation.json')
        write_json(directory/'validation.json',{'status':'PASS','regionId':'nvmr-connected','manifest_sha256':sha256(directory/'manifest.json'),'validator_sha256':sha256(Path(__file__)),'evidence_sha256':{name:sha256(directory/name) for name in ('routing-validation.json','synthetic-validation.json')}})
        (directory/'.validation-incomplete').unlink()
    write_json(evidence/'summary.json',{'status':'PASS','modes':{mode:{'connectedPairs':p['connectedPairs'],'noRoutePairs':p['noRoutePairs']} for mode,p in all_results.items()}})
    print(json.dumps({m:{k:v for k,v in p.items() if k in ('status','connectedPairs','noRoutePairs')} for m,p in all_results.items()}),flush=True)


@contextlib.contextmanager
def http10_keepalive():
    """Reuse explicit Content-Length HTTP/1.0 keep-alive sockets returned by osrm-routed."""
    import h11._connection as hc
    original=hc._keep_alive
    def keep_alive(event):
        connection=hc.get_comma_header(event.headers,b'connection')
        if b'close' in connection:return False
        if getattr(event,'http_version',b'1.1')<b'1.1':
            return b'keep-alive' in connection and bool(hc.get_comma_header(event.headers,b'content-length'))
        return True
    hc._keep_alive=keep_alive
    try:yield
    finally:hc._keep_alive=original


def snap_anchors():
    c=config();out=base();guard('anchor-snapping');folder=out/'anchors';folder.mkdir(parents=True,exist_ok=True)
    incomplete=folder/'.incomplete';path=folder/'snapped-anchors.json';manifest_path=folder/'manifest.json'
    if path.exists():
        if incomplete.exists() or not manifest_path.exists():raise RuntimeError('Existing anchor catalog incomplete; refusing overwrite')
        old=json.loads(path.read_text(encoding='utf-8'));manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        current={mode:routing_identity(mode,verify_graph(mode)) for mode in c['routing']}
        if (old['identity']!=identity() or old['routingIdentities']!=current or manifest['identity']!=identity() or old['boundaryVersion']!=c['boundaryVersion'] or old['sourceSha256']!=c['source']['sha256']):raise RuntimeError('Anchor catalog identity changed')
        if set(manifest['artifact_sha256'])!={'road-candidates.json','snapped-anchors.json'} or any(sha256(folder/name)!=value for name,value in manifest['artifact_sha256'].items()):raise RuntimeError('Anchor catalog bytes changed')
        print('REUSE verified mode-aware snapped anchor catalog');return
    if incomplete.exists() or manifest_path.exists():raise RuntimeError('Anchor output incomplete; refusing overwrite')
    incomplete.write_text('mode-aware bounded snapping incomplete')
    raw=json.loads((folder/'road-candidates.json').read_text(encoding='utf-8'));modes={};routing={};counts={}
    with http10_keepalive():
        for mode in c['routing']:
            m=verify_graph(mode);routing[mode]=routing_identity(mode,m);accepted=[];seen=set();rejects=Counter()
            with httpx.Client(base_url=c['routing'][mode]['baseUrl'],trust_env=False,timeout=20,headers={'Connection':'keep-alive'},limits=httpx.Limits(max_connections=64,max_keepalive_connections=64)) as client:
                def snap(anchor):
                    return snap_candidate(client,anchor,c['distribution']['maxSnapMeters'])
                with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
                    for anchor,data in pool.map(snap,raw['candidates']):
                        if data['code']!='Ok':rejects[data['code']]+=1;continue
                        p=data['waypoints'][0];coordinate=p['location'];key=tuple(coordinate);zone=next(z for z in c['operatingZones'] if z['id']==anchor['zoneId']);w,s,e,n=zone['bbox']
                        if p['distance']>c['distribution']['maxSnapMeters'] or not(w<=coordinate[0]<e and s<=coordinate[1]<n):rejects['outside-zone-or-snap-radius']+=1;continue
                        if key in seen:rejects['duplicate-snapped-position']+=1;continue
                        seen.add(key);accepted.append({'zoneId':anchor['zoneId'],'coordinate':coordinate,'snapDistanceMeters':p['distance']})
            modes[mode]=accepted;counts[mode]={'acceptedByZone':dict(Counter(x['zoneId'] for x in accepted)),'rejected':dict(rejects)};print(mode,counts[mode],flush=True)
    write_json(path,{'schemaVersion':'connected-snapped-anchors/v1','identity':identity(),'sourceSha256':c['source']['sha256'],'extractSha256':next(iter(routing.values()))['extractSha256'],'boundaryVersion':c['boundaryVersion'],'routingIdentities':routing,'modes':modes,'quality':counts,'provenance':'OSM road vertices spatially stratified across cells then nearest on independent local mode graph; duplicates removed'})
    write_json(folder/'manifest.json',{'identity':identity(),'source_sha256':c['source']['sha256'],'extract_sha256':next(iter(routing.values()))['extractSha256'],'artifact_sha256':{name:sha256(folder/name) for name in ('road-candidates.json','snapped-anchors.json')}})
    incomplete.unlink()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skip-synthetic',action='store_true');p.add_argument('--snap-anchors',action='store_true');p.add_argument('--prepare-synthetic',action='store_true');a=p.parse_args()
    with heavy_lock():
        if a.prepare_synthetic:prepare_synthetic()
        elif a.snap_anchors:snap_anchors()
        else:validate(a.skip_synthetic)
