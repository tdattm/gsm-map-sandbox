"""Independent generated OSM oracle plus real source-tag/node checks. No public router."""
import json
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.config import Settings
from backend.app.regions import default_registry
from backend.app.modes import resolve_mode
from backend.app.integrity import digest
from scripts.pipeline import execute, image_lock, write_json, Osmium


def synthetic(output):
    profile_hash=digest(ROOT/'profiles/motorbike.lua')
    folder=ROOT/'build/m2'/('synthetic-'+profile_hash[:12]); folder.mkdir(parents=True,exist_ok=True)
    osm=ET.Element('osm',version='0.6',generator='gsm-independent-profile-tests')
    cases=[]; next_id=1
    def node(x,y,tags=None):
        nonlocal next_id
        i=next_id;next_id+=1
        n=ET.SubElement(osm,'node',id=str(i),lon=str(x),lat=str(y),version='1')
        for k,v in (tags or {}).items():ET.SubElement(n,'tag',k=k,v=v)
        return i
    def way(refs,tags):
        nonlocal next_id
        i=next_id;next_id+=1
        w=ET.SubElement(osm,'way',id=str(i),version='1')
        for ref in refs:ET.SubElement(w,'nd',ref=str(ref))
        for k,v in tags.items():ET.SubElement(w,'tag',k=k,v=v)
        return i
    specifications=[
        ('ordinary',{},True,True),('motorcycle-no',{'motorcycle':'no'},False,True),
        ('hierarchy',{'access':'no','motor_vehicle':'no','motorcycle':'yes'},True,False),
        ('vehicle-no',{'vehicle':'no'},False,False),('motor-vehicle-no',{'motor_vehicle':'no'},False,False),
        ('private',{'access':'private'},False,True),('ambiguous',{'access':'unknown'},False,True),
        ('conditional',{'motorcycle:conditional':'no @ (08:00-10:00)'},False,True),
        ('motorway',{'highway':'motorway'},False,True),('motorroad',{'motorroad':'yes'},False,True),
        ('moped-not-motorcycle',{'moped':'no'},True,True),
        ('explicit-path',{'highway':'path','motorcycle':'yes','motorcar':'no'},True,False),
        ('untagged-path',{'highway':'path'},False,False),
        ('oneway',{'oneway':'yes'},True,True),
        ('oneway-exception',{'oneway':'yes','oneway:motorcycle':'no'},True,True),
        ('reverse-oneway',{'oneway':'-1'},True,True),
        ('bridge',{'bridge':'yes'},True,True),('tunnel',{'tunnel':'yes'},True,True)]
    for index,(name,tags,motor,car) in enumerate(specifications):
        x=105+index*.01;y=20
        refs=[node(x,y),node(x+.001,y),node(x+.002,y)]
        way(refs,{'highway':'residential',**tags})
        cases.append(dict(name=name,start=[x+.0002,y],end=[x+.0018,y],motor=motor,car=car,
                          reverseMotor=name not in ('oneway',),reverseCar=name not in ('oneway','oneway-exception'),tags=tags))
    # Barrier corridor with allowed stubs either side; cannot route through middle node.
    for offset,barrier in enumerate(['bollard','gate','no']):
        x=105+(.20+offset*.01);y=20
        refs=[node(x,y),node(x+.001,y,{'barrier':barrier}),node(x+.002,y)]
        way(refs,{'highway':'residential'})
        cases.append(dict(name='barrier-'+barrier,start=[x+.0002,y],end=[x+.0018,y],motor=barrier=='no',car=barrier!='bollard',tags={'barrier':barrier}))
    # Explicit from/via/to turn relation with deterministic detour.
    x=105.25;y=20
    a,b,c,d=[node(*p) for p in [(x,y),(x+.001,y),(x+.002,y),(x+.001,y+.001)]]
    w1=way([a,b],{'highway':'residential'});w2=way([b,c],{'highway':'residential'})
    way([b,d,c],{'highway':'residential'})
    rel=ET.SubElement(osm,'relation',id='9999',version='1')
    for typ,ref,role in [('way',w1,'from'),('node',b,'via'),('way',w2,'to')]:ET.SubElement(rel,'member',type=typ,ref=str(ref),role=role)
    for k,v in {'type':'restriction','restriction':'no_straight_on'}.items():ET.SubElement(rel,'tag',k=k,v=v)
    cases.append(dict(name='turn-restriction',start=[x+.0002,y],end=[x+.0018,y],motor=True,car=True,tags={'restriction':'no_straight_on'},mustPassNode=d))
    for i,(name,restriction,exception) in enumerate([
        ('mode-turn','restriction:motorcycle',None),('except-motorcycle','restriction','motorcycle')]):
        x=105.27+i*.01
        a,b,c,d=[node(*p) for p in [(x,y),(x+.001,y),(x+.002,y),(x+.001,y+.001)]]
        w1=way([a,b],{'highway':'residential'});w2=way([b,c],{'highway':'residential'})
        way([b,d,c],{'highway':'residential'})
        rel=ET.SubElement(osm,'relation',id=str(10000+i),version='1')
        for typ,ref,role in [('way',w1,'from'),('node',b,'via'),('way',w2,'to')]:ET.SubElement(rel,'member',type=typ,ref=str(ref),role=role)
        tags={'type':'restriction',restriction:'no_straight_on'}
        if exception:tags['except']=exception
        for k,v in tags.items():ET.SubElement(rel,'tag',k=k,v=v)
        cases.append(dict(name=name,start=[x+.0002,y],end=[x+.0018,y],motor=True,car=True,tags=tags,turnNode=d))
    # Separate tiny components: origin in ordinary case, destination in bridge case.
    cases.append(dict(name='disconnected',start=cases[0]['start'],end=cases[16]['end'],motor=False,car=False,tags={}))
    cases.append(dict(name='max-snap',start=[104,19],end=cases[0]['end'],motor=False,car=False,tags={}))
    source=folder/'network.osm';ET.ElementTree(osm).write(source,encoding='utf-8',xml_declaration=True)
    image=image_lock(Settings().osrm_image,False)
    result=[]
    for mode in ('car','motorbike'):
        target=folder/mode;target.mkdir(exist_ok=True)
        import shutil
        shutil.copyfile(source,target/'network.osm')
        base=['docker','run','--rm','--mount',f'type=bind,source={target},target=/data',
              '--mount',f'type=bind,source={ROOT / "profiles"},target=/profiles,readonly',image]
        for tool,params in [('osrm-extract',['-p','/opt/car.lua' if mode=='car' else '/profiles/motorbike.lua','/data/network.osm']),
                            ('osrm-partition',['/data/network.osrm']),('osrm-customize',['/data/network.osrm'])]:
            execute(base+[tool,*params])
        name='gsm-m2-validation-'+uuid.uuid4().hex[:10]
        execute(['docker','run','--rm','--detach','--name',name,'-p','127.0.0.1::5000',
            '--mount',f'type=bind,source={target},target=/data,readonly',image,'osrm-routed','--algorithm','mld','/data/network.osrm'])
        try:
            port=json.loads(execute(['docker','inspect',name],capture=True))[0]['NetworkSettings']['Ports']['5000/tcp'][0]['HostPort']
            url=f'http://127.0.0.1:{port}'
            with httpx.Client(trust_env=False,timeout=5) as client:
                for attempt in range(30):
                    try:client.get(url+'/nearest/v1/driving/105,20').raise_for_status();break
                    except httpx.HTTPError:time.sleep(.2)
                for case in cases:
                    for reverse in [False,True] if case['name'] in ('oneway','oneway-exception','reverse-oneway') else [False]:
                        points=[case['start'],case['end']]
                        if reverse:points.reverse()
                        expected=case['motor' if mode=='motorbike' else 'car']
                        if case['name']=='reverse-oneway':expected=reverse
                        elif reverse:expected=case['reverseMotor' if mode=='motorbike' else 'reverseCar']
                        coords=';'.join(','.join(map(str,p)) for p in points)
                        raw=client.get(url+'/route/v1/driving/'+coords,params={'radiuses':'1;1','annotations':'nodes','overview':'full','geometries':'geojson'}).json()
                        passed=(raw['code']=='Ok')==expected
                        if passed and expected and 'mustPassNode' in case:
                            passed=case['mustPassNode'] in raw['routes'][0]['legs'][0]['annotation']['nodes']
                        if passed and expected and 'turnNode' in case:
                            detour=case['turnNode'] in raw['routes'][0]['legs'][0]['annotation']['nodes']
                            passed=detour == ((mode=='motorbike') == (case['name']=='mode-turn'))
                        result.append(dict(case=case['name'],mode=mode,reverse=reverse,expectedRoutable=expected,
                            tags=case['tags'],status='PASS' if passed else 'FAIL',response=raw))
        finally:execute(['docker','stop',name])
    evidence={'status':'PASS' if all(c['status']=='PASS' for c in result) else 'FAIL','profile_sha256':profile_hash,
        'source_sha256':digest(source),'cases':result}
    write_json(output/'synthetic-validation.json',evidence)
    assert evidence['status']=='PASS',[(c['case'],c['mode'],c['reverse']) for c in result if c['status']=='FAIL']
    return evidence


