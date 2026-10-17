"""Opt-in live directed bridge/one-way and short-leg projection checks.

Uses existing M2 case coordinates/OSM tags, validated local mode contexts, and
immutable M3 result geometry. Writes only a new evidence namespace, no graphs.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.simulation import SimulationConfig, VehicleInput, BookingInput, simulate
from backend.app.simulation_worker import live_travels
from backend.app.schemas import RouteResponse
from scripts.audit_route_fidelity import audit, arc


async def run(output):
    source=ROOT/'docs/nvmr/m2-evidence/real-mode-cases.json'
    cases=json.loads(source.read_text(encoding='utf-8'))['cases']
    reports=[]
    for mode in ('CAR','MOTORBIKE'):
        case=next(c for c in cases if c['mode']==mode and c.get('expectedAllowed') and
                  c.get('tags',{}).get('bridge')=='yes' and c['tags'].get('oneway')=='yes')
        config=SimulationConfig(fleetSize=1,carCount=int(mode=='CAR'),bookingCount=2,
            horizonSeconds=7200,maxWaitSeconds=3600,onlineFraction=1.,seed=f's0-s1-directed-{mode}')
        async with live_travels(config) as (_,identities,travels,_):
            pinned=travels[mode]
            class DirectedProbe:
                # M2's bridge case is inside the routing buffer, outside the M3
                # operating box. Query the verified router directly ONLY in this
                # diagnostic adapter; do not expand runtime coverage or claim this
                # is an accepted M3 job. Table has one explicit candidate here.
                async def route(self,a,b):
                    data=await pinned.service('route',[a,b],{'geometries':'geojson','overview':'full','steps':'false'})
                    raw=data['routes'][0]
                    return RouteResponse(coordinates=raw['geometry']['coordinates'],distance=raw['distance'],
                        duration=raw['duration'],snap_points=data['waypoints'])
                async def table(self,positions,pickup):
                    return [0 if tuple(p)==tuple(pickup) else (await self.route(p,pickup)).duration for p in positions]
            travel=DirectedProbe()
            probe_travels={mode:travel}
            # Reverse pickup on the one-way network followed by forward bridge trip.
            verified=await travel.route(case['start'],case['end'])
            start,end=verified.coordinates[0],verified.coordinates[-1]
            initial=[VehicleInput(id='directed-'+mode,vehicleType=mode,position=end)]
            demand=[BookingInput(id='bridge-forward',serviceType=mode,requestTimeSeconds=1,pickup=start,dropoff=end),
                    BookingInput(id='bridge-reverse',serviceType=mode,requestTimeSeconds=5000,pickup=end,dropoff=start)]
            result=await simulate(config,initial,demand,probe_travels,identities,f's0-s1-directed-{mode}')
            assert result['counts']['completed']==2
            report=audit(result,10)
            forward=result['routes'][result['assignments'][0]['tripRouteRef']]
            backward=result['routes'][result['assignments'][1]['tripRouteRef']]
            assert forward['coordinates']!=list(reversed(backward['coordinates']))
            # Select the shortest distinct adjacent full-geometry vertex pair, then
            # route it independently. A truly zero snapped route is fail-closed.
            edges=sorted((arc(a,b),a,b) for a,b in zip(forward['coordinates'],forward['coordinates'][1:]) if a!=b)
            _,a,b=edges[0]
            # Query nearby points on the same bridge segment for a short real leg.
            short_end=[a[i]+(b[i]-a[i])*.002 for i in (0,1)]
            short=await travel.route(a,short_end)
            short_config=config.model_copy(update={'bookingCount':1,'horizonSeconds':60})
            short_result=await simulate(short_config,[initial[0].model_copy(update={'position':tuple(short.coordinates[0])})],
                [BookingInput(id='short',serviceType=mode,requestTimeSeconds=1,pickup=short.coordinates[0],dropoff=short.coordinates[-1])],probe_travels,identities,f's0-s1-short-{mode}')
            short_report=audit(short_result,10)
            report.update(osmWay=case['osmWay'],osmTags=case['tags'],sourceEvidence=str(source.relative_to(ROOT)),
                diagnosticScope='Standalone directed OSRM projection probe in routing buffer, NOT an accepted M3 job. Runtime operating_bbox remains unchanged.',
                initialRuntimeRejection='INVALID_INITIAL_SNAP: bridge endpoints outside operating_bbox; kept fail-closed; no tolerance widened',
                reverseGeometryDiffers=True,forwardDistance=forward['distance'],reverseDistance=backward['distance'],
                shortLegDistanceMeters=short.distance,shortLegDurationSeconds=short.duration,shortAudit=short_report)
            report.update(shortPassed=short_report['passed'],shortSamples=short_report['samples'],shortMaxDeviationMeters=short_report['maxDeviationMeters'])
            output.mkdir(parents=True,exist_ok=True)
            (output/f'directed-{mode.lower()}-result.json').write_text(json.dumps(result),encoding='utf-8')
            (output/f'directed-{mode.lower()}-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            assert report['passed'] and short_report['passed']
            reports.append({k:v for k,v in report.items() if k not in ('rows','transitions','shortAudit','osmTags','sampledRoutes')})
    return reports


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/s0-s1/directed')
    args=parser.parse_args()
    summary=asyncio.run(run(args.output))
    path=ROOT/'docs/nvmr/s0-s1-evidence/directed-live-summary.json'
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True,indent=2))
