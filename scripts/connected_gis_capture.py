"""Copy compact provenance/evidence from ignored Connected artifacts for review."""
import json
import re
import shutil
import sqlite3
import platform
import importlib.metadata
from datetime import datetime,timezone
from pathlib import Path
from scripts.connected_gis import ROOT,base,config,identity,verify_graph,verify_render
from scripts.pipeline import sha256,write_json


def capture():
    out=ROOT/'docs/nvmr/r1b-evidence/gis';out.mkdir(parents=True,exist_ok=True)
    audit={'capturedUtc':datetime.now(timezone.utc).isoformat(),'identity':identity(),'source':config()['source'],'artifacts':{},'graphs':{},'render':{},'limitations':['Artifact hash verification is separate from OSRM HTTP/router proof and end-to-end simulation acceptance.']}
    paths=['coverage-evidence.json','source-verification.json','extracted/coverage.osm.metadata.json','render/manifest.json','render/features-manifest.json','render/software-provenance.json','render/osm-administrative-extents.json','anchors/manifest.json','validation/summary.json']
    for mode in ('CAR','MOTORBIKE'):
        folder=base()/'routing'/mode.lower()
        try:
            m=verify_graph(mode)
            audit['graphs'][mode]={'fileIntegrity':'PASS','manifestSha256':sha256(folder/'manifest.json'),'profileSha256':m['profile_sha256'],'sizeBytes':sum(m['artifact_sizes'].values()),'stages':[]}
            for stage in m['resources']:
                log=(folder/stage['log']).read_text(encoding='utf-8');ram=re.findall(r'RAM: peak bytes used: (\d+)',log)
                audit['graphs'][mode]['stages'].append({'stage':stage['stage'],'exitCode':stage['exitCode'],'wallSeconds':stage['resources']['wallSeconds'],'osrmReportedPeakBytes':int(ram[-1]) if ram else None,'hostMinimumPhysicalBytes':stage['resources']['minimumAvailablePhysicalBytes'],'hostMinimumCommitHeadroomBytes':stage['resources']['minimumCommitHeadroomBytes'],'dockerSamples':len(stage.get('dockerSamples',[]))})
        except (OSError,ValueError,KeyError,RuntimeError) as exc:audit['graphs'][mode]={'fileIntegrity':'NOT_VERIFIED','reason':str(exc)}
        paths.extend(f'routing/{mode.lower()}/{name}' for name in ('manifest.json','router-evidence.json','validation.json','routing-validation.json','synthetic-validation.json','build-resources.json'))
    try:
        m=verify_render();archive=base()/ 'render/tiles.mbtiles'
        audit['render']={'fileIntegrity':'PASS','archiveSha256':sha256(archive),'archiveSizeBytes':archive.stat().st_size,'tileCounts':m['tile_counts'],'features':m['features'],'resources':m['resources']}
        import shapely
        software={'python':platform.python_version(),'packages':{name:importlib.metadata.version(name) for name in ('osmium','shapely','mapbox-vector-tile','protobuf')},
            'geos':shapely.geos_version_string,'rendererSha256':sha256(ROOT/'scripts/connected_gis_render.py'),
            'requirementsSha256':sha256(ROOT/'scripts/requirements-connected-gis.txt'),'renderManifestSha256':sha256(base()/'render/manifest.json'),
            'note':'Captured after successful native stage; renderer source remained unchanged during that stage. Artifact checksum is the exact-output identity; rebuilding with different libraries may change encoded bytes.'}
        sidecar=base()/'render/software-provenance.json'
        if sidecar.exists():
            if json.loads(sidecar.read_text(encoding='utf-8'))!=software:raise RuntimeError('Render software provenance differs; refusing overwrite')
        else:write_json(sidecar,software)
    except (OSError,ValueError,KeyError,RuntimeError) as exc:audit['render']={'fileIntegrity':'NOT_VERIFIED','reason':str(exc)}
    try:
        from scripts.connected_overview_tiles import verify_overview
        overview=verify_overview()
        archive=base()/'render-overview/tiles.mbtiles'
        audit['overview']={'fileIntegrity':'PASS','archiveSha256':sha256(archive),
            'archiveSizeBytes':archive.stat().st_size,'tileCounts':overview['tile_counts'],
            'resources':overview['resources']}
        paths.append('render-overview/manifest.json')
    except (OSError,ValueError,KeyError,RuntimeError,sqlite3.Error) as exc:
        audit['overview']={'fileIntegrity':'NOT_VERIFIED','reason':str(exc)}
    for relative in paths:
        source=base()/relative
        if not source.exists():continue
        destination=out/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
        audit['artifacts'][relative]={'sha256':sha256(source),'sizeBytes':source.stat().st_size}
    write_json(out/'artifact-audit.json',audit)
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=='__main__':capture()
