import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/lib/api'
import { useSimulation } from '../src/lib/use-simulation'
import { fixtureSnapshot } from '../src/lib/simulation'
vi.mock('../src/lib/api',async(importOriginal)=>({...await importOriginal<typeof import('../src/lib/api')>(),api:vi.fn()}))
const mocked=vi.mocked(api)
function deferred<T>(){let resolve!:(v:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve}}
afterEach(()=>{mocked.mockReset();vi.useRealTimers()})
describe('M3 job lifecycle isolation',()=>{
  it('deduplicates same-turn create and connection retry never repeats POST',async()=>{
    const pending=deferred<unknown>();mocked.mockReturnValue(pending.promise)
    const {result,unmount}=renderHook(()=>useSimulation())
    let first:Promise<void>,second:Promise<void>
    act(()=>{first=result.current.create(10,20,1,'one');second=result.current.create(10,20,1,'one')})
    expect(mocked.mock.calls.filter(([,options])=>options?.method==='POST')).toHaveLength(1)
    await act(async()=>{pending.resolve({id:'one',status:'CANCELLED',progress:0});await first!;await second!})
    act(()=>result.current.retry())
    expect(mocked.mock.calls.filter(([,options])=>options?.method==='POST')).toHaveLength(1)
    unmount()
  })
  it('does not transfer immutable paused snapshots repeatedly and resumes after seek',async()=>{
    vi.useFakeTimers()
    mocked.mockImplementation((path,options)=>{
      if(options?.method==='POST')return Promise.resolve({id:'run-1',status:'COMPLETED',progress:1})
      if(path.includes('/result'))return Promise.resolve({schemaVersion:'gsm-simulation-result/v1',runId:'run-1',regionId:'nvmr-hanoi-core',simulationDurationSeconds:120,counts:{requested:0,assigned:0,completed:0,unserved:0}})
      const time=Number(new URL(path,'http://localhost').searchParams.get('timeSeconds'))
      const value=fixtureSnapshot(100,time);value.runId='run-1';for(const v of value.vehicles)if(['ASSIGNED','ON_TRIP'].includes(v.serviceState))v.activeBookingId='test-booking'
      for(const mode of ['CAR','MOTORBIKE'] as const){value.routingIdentities[mode].profile=mode==='CAR'?'car':'motorbike';value.routingIdentities[mode].algorithm='mld'}
      return Promise.resolve(value)
    })
    const {result,unmount}=renderHook(()=>useSimulation())
    await act(()=>result.current.create(100,0,.8,'seed'))
    await act(()=>vi.advanceTimersByTimeAsync(1000))
    expect(mocked.mock.calls.filter(([path])=>path.includes('/snapshot')).length).toBe(1)
    expect(vi.getTimerCount()).toBe(0) // Paused projection has no 100ms wake loop.
    act(()=>result.current.seek(10))
    await act(()=>vi.advanceTimersByTimeAsync(1000))
    expect(mocked.mock.calls.filter(([path])=>path.includes('/snapshot')).length).toBe(2)
    expect(result.current.snapshot?.simulationTimeSeconds).toBe(10)
    unmount()
  })
  it('Meeting changes only presentation cadence and does not edit the submitted scientific config',async()=>{
    const bodies:unknown[]=[]
    mocked.mockImplementation((_path,options)=>{if(options?.body)bodies.push(JSON.parse(String(options.body)));return Promise.resolve({id:'done',status:'CANCELLED',progress:0})})
    const standard=renderHook(()=>useSimulation('standard')),meeting=renderHook(()=>useSimulation('meeting'))
    await act(()=>standard.result.current.create(100,20,.8,'same',{carCount:40,horizonSeconds:900,maxWaitSeconds:300}))
    await act(()=>meeting.result.current.create(100,20,.8,'same',{carCount:40,horizonSeconds:900,maxWaitSeconds:300}))
    expect(bodies).toHaveLength(2);expect(bodies[0]).toEqual(bodies[1])
    standard.unmount();meeting.unmount()
  })
  it('does not resurrect a late create response after reset / fixture change',async()=>{
    const pending=deferred<unknown>();mocked.mockReturnValue(pending.promise)
    const {result,unmount}=renderHook(()=>useSimulation())
    let creation:Promise<void>;act(()=>{creation=result.current.create(100,20,.8,'seed')})
    act(()=>result.current.fixture(500))
    await act(async()=>{pending.resolve({id:'old',status:'RUNNING',progress:.2});await creation!})
    expect(result.current.job).toBeNull();expect(result.current.fixtureSize).toBe(500);expect(result.current.snapshot?.counts.total).toBe(500)
    unmount()
  })
  it('ignores old completion after cancellation and never publishes partial result',async()=>{
    const pendingStatus=deferred<unknown>()
    mocked.mockImplementation((path,options)=>{
      if(path.endsWith('/cancel'))return Promise.resolve({id:'run-1',status:'CANCELLED',progress:0})
      if(options?.method==='POST')return Promise.resolve({id:'run-1',status:'RUNNING',progress:.1})
      return pendingStatus.promise
    })
    const {result,unmount}=renderHook(()=>useSimulation())
    await act(()=>result.current.create(100,20,.8,'seed'))
    await waitFor(()=>expect(result.current.job?.status).toBe('RUNNING'))
    await act(()=>result.current.cancel())
    await act(async()=>{pendingStatus.resolve({id:'run-1',status:'COMPLETED',progress:1});await pendingStatus.promise})
    expect(result.current.job?.status).toBe('CANCELLED');expect(result.current.snapshot).toBeNull();expect(result.current.result).toBeNull()
    expect(mocked.mock.calls.some(([path])=>path.includes('/result'))).toBe(false)
    unmount()
  })
  it('restarts status polling after failed cancellation without accepting old status',async()=>{
    const pendingStatus=deferred<unknown>();let polls=0
    mocked.mockImplementation((path,options)=>{
      if(path.endsWith('/cancel'))return Promise.reject(new Error('Network unavailable'))
      if(options?.method==='POST')return Promise.resolve({id:'run-1',status:'RUNNING',progress:.1})
      polls++;return polls===1?pendingStatus.promise:Promise.resolve({id:'run-1',status:'RUNNING',progress:.8})
    })
    const {result,unmount}=renderHook(()=>useSimulation())
    await act(()=>result.current.create(100,20,.8,'seed'))
    await waitFor(()=>expect(polls).toBe(1))
    await act(()=>result.current.cancel())
    await waitFor(()=>expect(result.current.job?.progress).toBe(.8))
    await act(async()=>{pendingStatus.resolve({id:'run-1',status:'COMPLETED',progress:1});await pendingStatus.promise})
    expect(result.current.job?.status).toBe('RUNNING');expect(result.current.job?.progress).toBe(.8)
    expect(result.current.error).toBe('Network unavailable');expect(result.current.result).toBeNull()
    unmount()
  })
})


