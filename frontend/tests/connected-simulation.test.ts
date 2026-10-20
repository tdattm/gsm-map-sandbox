import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/lib/api'
import { connectedMapStyle } from '../src/lib/map-style'
import { allocateIntegers, allocationTotals, connectedMapSnapshot, defaultAllocations, filterConnectedSnapshot, validateConnectedSnapshot, validateConnectedResult, type ConnectedConfig, type ConnectedSnapshot } from '../src/lib/connected-simulation'
import { useConnectedSimulation } from '../src/lib/use-connected-simulation'
import { fixtureSnapshot } from '../src/lib/simulation'

vi.mock('../src/lib/api',async original=>({...await original<typeof import('../src/lib/api')>(),api:vi.fn()}))
const mocked=vi.mocked(api)
const config:ConnectedConfig={schemaVersion:'gsm-nvmr-connected-scenario/v1',seed:'test',fleetSize:100,carCount:40,bookingCount:0,horizonSeconds:900,maxWaitSeconds:300,onlineFraction:1,fleetAllocations:defaultAllocations(100),demandWeights:{hanoi:1,'bac-ninh':1,'hung-yen':1,'phu-tho':1,'thai-nguyen':1},demandCarFraction:.4,crossZoneDemandFraction:.25}
function projection(time=0):ConnectedSnapshot {
  const s=fixtureSnapshot(100,time)
  s.runId='run';s.regionId='nvmr-connected'
  for(const mode of ['CAR','MOTORBIKE'] as const)s.routingIdentities[mode]={...s.routingIdentities[mode],regionId:'nvmr-connected',profile:mode==='CAR'?'car':'motorbike',algorithm:'mld'}
  const vehicles=s.vehicles.map((v,i)=>({...v,id:`NVMR-${i}`,serviceState:'IDLE' as const,isMoving:false,homeZoneId:'hanoi',currentZoneId:i<80?'hanoi':'bac-ninh'}))
  const counts=(total:number)=>({total,online:total,offline:0,idle:total,assigned:0,onTrip:0,moving:0})
  return {...s,schemaVersion:'gsm-nvmr-connected-snapshot/v1',vehicles,counts:counts(100),zoneCounts:{hanoi:counts(80),'bac-ninh':counts(20)}}
}
const summary=()=>({schemaVersion:'gsm-nvmr-connected-result/v1' as const,runId:'run',regionId:'nvmr-connected',config,simulationDurationSeconds:120,counts:{requested:0,assigned:0,completed:0,unserved:0}})
afterEach(()=>{mocked.mockReset();vi.useRealTimers()})
describe('Connected global contracts and allocation',()=>{
  it('conserves every integer at each scale and gives exact 5000 default',()=>{
    expect(defaultAllocations()).toEqual([{zoneId:'hanoi',carCount:1600,motorbikeCount:2400},...['bac-ninh','hung-yen','phu-tho','thai-nguyen'].map(zoneId=>({zoneId,carCount:100,motorbikeCount:150}))])
    for(const size of [1,2,3,13,100,500,1000,5000]) expect(allocationTotals(defaultAllocations(size))).toEqual({fleetSize:size,carCount:Math.round(size*.4),motorbikeCount:size-Math.round(size*.4)})
    expect(allocateIntegers(3,[1,1,1,1,1])).toEqual([1,1,1,0,0])
    expect(()=>allocateIntegers(3,[0,0])).toThrow()
  })
  it('validates one global snapshot and rejects duplicate IDs, wrong graph, zones or conservation',()=>{
    expect(validateConnectedSnapshot(projection(),'run',100).vehicles).toHaveLength(100)
    const mutations=[(s:ConnectedSnapshot)=>{s.vehicles[1].id=s.vehicles[0].id},(s:ConnectedSnapshot)=>{s.routingIdentities.CAR.regionId='nvmr-hanoi-core'},(s:ConnectedSnapshot)=>{s.zoneCounts.hanoi.total--},(s:ConnectedSnapshot)=>{s.vehicles[0].homeZoneId='unverified'},(s:ConnectedSnapshot)=>{s.counts.total++}]
    for(const mutate of mutations){const s=projection();mutate(s);expect(()=>validateConnectedSnapshot(s,'run',100)).toThrow()}
    expect(()=>validateConnectedSnapshot(projection(),'run',5000)).toThrow('CONNECTED_FLEET_CONSERVATION')
    expect(connectedMapSnapshot(projection()).schemaVersion).toBe('gsm-simulation-snapshot/v1')
    expect(projection().schemaVersion).toBe('gsm-nvmr-connected-snapshot/v1')
  })
  it('filters only the display projection and preserves authoritative global state',()=>{
    const s=projection(),filtered=filterConnectedSnapshot(s,'bac-ninh','MOTORBIKE')!
    expect(filtered.vehicles).toHaveLength(20);expect(filtered.counts.total).toBe(20)
    expect(s.vehicles).toHaveLength(100);expect(s.counts.total).toBe(100)
    expect(validateConnectedSnapshot(s,'run').zoneCounts.hanoi.total).toBe(80)
  })
  it('preserves a 5000-vehicle global projection across zone/mode filters and outside-zone travel',()=>{
    // Contract fixture only: this does not certify a live OSRM or browser benchmark.
    const templates=fixtureSnapshot(5000,0).vehicles
    const counts=(total:number)=>({total,online:total,offline:0,idle:total,assigned:0,onTrip:0,moving:0})
    let index=0
    const vehicles=defaultAllocations().flatMap(row=>(['CAR','MOTORBIKE'] as const).flatMap(mode=>
      Array.from({length:mode==='CAR'?row.carCount:row.motorbikeCount},()=>{
        const i=index++
        return {...templates[i],id:`NVMR-${mode}-${row.zoneId}-${i}`,vehicleType:mode,serviceState:'IDLE' as const,
          isMoving:false,homeZoneId:row.zoneId,currentZoneId:row.zoneId}
      })))
    const snapshot:ConnectedSnapshot={...projection(),vehicles,counts:counts(5000),
      zoneCounts:Object.fromEntries(defaultAllocations().map(row=>[row.zoneId,counts(row.carCount+row.motorbikeCount)]))}
    expect(validateConnectedSnapshot(snapshot,'run',5000).vehicles).toHaveLength(5000)
    expect(new Set(vehicles.map(v=>v.id)).size).toBe(5000)
    expect(filterConnectedSnapshot(snapshot,'','CAR')?.counts.total).toBe(2000)
    expect(filterConnectedSnapshot(snapshot,'bac-ninh','MOTORBIKE')?.counts.total).toBe(150)
    snapshot.vehicles[0].currentZoneId='outside-operating-zones'
    snapshot.zoneCounts.hanoi=counts(3999)
    snapshot.zoneCounts['outside-operating-zones']=counts(1)
    expect(validateConnectedSnapshot(snapshot,'run',5000).counts.total).toBe(5000)
    expect(filterConnectedSnapshot(snapshot,'outside-operating-zones','')?.counts.total).toBe(1)
    expect(snapshot.vehicles.filter(v=>v.homeZoneId==='hanoi')).toHaveLength(4000)
  })
  it('rejects negative offsets, swapped zone categories and undeclared current zone or bucket',()=>{
    const mutations=[
      (s:ConnectedSnapshot)=>{s.zoneCounts.hanoi.offline=-1;s.zoneCounts['bac-ninh'].offline=1},
      (s:ConnectedSnapshot)=>{s.zoneCounts.hanoi.idle--;s.zoneCounts.hanoi.assigned++;s.zoneCounts['bac-ninh'].idle++;s.zoneCounts['bac-ninh'].assigned--},
      (s:ConnectedSnapshot)=>{s.zoneCounts.hanoi.total=20;s.zoneCounts['bac-ninh'].total=80},
      (s:ConnectedSnapshot)=>{s.vehicles[0].currentZoneId='unverified-province'},
      (s:ConnectedSnapshot)=>{s.zoneCounts['unverified-province']={...s.counts,total:0,online:0,idle:0}},
      (s:ConnectedSnapshot)=>{s.vehicles[0].isMoving=true},
    ]
    for(const mutate of mutations){const s=projection();mutate(s);expect(()=>validateConnectedSnapshot(s,'run')).toThrow()}
  })
  it('rejects results whose requested numerator cannot reconcile completed/unserved',()=>{
    expect(validateConnectedResult(summary(),'run').simulationDurationSeconds).toBe(120)
    const s=summary();s.counts.requested++;expect(()=>validateConnectedResult(s,'run')).toThrow()
  })
  it('uses one viewport MVT source with local fonts, correct layers and no region-wide GeoJSON',()=>{
    const style=connectedMapStyle(),source=style.sources['connected-basemap']
    expect(Object.keys(style.sources)).toHaveLength(1)
    expect(source.type).toBe('vector')
    if(source.type==='vector'){expect(source.tiles).toEqual(['/api/v5/connected/map/tiles/{z}/{x}/{y}.pbf']);expect(source.bounds).toEqual([104.35,20.06,107.25,22.85]);expect(source.minzoom).toBe(0);expect(source.maxzoom).toBe(13)}
    expect(style.layers.filter(l=>'source' in l).every(l=>'source-layer' in l)).toBe(true)
    // Legal attribution links are navigation, never tile/font resources.
    const {attribution,...localSource}=source
    expect(attribution).toContain('https://www.openstreetmap.org/copyright')
    expect(JSON.stringify({...style,sources:{'connected-basemap':localSource}})).not.toMatch(/https?:/)
  })
})
describe('Connected session concurrency and immutable playback',()=>{
  it('opens persisted global run, seeks one clock and selects a vehicle across zones',async()=>{
    vi.useFakeTimers()
    mocked.mockImplementation((path,options)=>{if(options?.method==='POST')return Promise.resolve({id:'run',status:'COMPLETED',progress:1});if(path.includes('/result'))return Promise.resolve(summary());return Promise.resolve(projection(Number(new URL(path,'http://local').searchParams.get('timeSeconds'))))})
    const {result,unmount}=renderHook(()=>useConnectedSimulation('meeting'))
    await act(()=>result.current.create(config));await act(()=>vi.advanceTimersByTimeAsync(1000))
    expect(result.current.snapshot?.counts.total).toBe(100)
    act(()=>result.current.selectVehicle('NVMR-90'));expect(result.current.vehicle?.currentZoneId).toBe('bac-ninh')
    act(()=>result.current.seek(50));await act(()=>vi.advanceTimersByTimeAsync(1000))
    expect(result.current.snapshot?.simulationTimeSeconds).toBe(50);expect(result.current.clock.getSnapshot().simulationTimeSeconds).toBe(50)
    expect(mocked.mock.calls.every(([p])=>p.startsWith('/api/v5/'))).toBe(true)
    expect(mocked.mock.calls.some(([p])=>p.includes('/route/v1/'))).toBe(false)
    unmount()
  })
  it('ignores snapshot response racing a seek',async()=>{
    vi.useFakeTimers();let resolve!:(value:ConnectedSnapshot)=>void;const old=new Promise<ConnectedSnapshot>(r=>{resolve=r})
    mocked.mockImplementation((path,options)=>{if(options?.method==='POST')return Promise.resolve({id:'run',status:'COMPLETED',progress:1});if(path.includes('/result'))return Promise.resolve(summary());const time=Number(new URL(path,'http://local').searchParams.get('timeSeconds'));return time===0?old:Promise.resolve(projection(time))})
    const {result,unmount}=renderHook(()=>useConnectedSimulation('standard'))
    await act(()=>result.current.create(config));act(()=>result.current.seek(40));await act(()=>vi.advanceTimersByTimeAsync(1000));await act(async()=>resolve(projection(0)))
    expect(result.current.snapshot?.simulationTimeSeconds).toBe(40);unmount()
  })
  it('deduplicates create and ignores a late result after reset',async()=>{
    let resolve!:(value:unknown)=>void;mocked.mockImplementation(()=>new Promise(r=>{resolve=r}))
    const {result,unmount}=renderHook(()=>useConnectedSimulation('standard'));let pending!:Promise<void>
    act(()=>{pending=result.current.create(config);void result.current.create(config)})
    expect(mocked).toHaveBeenCalledTimes(1);act(()=>result.current.reset());await act(async()=>{resolve({id:'old',status:'COMPLETED',progress:1});await pending})
    expect(result.current.job).toBeNull();unmount()
  })
  it('does not resurrect completed job response after cancellation',async()=>{
    let resolve!:(value:unknown)=>void
    mocked.mockImplementation((path,options)=>{if(path.endsWith('/cancel'))return Promise.resolve({id:'run',status:'CANCELLED',progress:0});if(options?.method==='POST')return Promise.resolve({id:'run',status:'RUNNING',progress:0});return new Promise(r=>{resolve=r})})
    const {result,unmount}=renderHook(()=>useConnectedSimulation('standard'));await act(()=>result.current.create(config));await act(()=>result.current.cancel());await act(async()=>resolve({id:'run',status:'COMPLETED',progress:1}))
    expect(result.current.job?.status).toBe('CANCELLED');expect(result.current.result).toBeNull();unmount()
  })
})
