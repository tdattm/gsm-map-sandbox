import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/lib/api'
import { allocationTotals, regionalIds, syntheticAllocation, validateRegionalResult, validateRegionalSnapshot, type RegionalSnapshot } from '../src/lib/regional-simulation'
import { useRegionalSimulation } from '../src/lib/use-regional-simulation'
import { fixtureSnapshot } from '../src/lib/simulation'
vi.mock('../src/lib/api',async original=>({...await original<typeof import('../src/lib/api')>(),api:vi.fn()}))
const mocked = vi.mocked(api)
const config = {schemaVersion:'gsm-nvmr-regional-scenario/v1' as const,seed:'test',horizonSeconds:900,maxWaitSeconds:300,regions:syntheticAllocation()}
function projection(time=0): RegionalSnapshot {
  const regions = regionalIds.map(id=>{
    const s = fixtureSnapshot(100,time)
    s.vehicles=s.vehicles.slice(0,10)
    s.runId='run';s.regionId=id
    for (const mode of ['CAR','MOTORBIKE'] as const) s.routingIdentities[mode]={...s.routingIdentities[mode],regionId:id,profile:mode==='CAR'?'car':'motorbike',algorithm:'mld'}
    for (const v of s.vehicles) {v.id=`${id}:${v.id}`;v.serviceState='IDLE';v.activeBookingId=null;v.routeRef=null}
    s.counts={total:10,online:10,offline:0,idle:10,assigned:0,onTrip:0,moving:0}
    return s
  })
  return {schemaVersion:'gsm-nvmr-regional-snapshot/v1',runId:'run',simulationTimeSeconds:time,sequenceNumber:Math.floor(time*1e6),regions,
    counts:{total:20,online:20,offline:0,idle:20,assigned:0,onTrip:0,moving:0},vehicles:regions.flatMap(r=>r.vehicles.map(v=>({...v,regionId:r.regionId})))}
}
const summary = ()=>({schemaVersion:'gsm-nvmr-regional-result/v1' as const,runId:'run',config,simulationDurationSeconds:120,
  counts:{requested:0,assigned:0,completed:0,unserved:0},regions:regionalIds.map(regionId=>({schemaVersion:'gsm-simulation-result/v1' as const,runId:'run',regionId,config:config.regions.find(r=>r.regionId===regionId)!,simulationDurationSeconds:120,counts:{requested:0,assigned:0,completed:0,unserved:0}}))})
afterEach(()=>{mocked.mockReset();vi.useRealTimers()})

