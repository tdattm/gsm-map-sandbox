import { useEffect, useState } from 'react'
import { api, type Coordinate, type Route } from './api'
import { validateBookingPlan, type BookingPlan, type BookingConfig } from './booking'
import { prepareScenario, type CandidateCatalog, type FleetScenario } from './fleet'
export type VehicleType = 'CAR' | 'MOTORBIKE'
export type FleetMix = VehicleType | 'MIXED'
export interface RoutingIdentity { regionId: string; vehicleType: VehicleType; profile: string; profileSha256: string; graphManifestSha256: string; sourceSha256: string; extractSha256: string; algorithm: string }
export interface ModeMetadata { vehicleType: VehicleType; ready: boolean; reason: string; routingIdentity: RoutingIdentity | null }
const emptyModes:ModeMetadata[]=[]
export const modeApi = (region: string, type: VehicleType, path: string) => `/api/v2/regions/${encodeURIComponent(region)}/modes/${type}${path}`
export const typesFor = (mix: FleetMix, count: number): VehicleType[] => Array.from({length:count},(_,i)=>mix === 'MIXED' ? i%2 ? 'MOTORBIKE':'CAR' : mix)
export function useModes(regionId: string, saved: boolean, refreshKey: number) {
  const [snapshot,setSnapshot]=useState<{regionId:string; modes:ModeMetadata[]} | null>(null)
  useEffect(()=>{
    if(saved || regionId==='hcm-center') return
    const controller=new AbortController()
    api<{regionId:string;modes:ModeMetadata[]}>(`/api/v2/regions/${encodeURIComponent(regionId)}/modes`,{signal:controller.signal})
      .then(result=>{if(!controller.signal.aborted && result.regionId===regionId && Array.isArray(result.modes))setSnapshot(result)})
      .catch(()=>{if(!controller.signal.aborted)setSnapshot(null)})
    return ()=>controller.abort()
  },[regionId,saved,refreshKey])
  return snapshot?.regionId===regionId ? snapshot.modes : emptyModes
}
export const sameRoutingIdentity = (a:RoutingIdentity,b:RoutingIdentity) => (['regionId','vehicleType','profile','profileSha256','graphManifestSha256','sourceSha256','extractSha256','algorithm'] as const).every(k=>a[k]===b[k])
export async function modeRoute(region: string, mode: VehicleType, start: Coordinate, end: Coordinate, signal: AbortSignal, expected?:RoutingIdentity) {
  const result=await api<{schemaVersion:string;routingIdentity:RoutingIdentity;route:Route}>(modeApi(region,mode,'/route'),{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start,end}),signal})
  if(result.schemaVersion!=='gsm-mode-route/v1' || result.routingIdentity.regionId!==region || result.routingIdentity.vehicleType!==mode || result.routingIdentity.profile!==(mode==='CAR'?'car':'motorbike') || !result.routingIdentity.graphManifestSha256 || (expected && !sameRoutingIdentity(result.routingIdentity,expected))) throw new Error('MODE_RESPONSE_MISMATCH')
  return result.route
}
export interface MixedConfig extends BookingConfig {vehicleTypes:VehicleType[];serviceTypes:VehicleType[]}
export interface MixedPlan {schemaVersion:string;regionId:string;config:MixedConfig;routingIdentities:Record<string,RoutingIdentity>;plan:BookingPlan}
export function validateMixed(result:MixedPlan, region:string, expected?:MixedConfig) {
  if(result.schemaVersion!=='gsm-multimodal-scenario/v1' || result.regionId!==region) throw new Error('INVALID_MULTIMODAL_PLAN')
  const plan=validateBookingPlan(result.plan)
  const config=result.config
  if(!config || config.vehicleTypes?.length!==plan.vehicles.length || config.serviceTypes?.length!==plan.demand.length) throw new Error('INVALID_MULTIMODAL_CONFIG')
  if(expected && (Object.entries(expected).some(([k,v])=>JSON.stringify(v)!==JSON.stringify(config[k as keyof MixedConfig])))) throw new Error('MODE_RESPONSE_MISMATCH')
  for(const [i,v] of plan.vehicles.entries()) if(v.vehicleType!==config.vehicleTypes[i]) throw new Error('VEHICLE_CONFIG_MISMATCH')
  for(const b of plan.demand) if(!/^BK-\d{3}$/.test(b.id) || b.serviceType!==config.serviceTypes[Number(b.id.slice(3))-1]) throw new Error('SERVICE_CONFIG_MISMATCH')
  for(const [mode,id] of Object.entries(result.routingIdentities)) if(id.vehicleType!==mode || id.regionId!==region || id.profile!==(mode==='CAR'?'car':'motorbike') || id.algorithm!=='mld') throw new Error('ROUTING_IDENTITY_MISMATCH')
  for(const v of plan.vehicles) if(!['CAR','MOTORBIKE'].includes(v.vehicleType ?? '')) throw new Error('INVALID_VEHICLE_TYPE')
  for(const b of plan.demand) if(!['CAR','MOTORBIKE'].includes(b.serviceType ?? '')) throw new Error('INVALID_SERVICE_TYPE')
  for(const a of plan.assignments) {
    const vehicle=plan.vehicles.find(v=>v.id===a.vehicleId)!, booking=plan.demand.find(b=>b.id===a.bookingId)!
    if(vehicle.vehicleType!==booking.serviceType || a.vehicleType!==vehicle.vehicleType || !a.routingIdentity || !result.routingIdentities[a.vehicleType!] || !sameRoutingIdentity(a.routingIdentity,result.routingIdentities[a.vehicleType!])) throw new Error('CROSS_MODE_ASSIGNMENT')
    if(a.dispatchCandidates.some(c=>plan.vehicles.find(v=>v.id===c.vehicleId)?.vehicleType!==vehicle.vehicleType)) throw new Error('CROSS_MODE_CANDIDATE')
  }
  return plan
}