describe('Simulation product configuration and opening runs',()=>{
  it('submits the chosen mix and supported demand controls unchanged',async()=>{
    mocked.mockResolvedValue({id:'small',status:'CANCELLED',progress:0})
    const {result,unmount}=renderHook(()=>useSimulation())
    await act(()=>result.current.create(10,20,1,'ux',{carCount:5,horizonSeconds:600,maxWaitSeconds:120,workload:'burst'}))
    expect(JSON.parse(mocked.mock.calls[0][1]!.body as string)).toEqual({regionId:'nvmr-hanoi-core',seed:'ux',fleetSize:10,carCount:5,bookingCount:20,horizonSeconds:600,maxWaitSeconds:120,onlineFraction:1,workload:'burst'})
    unmount()
  })
  it('does not publish an old open-run request over a newer fixture',async()=>{
    const pending=deferred<unknown>();mocked.mockReturnValue(pending.promise)
    const {result,unmount}=renderHook(()=>useSimulation())
    let opening:Promise<void>;act(()=>{opening=result.current.open('old-run')})
    act(()=>result.current.fixture(1000))
    await act(async()=>{pending.resolve({id:'old-run',status:'COMPLETED',progress:1});await opening!})
    expect(result.current.job).toBeNull();expect(result.current.snapshot?.counts.total).toBe(1000)
    expect(mocked.mock.calls.some(([path])=>path.includes('/result'))).toBe(false)
    unmount()
  })
})
