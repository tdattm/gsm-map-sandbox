import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api'
import { FleetClock } from './fleet-clock'
import { fixtureSnapshot, SnapshotGate, validateSimulationRoute, validateBookingDetail, type BookingDetail, type SelectedJourney, type SimulationJob, type SimulationResult, type SimulationRoute, type SimulationSnapshot } from './simulation'
import { presentationPolicy, type PresentationProfile } from './simulation-profile'

const base='/api/v3/simulation/jobs',regionId='nvmr-hanoi-core'
const terminal=(status:string)=>['COMPLETED','FAILED','CANCELLED','INTERRUPTED'].includes(status)
const errorMessage=(e:unknown)=>e instanceof Error?e.message+(e instanceof ApiError?` (HTTP ${e.status})`:''):String(e)
export function useSimulation(profile:PresentationProfile='standard') {
  const [clock]=useState(()=>new FleetClock()),[job,setJob]=useState<SimulationJob|null>(null),[result,setResult]=useState<SimulationResult|null>(null)
  const [snapshot,setSnapshot]=useState<SimulationSnapshot|null>(null),[route,setRoute]=useState<SimulationRoute|null>(null),[selectedId,setSelectedId]=useState<string|null>(null),[error,setError]=useState(''),[routeError,setRouteError]=useState(''),[loading,setLoading]=useState(false),[fixtureSize,setFixtureSize]=useState<number|null>(null)
  const [pollEpoch,setPollEpoch]=useState(0)
  const [journey,setJourney]=useState<SelectedJourney|null>(null),[detailLoading,setDetailLoading]=useState(false)
  const [detailEpoch,setDetailEpoch]=useState(0)
  const [detailLatencyMs,setDetailLatencyMs]=useState<number|null>(null)
  const submitting=useRef(false)
  const policy=presentationPolicy[profile]
  useEffect(()=>{clock.setPresentationHz(policy.clockHz)},[clock,policy])
  const epoch=useRef(0),requests=useRef(new Set<AbortController>()),gate=useRef<SnapshotGate|null>(null)
  const reset=useCallback(()=>{epoch.current++;requests.current.forEach(c=>c.abort());requests.current.clear();clock.configure(0);setJob(null);setResult(null);setSnapshot(null);setRoute(null);setJourney(null);setSelectedId(null);setError('');setRouteError('');setFixtureSize(null);setLoading(false)},[clock])
  useEffect(()=>()=>{requests.current.forEach(c=>c.abort());clock.dispose()},[clock])
  const fixture=useCallback((size:number)=>{reset();setFixtureSize(size);clock.configure(3600);setSnapshot(fixtureSnapshot(size));setSelectedId('fixture-00000')},[clock,reset])
  useEffect(()=>{
    if(fixtureSize===null)return
    let previousTime=clock.getSnapshot().simulationTimeSeconds,last=0,timer:number|undefined
    const publish=()=>{timer=undefined;if(document.hidden)return;const time=clock.getSnapshot().simulationTimeSeconds;if(time!==previousTime){last=performance.now();previousTime=time;setSnapshot(fixtureSnapshot(fixtureSize,time))}}
    const wake=()=>{if(timer===undefined&&!document.hidden)timer=window.setTimeout(publish,Math.max(0,policy.snapshotMs-(performance.now()-last)))}
    const unsubscribe=clock.subscribe(wake);document.addEventListener('visibilitychange',wake)
    return ()=>{unsubscribe();clearTimeout(timer);document.removeEventListener('visibilitychange',wake)}
  },[fixtureSize,clock,policy])
  const create=async(fleetSize:number,bookingCount:number,onlineFraction:number,seed:string,options?:{carCount?:number;horizonSeconds?:number;maxWaitSeconds?:number;workload?:string})=>{
    if(submitting.current||loading||job&&['QUEUED','RUNNING'].includes(job.status))return
    submitting.current=true
    reset();setLoading(true);const version=epoch.current,controller=new AbortController();requests.current.add(controller)
    try {
      const next=await api<SimulationJob>(base,{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({regionId,seed,fleetSize,carCount:options?.carCount??Math.round(fleetSize*.4),bookingCount,horizonSeconds:options?.horizonSeconds??900,maxWaitSeconds:options?.maxWaitSeconds??300,onlineFraction,workload:options?.workload??'typical'})})
      if(epoch.current===version)setJob(next)
    }catch(e){if(!controller.signal.aborted)setError(errorMessage(e))}finally{submitting.current=false;requests.current.delete(controller);if(epoch.current===version)setLoading(false)}
  }
  useEffect(()=>{
    if(!job||terminal(job.status))return
    const controller=new AbortController(),version=epoch.current;requests.current.add(controller);let timer:number|undefined
    const poll=async()=>{
      try {const next=await api<SimulationJob>(`${base}/${encodeURIComponent(job.id)}`,{signal:controller.signal});if(!controller.signal.aborted&&version===epoch.current){setJob(next);if(!terminal(next.status))timer=window.setTimeout(poll,700)}}
      catch(e){if(!controller.signal.aborted){setError(errorMessage(e));timer=window.setTimeout(poll,2000)}}
    }
    void poll();return ()=>{controller.abort();requests.current.delete(controller);clearTimeout(timer)}
  },[job?.id,job?.status,pollEpoch])
  useEffect(()=>{
    if(!job||job.status!=='COMPLETED')return
    const controller=new AbortController();requests.current.add(controller)
    api<SimulationResult>(`${base}/${encodeURIComponent(job.id)}/result?summary=true`,{signal:controller.signal}).then(value=>{
      if(controller.signal.aborted)return
      if(value.schemaVersion!=='gsm-simulation-result/v1'||value.runId!==job.id||value.regionId!==regionId||!Number.isFinite(value.simulationDurationSeconds)||value.simulationDurationSeconds<0)throw new Error('INVALID_SIMULATION_RESULT')
      setResult(value);gate.current=new SnapshotGate(job.id,regionId);clock.configure(value.simulationDurationSeconds)
    }).catch(e=>{if(!controller.signal.aborted)setError(errorMessage(e))})
    return ()=>{controller.abort();requests.current.delete(controller)}
  },[job?.id,job?.status,clock,pollEpoch])
  useEffect(()=>{
    if(!result)return
    const controller=new AbortController();requests.current.add(controller);let timer:number|undefined,inFlight=false,lastStart=0
    let publishedKey:string|null=null
    gate.current=new SnapshotGate(result.runId,regionId)
    const wake=()=>{if(timer===undefined&&!controller.signal.aborted&&!document.hidden)timer=window.setTimeout(poll,Math.max(0,policy.snapshotMs-(performance.now()-lastStart)))}
    const poll=async()=>{
      timer=undefined
      if(inFlight||controller.signal.aborted||document.hidden)return
      const version=epoch.current,time=clock.getSnapshot().simulationTimeSeconds
      const key=`${version}:${time.toFixed(3)}`
      if(key===publishedKey)return
      inFlight=true;lastStart=performance.now();let failed=false
      try {
        const next=await api<SimulationSnapshot>(`${base}/${encodeURIComponent(result.runId)}/snapshot?timeSeconds=${time.toFixed(3)}`,{signal:controller.signal})
        if(!controller.signal.aborted&&version===epoch.current&&gate.current?.accept(next)){publishedKey=key;setSnapshot(next);setError('')}
      }catch(e){failed=true;if(!controller.signal.aborted&&version===epoch.current)setError(errorMessage(e))}
      inFlight=false
      // Clock changes drive projections. A paused unchanged run has no polling loop.
      if(!controller.signal.aborted&&!failed)wake()
      else if(!controller.signal.aborted&&clock.getSnapshot().playbackStatus==='playing')timer=window.setTimeout(wake,2000)
    }
    const unsubscribe=clock.subscribe(wake);document.addEventListener('visibilitychange',wake)
    void poll();return ()=>{controller.abort();requests.current.delete(controller);clearTimeout(timer);unsubscribe();document.removeEventListener('visibilitychange',wake)}
  },[result,clock,policy,pollEpoch])
  const seek=useCallback((seconds:number)=>{epoch.current++;gate.current=result?new SnapshotGate(result.runId,regionId):null;setRoute(null);setSnapshot(null);clock.seek(seconds);if(fixtureSize!==null)setSnapshot(fixtureSnapshot(fixtureSize,clock.getSnapshot().simulationTimeSeconds))},[clock,result,fixtureSize])
  const vehicle=snapshot?.vehicles.find(v=>v.id===selectedId),bookingId=vehicle?.activeBookingId??null,identity=vehicle?.vehicleType
  useEffect(()=>{
    setRoute(null);setJourney(null);setRouteError('');setDetailLoading(false);setDetailLatencyMs(null)
    if(!snapshot||!vehicle||!bookingId||fixtureSize!==null)return
    const controller=new AbortController();requests.current.add(controller)
    setDetailLoading(true)
    const begun=performance.now()
    const root=`${base}/${encodeURIComponent(snapshot.runId)}`
    const loadRoute=async(ref:string)=>validateSimulationRoute(await api<SimulationRoute>(`${root}/routes/${encodeURIComponent(ref)}`,{signal:controller.signal}),snapshot,{...vehicle,routeRef:ref})
    void (async()=>{
      try {
        const detail=validateBookingDetail(await api<BookingDetail>(`${root}/bookings/${encodeURIComponent(bookingId)}`,{signal:controller.signal}),snapshot,vehicle)
        if(controller.signal.aborted)return
        const [pickupRoute,tripRoute]=await Promise.all([detail.pickupLeg.routeRef?loadRoute(detail.pickupLeg.routeRef):null,loadRoute(detail.tripLeg.routeRef!)])
        if(!controller.signal.aborted){setJourney({detail,pickupRoute,tripRoute});setDetailLatencyMs(performance.now()-begun)}
      }catch(e){
        if(!controller.signal.aborted){
          setRouteError(errorMessage(e))
          // Old API/historical details can still expose the validated active leg.
          if(vehicle.routeRef)try {const value=await loadRoute(vehicle.routeRef);if(!controller.signal.aborted)setRoute(value)}catch{/* Detail error remains visible. */}
        }
      }finally{if(!controller.signal.aborted)setDetailLoading(false)}
    })()
    return ()=>{controller.abort();requests.current.delete(controller)}
    // Route references and identities are immutable within a run. Position ticks do not refetch geometry.
  },[snapshot?.runId,bookingId,selectedId,identity,fixtureSize,detailEpoch])
  const cancel=async()=>{
    if(!job)return
    epoch.current++;setSnapshot(null);setResult(null);setRoute(null);clock.configure(0)
    const controller=new AbortController();requests.current.add(controller)
    try {const next=await api<SimulationJob>(`${base}/${encodeURIComponent(job.id)}/cancel`,{method:'POST',signal:controller.signal});if(!controller.signal.aborted)setJob(next)}catch(e){if(!controller.signal.aborted){setError(errorMessage(e));setPollEpoch(value=>value+1)}}finally{requests.current.delete(controller)}
  }
  const open=async(id:string)=>{
    reset();setLoading(true);const version=epoch.current,controller=new AbortController();requests.current.add(controller)
    try {const next=await api<SimulationJob>(`${base}/${encodeURIComponent(id.trim())}`,{signal:controller.signal});if(!controller.signal.aborted&&epoch.current===version)setJob(next)}
    catch(e){if(!controller.signal.aborted&&epoch.current===version)setError(errorMessage(e))}
    finally{requests.current.delete(controller);if(epoch.current===version)setLoading(false)}
  }
  const retry=()=>{setError('');setPollEpoch(value=>value+1)}
  const currentJourney=journey&&journey.detail.runId===snapshot?.runId&&journey.detail.vehicleId===vehicle?.id&&journey.detail.bookingId===bookingId?journey:null
  const activeRoute=currentJourney?(vehicle?.serviceState==='ASSIGNED'?currentJourney.pickupRoute:currentJourney.tripRoute):route?.routeRef===vehicle?.routeRef?route:null
  const retryDetail=()=>setDetailEpoch(value=>value+1)
  return {open,retry,retryDetail,clock,job,result,snapshot,route:activeRoute,journey:currentJourney,detailLoading,detailLatencyMs,vehicle,selectedId,setSelectedId,error,routeError,loading,fixtureSize,fixture,create,cancel,reset,seek}
}