export async function prepareModeFleet(region:string,mix:FleetMix,seed:string,count:number,signal:AbortSignal,cache:Map<string,Route>,onProgress:(n:number)=>void):Promise<FleetScenario> {
  const types=typesFor(mix,count), results:FleetScenario[]=[]
  let done=0
  for(const mode of ['CAR','MOTORBIKE'] as const) {
    const size=types.filter(t=>t===mode).length;if(!size)continue
    const catalog=await api<CandidateCatalog>(modeApi(region,mode,'/candidates'),{signal})
    if(catalog.provenance.vehicle_type!==mode || catalog.provenance.region_id!==region)throw new Error('MODE_RESPONSE_MISMATCH')
    const identity=catalog.provenance.routingIdentity as RoutingIdentity
    const part=await prepareScenario(catalog,seed,size,signal,(a,b,s)=>modeRoute(region,mode,a,b,s,identity),cache,n=>onProgress(done+n))
    for(const v of part.vehicles){v.vehicleType=mode;v.id=`${mode}-${v.id}`;v.label=v.id}
    for(const f of part.failures)f.id=`${mode}-${f.id}`
    results.push(part);done+=size
  }
  signal.throwIfAborted()
  const first=results[0]
  // New contract only: the mixed identity includes both mode fingerprints.
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(results.map(r=>r.datasetFingerprint))))
  const fingerprint=Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('')
  signal.throwIfAborted()
  return {...first,id:`multimodal-fleet/v1:${results.map(r=>r.id).join(':')}`,vehicles:results.flatMap(r=>r.vehicles),
    datasetFingerprint:fingerprint,
    routingSource:mix==='MIXED' ? 'OSRM local / CAR + MOTORBIKE / MLD' : first.routingSource,
    simulationDurationSeconds:Math.max(...results.map(r=>r.simulationDurationSeconds)),requestedVehicles:count,
    failures:results.flatMap(r=>r.failures),routeRequests:results.reduce((s,r)=>s+r.routeRequests,0),cacheHits:results.reduce((s,r)=>s+r.cacheHits,0),
    provenance:{...first.provenance,modelVersion:'multimodal-fleet/v1',modeProvenance:results.map(r=>r.provenance)}}
}
