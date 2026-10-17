import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { modeRoute, prepareModeFleet, typesFor, useModes, validateMixed, type MixedPlan, type RoutingIdentity } from '../src/lib/multimodal'
import { useBooking } from '../src/lib/use-booking'
import { useFleet } from '../src/lib/use-fleet'
import recorded from '../../docs/nvmr/m2-evidence/mixed-plan.json'
import type { Coordinate, Route } from '../src/lib/api'
import { webcrypto } from 'node:crypto'

const region='nvmr-hanoi-core'
const response=(r:unknown)=>({ok:true,json:async()=>r})
const identity=(mode:'CAR'|'MOTORBIKE')=>recorded.routingIdentities[mode] as RoutingIdentity
describe('M2 explicit mode contracts',()=>{
  it('pins mode and graph in route responses and rejects CAR substitution',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>response({schemaVersion:'gsm-mode-route/v1',routingIdentity:identity('CAR'),route:{}})))
    await expect(modeRoute(region,'MOTORBIKE',[105.84,21.03],[105.85,21.03],new AbortController().signal)).rejects.toThrow('MODE_RESPONSE_MISMATCH')
    vi.stubGlobal('fetch',vi.fn(async()=>response({schemaVersion:'gsm-mode-route/v1',routingIdentity:identity('MOTORBIKE'),route:{}})))
    await expect(modeRoute(region,'MOTORBIKE',[105.84,21.03],[105.85,21.03],new AbortController().signal,{...identity('MOTORBIKE'),graphManifestSha256:'old'})).rejects.toThrow('MODE_RESPONSE_MISMATCH')
  })
  it('validates typed assignments, candidate compatibility and history',()=>{
    const raw=structuredClone(recorded) as unknown as MixedPlan
    expect(validateMixed(raw,region).assignments).toHaveLength(20)
    raw.plan.vehicles[0].vehicleType='MOTORBIKE'
    expect(()=>validateMixed(raw,region)).toThrow('VEHICLE_CONFIG_MISMATCH')
    raw.config.vehicleTypes[0]='MOTORBIKE'
    expect(()=>validateMixed(raw,region)).toThrow('CROSS_MODE')
    expect(()=>validateMixed(recorded as unknown as MixedPlan,region,{...recorded.config,vehicleTypes:['MOTORBIKE']} as never)).toThrow('MODE_RESPONSE_MISMATCH')
  })
  it('sends a mixed fleet/request set to the versioned adapter and keeps one clock',async()=>{
    const fetcher=vi.fn(async()=>response(recorded));vi.stubGlobal('fetch',fetcher)
    const {result,rerender}=renderHook(({mix})=>useBooking(true,true,region,mix),{initialProps:{mix:'MIXED' as 'MIXED'|'CAR'}})
    const clock=result.current.clock
    await act(async()=>result.current.generate(recorded.plan.config))
    expect(result.current.plan?.vehicles.filter(v=>v.vehicleType==='MOTORBIKE')).toHaveLength(5)
    const [url,options]=fetcher.mock.calls[0] as unknown as [string,RequestInit]
    expect(url).toBe(`/api/v2/regions/${region}/booking-simulation/prepare`)
    expect(JSON.parse(options.body as string).vehicleTypes).toEqual(typesFor('MIXED',10))
    rerender({mix:'CAR'});expect(result.current.plan).toBeNull();expect(result.current.multimodal).toBeNull();expect(result.current.clock).toBe(clock)
  })
  it('aborts a slow preparation on mode switch and ignores a late result',async()=>{
    let finish!:(value:unknown)=>void,signal!:AbortSignal
    vi.stubGlobal('fetch',vi.fn((_url:string,options:RequestInit)=>{signal=options.signal as AbortSignal;return new Promise(resolve=>{finish=resolve})}))
    const {result,rerender}=renderHook(({mix})=>useBooking(true,true,region,mix),{initialProps:{mix:'MIXED' as 'MIXED'|'CAR'}})
    let work!:Promise<void>;act(()=>{work=result.current.generate(recorded.plan.config)})
    rerender({mix:'CAR'});expect(signal.aborted).toBe(true)
    await act(async()=>{finish(response(recorded));await work})
    expect(result.current.plan).toBeNull()
  })
  it('discards mode metadata when the selected region changes',async()=>{
    let finish!:(value:unknown)=>void,signal!:AbortSignal
    vi.stubGlobal('fetch',vi.fn((_url:string,options:RequestInit)=>{signal=options.signal as AbortSignal;return new Promise(resolve=>{finish=resolve})}))
    const {result,rerender}=renderHook(({id})=>useModes(id,false,0),{initialProps:{id:region}})
    rerender({id:'hcm-center'});expect(signal.aborted).toBe(true)
    await act(async()=>finish(response({regionId:region,modes:[{vehicleType:'MOTORBIKE',ready:true}]})))
    expect(result.current).toEqual([])
  })
  it('prepares one mixed fleet with isolated caches and stable playback clock',async()=>{
    vi.stubGlobal('crypto',webcrypto)
    const fetcher=vi.fn(async(url:string,options?:RequestInit)=>{
      const mode=url.includes('/MOTORBIKE/')?'MOTORBIKE':'CAR'
      if(url.endsWith('/candidates'))return response({candidates:Array.from({length:6},(_,i)=>({id:`a-${i}`,coordinate:[105.83+i*.001,21.03]})),datasetFingerprint:`fixture-${mode}`,
        routingSource:'fixture',provenance:{region_id:region,vehicle_type:mode,routingIdentity:identity(mode),display_bbox:[105.8,21,105.9,21.1],max_snap_meters:100}})
      const {start,end}=JSON.parse(options!.body as string) as {start:Coordinate;end:Coordinate}
      const route:Route={coordinates:[start,end],distance:100,duration:mode==='CAR'?20:30,snap_points:[{location:start,distance:0,name:''},{location:end,distance:0,name:''}],duration_source:'synthetic fixture'}
      return response({schemaVersion:'gsm-mode-route/v1',routingIdentity:identity(mode),route})
    });vi.stubGlobal('fetch',fetcher)
    const {result,rerender}=renderHook(({mix})=>useFleet(true,true,region,mix),{initialProps:{mix:'MIXED' as 'MIXED'|'MOTORBIKE'}})
    const clock=result.current.clock
    await act(async()=>result.current.generate('fixed',10))
    expect(result.current.scenario?.vehicles.filter(v=>v.vehicleType==='CAR')).toHaveLength(5)
    expect(result.current.scenario?.vehicles.filter(v=>v.vehicleType==='MOTORBIKE')).toHaveLength(5)
    expect(new Set(result.current.scenario?.vehicles.map(v=>v.id)).size).toBe(10)
    expect(result.current.scenario?.datasetFingerprint).toMatch(/^[a-f0-9]{64}$/)
    expect(result.current.scenario?.datasetFingerprint).not.toBe('fixture-CAR')
    expect(result.current.scenario?.vehicles.find(v=>v.vehicleType==='MOTORBIKE')?.route.duration).toBe(30)
    rerender({mix:'MOTORBIKE'});expect(result.current.scenario).toBeNull();expect(result.current.clock).toBe(clock)
    const controller=new AbortController();controller.abort()
    await expect(prepareModeFleet(region,'MIXED','fixed',10,controller.signal,new Map(),()=>{})).rejects.toThrow()
  })
})