describe('Regional boundary and playback',()=>{
  it('sums allocation across regions and labels an explicit small synthetic preset',()=>{
    expect(allocationTotals(syntheticAllocation())).toEqual({fleetSize:20,carCount:10,motorbikeCount:10,bookingCount:24})
  })
  it('rejects wrong clock, counts, duplicate region and wrong graph or namespace',()=>{
    expect(validateRegionalSnapshot(projection(),'run').counts.total).toBe(20)
    const mutations = [
      (s:RegionalSnapshot)=>s.counts.total++,
      (s:RegionalSnapshot)=>s.regions[0].simulationTimeSeconds++,
      (s:RegionalSnapshot)=>{s.regions[0].regionId=s.regions[1].regionId},
      (s:RegionalSnapshot)=>{s.regions[0].routingIdentities.CAR.regionId=s.regions[1].regionId},
      (s:RegionalSnapshot)=>{s.regions[0].vehicles[0].id='unscoped'},
    ]
    for (const mutate of mutations) {const s=projection();mutate(s);expect(()=>validateRegionalSnapshot(s,'run')).toThrow()}
    const bad=summary();bad.counts.requested=1;expect(()=>validateRegionalResult(bad,'run')).toThrow()
  })
  it('uses one paused clock, keeps the run while drilling down, and seeks without resetting duration/time',async()=>{
    vi.useFakeTimers()
    mocked.mockImplementation((path,options)=>{
      if (path==='/api/regions') return Promise.resolve({regions:[]})
      if (options?.method==='POST') return Promise.resolve({id:'run',status:'COMPLETED',progress:1})
      if (path.includes('/result')) return Promise.resolve(summary())
      return Promise.resolve(projection(Number(new URL(path,'http://local').searchParams.get('timeSeconds'))))
    })
    const {result,unmount}=renderHook(()=>useRegionalSimulation('meeting'))
    await act(()=>result.current.create(config))
    await act(()=>vi.advanceTimersByTimeAsync(1000))
    expect(result.current.snapshot?.counts.total).toBe(20)
    expect(mocked.mock.calls.filter(([p])=>p.includes('/snapshot'))).toHaveLength(1)
    act(()=>result.current.selectRegion(regionalIds[1]))
    expect(result.current.regionalSnapshot?.regionId).toBe(regionalIds[1])
    expect(result.current.result?.runId).toBe('run')
    act(()=>result.current.seek(50))
    await act(()=>vi.advanceTimersByTimeAsync(1000))
    expect(result.current.snapshot?.simulationTimeSeconds).toBe(50)
    expect(result.current.clock.getSnapshot().simulationTimeSeconds).toBe(50)
    expect(mocked.mock.calls.filter(([p])=>p.includes('/snapshot'))).toHaveLength(2)
    act(()=>result.current.retry())
    await act(()=>vi.advanceTimersByTimeAsync(1000))
    expect(result.current.clock.getSnapshot().simulationTimeSeconds).toBe(50)
    expect(result.current.snapshot?.simulationTimeSeconds).toBe(50)
    const id=result.current.snapshot!.regions[0].vehicles[0].id
    act(()=>result.current.selectVehicle(id))
    expect(result.current.regionId).toBe(regionalIds[0]);expect(result.current.selectedId).toBe(id)
    unmount()
  })
  it('rejects late snapshots after seek and accepts the replacement projection',async()=>{
    vi.useFakeTimers()
    let resolveOld!:(value:RegionalSnapshot)=>void
    const old=new Promise<RegionalSnapshot>(r=>{resolveOld=r})
    mocked.mockImplementation((path,options)=>{
      if(path==='/api/regions')return Promise.resolve({regions:[]})
      if(options?.method==='POST')return Promise.resolve({id:'run',status:'COMPLETED',progress:1})
      if(path.includes('/result'))return Promise.resolve(summary())
      const time=Number(new URL(path,'http://local').searchParams.get('timeSeconds'))
      return time===0?old:Promise.resolve(projection(time))
    })
    const {result,unmount}=renderHook(()=>useRegionalSimulation('standard'))
    await act(()=>result.current.create(config))
    act(()=>result.current.seek(40))
    await act(()=>vi.advanceTimersByTimeAsync(1000))
    await act(async()=>resolveOld(projection(0)))
    expect(result.current.snapshot?.simulationTimeSeconds).toBe(40)
    unmount()
  })
  it('deduplicates POST and ignores a late response after reset',async()=>{
    let resolve!:(value:unknown)=>void
    mocked.mockImplementation((path)=>path==='/api/regions'?Promise.resolve({regions:[]}):new Promise(r=>{resolve=r}))
    const {result,unmount}=renderHook(()=>useRegionalSimulation('standard'))
    let pending!:Promise<void>
    act(()=>{pending=result.current.create(config);void result.current.create(config)})
    expect(mocked.mock.calls.filter(([,o])=>o?.method==='POST')).toHaveLength(1)
    act(()=>result.current.reset())
    await act(async()=>{resolve({id:'old',status:'COMPLETED',progress:1});await pending})
    expect(result.current.job).toBeNull();unmount()
  })
  it('does not resurrect a completed response racing cancellation',async()=>{
    let resolve!:(value:unknown)=>void
    mocked.mockImplementation((path,options)=>{
      if(path==='/api/regions')return Promise.resolve({regions:[]})
      if(path.endsWith('/cancel'))return Promise.resolve({id:'run',status:'CANCELLED',progress:0})
      if(options?.method==='POST')return Promise.resolve({id:'run',status:'RUNNING',progress:0})
      return new Promise(r=>{resolve=r})
    })
    const {result,unmount}=renderHook(()=>useRegionalSimulation('standard'))
    await act(()=>result.current.create(config))
    await act(()=>result.current.cancel())
    await act(async()=>resolve({id:'run',status:'COMPLETED',progress:1}))
    expect(result.current.job?.status).toBe('CANCELLED');expect(result.current.result).toBeNull();unmount()
  })
})