def real_cases(c,output):
    ids=['28924657','35978226','9656730']  # Explicit motorcycle-only alley, prohibited expressway, shared bridge.
    raw=Osmium(Settings(),False).run(['getid',c.extracted_path,*('w'+x for x in ids),'-r','-f','osm'],capture=True)
    (output/'source-mode-ways.xml').write_text(raw,encoding='utf-8')
    tree=ET.fromstring(raw)
    nodes={int(n.attrib['id']):[float(n.attrib['lon']),float(n.attrib['lat'])] for n in tree.findall('node')}
    records=[]
    for way in tree.findall('way'):
        if way.attrib['id'] not in ids:continue
        tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
        refs=[int(n.attrib['ref']) for n in way.findall('nd')]
        a,b=max(zip(refs,refs[1:]),key=lambda p:sum((x-y)**2 for x,y in zip(nodes[p[0]],nodes[p[1]])))
        start=[x*.8+y*.2 for x,y in zip(nodes[a],nodes[b])]
        end=[x*.2+y*.8 for x,y in zip(nodes[a],nodes[b])]
        for mode,port in [('CAR',5001),('MOTORBIKE',5002)]:
            expected= tags.get('motorcar')!='no' if mode=='CAR' else tags.get('motorcycle')!='no' and tags.get('highway')!='motorway'
            coords=';'.join(','.join(map(str,p)) for p in [start,end])
            with httpx.Client(trust_env=False,timeout=10) as client:
                route=client.get(f'http://127.0.0.1:{port}/route/v1/driving/{coords}',params={'radiuses':'1;1','overview':'full','geometries':'geojson','annotations':'nodes'}).json()
                nearest=client.get(f'http://127.0.0.1:{port}/nearest/v1/driving/{start[0]},{start[1]}',params={'radiuses':'1'}).json()
                table=client.get(f'http://127.0.0.1:{port}/table/v1/driving/{coords}',params={'radiuses':'1;1','sources':'0','destinations':'1'}).json()
            edge=(a,b)
            route_nodes=route['routes'][0]['legs'][0]['annotation']['nodes'] if route['code']=='Ok' else []
            uses=edge in set(zip(route_nodes,route_nodes[1:]))
            if expected:
                # Nearest node IDs may describe a compressed edge's adjacent nodes.
                # Instead compare every full geometry point against this independently
                # selected straight source segment (endpoints are 20/80% along it).
                import math
                origin,finish=nodes[a],nodes[b]
                scale=math.cos(math.radians(origin[1]))
                dx,dy=(finish[0]-origin[0])*scale,finish[1]-origin[1]
                def source_distance(p):
                    px,py=(p[0]-origin[0])*scale,p[1]-origin[1]
                    t=max(0,min(1,(px*dx+py*dy)/(dx*dx+dy*dy)))
                    return math.hypot(px-t*dx,py-t*dy)*111200
                passed=route['code']=='Ok' and nearest['code']=='Ok' and table['code']=='Ok'
                if passed:
                    passed=(abs(table['durations'][0][0]-route['routes'][0]['duration'])<1
                            and all(source_distance(p)<1 for p in route['routes'][0]['geometry']['coordinates']))
            else:
                near_nodes=nearest['waypoints'][0].get('nodes',[]) if nearest['code']=='Ok' else []
                passed=not uses and set(near_nodes)!=set(edge)
            records.append(dict(osmWay=way.attrib['id'],tags=tags,sourceEdge=edge,mode=mode,expectedAllowed=expected,
                status='PASS' if passed else 'FAIL',start=start,end=end,route=route,nearest=nearest,table=table))
    evidence={'status':'PASS' if all(r['status']=='PASS' for r in records) and len(records)==6 else 'FAIL',
        'source_sha256':digest(c.extracted_path),'cases':records,
        'unknown':['Current physical signs','Conditional/via-way restrictions outside fixtures','Traffic ETA calibration']}
    write_json(output/'real-mode-cases.json',evidence)
    assert evidence['status']=='PASS',[(r['osmWay'],r['mode']) for r in records if r['status']=='FAIL']
    return evidence


def main():
    output=ROOT/'docs/nvmr/m2-evidence';output.mkdir(exist_ok=True)
    c=resolve_mode(default_registry(Settings()),'nvmr-hanoi-core','MOTORBIKE')
    pending=c.routing_dir/'.validation-incomplete'
    pending.write_text('Independent routing validation in progress; fail closed')
    synthetic(output)
    from scripts.hanoi_pilot import audit_oneway_nodes
    audit_oneway_nodes(c,output)
    real_cases(c,output)
    write_json(c.routing_dir/'validation.json',{'status':'PASS','manifest_sha256':digest(c.routing_dir/'manifest.json'),
        'validator_sha256':digest(Path(__file__)),
        'synthetic_sha256':digest(output/'synthetic-validation.json'),'real_oneway_sha256':digest(output/'osm-oneway-nodes.json'),
        'directed_cases_sha256':digest(output/'real-mode-cases.json'),
        'scope':'static source-tag pilot; conditional restrictions, physical signage and ETA calibration UNKNOWN'})
    pending.unlink()
    print('PASS MOTORBIKE validation')


if __name__=='__main__':main()
