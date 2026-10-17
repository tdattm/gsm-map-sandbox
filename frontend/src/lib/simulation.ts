import type { Coordinate } from './api'
import { seededRandom } from './fleet'
import { sameRoutingIdentity, type RoutingIdentity, type VehicleType } from './multimodal'

export interface SimulationVehicle { id:string; vehicleType:VehicleType; serviceState:'OFFLINE'|'IDLE'|'ASSIGNED'|'ON_TRIP'; position:Coordinate; headingDegrees:number; activeBookingId:string|null; routeRef:string|null }
export interface SimulationSnapshot {
  schemaVersion:'gsm-simulation-snapshot/v1'; runId:string; regionId:string; sequenceNumber:number; simulationTimeSeconds:number
  counts:{total:number;offline:number;online:number;idle:number;assigned:number;onTrip:number;moving:number}
  vehicles:SimulationVehicle[]; routingIdentities:Record<VehicleType,RoutingIdentity>
}
export interface SimulationRoute { schemaVersion:'gsm-simulation-route/v1';runId:string;regionId:string;routeRef:string;routingIdentity:RoutingIdentity;coordinates:Coordinate[];distance:number;duration:number }
export interface SimulationJob { config?:Record<string,unknown>; id:string;status:'QUEUED'|'RUNNING'|'COMPLETED'|'CANCELLED'|'FAILED'|'INTERRUPTED';progress:number;error?:string|{code:string;message:string}|null }
export interface SimulationResult {schemaVersion:'gsm-simulation-result/v1';runId:string;regionId:string;simulationDurationSeconds:number;counts:{requested:number;assigned:number;completed:number;unserved:number}}
export interface SimulationLeg {phase:'pickup'|'trip';routeRef:string|null;startTimeSeconds:number;endTimeSeconds:number;distance:number;duration:number}
export interface BookingDetail {
  schemaVersion:'gsm-simulation-booking-detail/v1';runId:string;regionId:string;bookingId:string;vehicleId:string;vehicleType:VehicleType;serviceType:VehicleType
  routingIdentity:RoutingIdentity;requestTimeSeconds:number;pickupDeadlineSeconds:number;pickup:Coordinate;dropoff:Coordinate;requestedPickup:Coordinate;requestedDropoff:Coordinate;assignmentPosition:Coordinate
  pickupLeg:SimulationLeg;tripLeg:SimulationLeg;provenance:string
}
export interface SelectedJourney {detail:BookingDetail;pickupRoute:SimulationRoute|null;tripRoute:SimulationRoute}
export function validateBookingDetail(d:BookingDetail,s:SimulationSnapshot,v:SimulationVehicle) {
  if(!d||d.schemaVersion!=='gsm-simulation-booking-detail/v1'||d.runId!==s.runId||d.regionId!==s.regionId||d.vehicleId!==v.id||d.bookingId!==v.activeBookingId||d.vehicleType!==v.vehicleType||d.serviceType!==v.vehicleType||!sameRoutingIdentity(d.routingIdentity,s.routingIdentities[v.vehicleType])||![d.pickup,d.dropoff,d.requestedPickup,d.requestedDropoff,d.assignmentPosition].every(point))throw new Error('BOOKING_DETAIL_IDENTITY_MISMATCH')
  for(const [phase,leg] of [['pickup',d.pickupLeg],['trip',d.tripLeg]] as const) {
    if(!leg||leg.phase!==phase||![leg.startTimeSeconds,leg.endTimeSeconds,leg.duration,leg.distance].every(n=>Number.isFinite(n)&&n>=0)||leg.endTimeSeconds<leg.startTimeSeconds||Math.abs(leg.endTimeSeconds-leg.startTimeSeconds-leg.duration)>1e-6||!(leg.routeRef===null||typeof leg.routeRef==='string'))throw new Error('INVALID_BOOKING_LEG')
  }
  if(!d.tripLeg.routeRef||d.pickupLeg.endTimeSeconds!==d.tripLeg.startTimeSeconds||!Number.isFinite(d.requestTimeSeconds)||d.requestTimeSeconds<0||!Number.isFinite(d.pickupDeadlineSeconds)||d.pickupDeadlineSeconds<d.pickupLeg.endTimeSeconds||d.requestTimeSeconds>d.pickupLeg.startTimeSeconds||(!d.pickupLeg.routeRef&&(d.pickupLeg.distance!==0||d.pickupLeg.duration!==0)))throw new Error('INVALID_BOOKING_TIMING')
  return d
}
export function legProgress(leg:SimulationLeg,time:number) {return leg.duration?Math.max(0,Math.min(1,(time-leg.startTimeSeconds)/leg.duration)):time>=leg.endTimeSeconds?1:0}
const point = (p:unknown):p is Coordinate => Array.isArray(p) && p.length===2 && p.every(Number.isFinite) && Math.abs(p[0])<=180 && Math.abs(p[1])<=90
export function validateSnapshot(value:SimulationSnapshot,runId:string,regionId:string) {
  if(!value || value.schemaVersion!=='gsm-simulation-snapshot/v1' || value.runId!==runId || value.regionId!==regionId || !Number.isInteger(value.sequenceNumber) || value.sequenceNumber<0 || !Number.isFinite(value.simulationTimeSeconds) || value.simulationTimeSeconds<0 || !Array.isArray(value.vehicles)) throw new Error('INVALID_SIMULATION_SNAPSHOT')
  const c=value.counts, counts={OFFLINE:0,IDLE:0,ASSIGNED:0,ON_TRIP:0},ids=new Set<string>()
  for(const v of value.vehicles) {
    if(!v.id || ids.has(v.id) || !['CAR','MOTORBIKE'].includes(v.vehicleType) || !Object.hasOwn(counts,v.serviceState) || !point(v.position) || !Number.isFinite(v.headingDegrees) || !(v.activeBookingId===null || typeof v.activeBookingId==='string') || !(v.routeRef===null || typeof v.routeRef==='string')) throw new Error('INVALID_SIMULATION_VEHICLE')
    const identity=value.routingIdentities?.[v.vehicleType]
    const fixture=runId.startsWith('fixture-')&&identity?.profile==='synthetic-render-only'&&identity?.algorithm==='none'
    if(!identity || identity.regionId!==regionId || identity.vehicleType!==v.vehicleType || !['profileSha256','graphManifestSha256','sourceSha256','extractSha256'].every(key=>typeof identity[key as keyof RoutingIdentity]==='string'&&!!identity[key as keyof RoutingIdentity]) || (!fixture&&(identity.profile!==(v.vehicleType==='CAR'?'car':'motorbike')||identity.algorithm!=='mld'))) throw new Error('SIMULATION_IDENTITY_MISMATCH')
    if(!fixture&&(v.serviceState==='ASSIGNED'||v.serviceState==='ON_TRIP')!==!!v.activeBookingId) throw new Error('SIMULATION_ASSIGNMENT_MISMATCH')
    if(fixture&&(v.activeBookingId!==null||v.routeRef!==null))throw new Error('FIXTURE_HAS_BUSINESS_DATA')
    ids.add(v.id);counts[v.serviceState]++
  }
  if(!c || !['total','offline','online','idle','assigned','onTrip','moving'].every(key=>Object.hasOwn(c,key)&&Number.isInteger(c[key as keyof typeof c])&&c[key as keyof typeof c]>=0) || c.total!==ids.size || c.total!==c.offline+c.online || c.online!==c.idle+c.assigned+c.onTrip || c.offline!==counts.OFFLINE || c.idle!==counts.IDLE || c.assigned!==counts.ASSIGNED || c.onTrip!==counts.ON_TRIP || c.moving>c.assigned+c.onTrip) throw new Error('SIMULATION_COUNTS_MISMATCH')
  return value
}
/** Epoch is reset only on explicit run change/seek. HTTP completion order cannot move time backwards. */
export class SnapshotGate {
  private sequence=-1
  readonly runId:string
  readonly regionId:string
  constructor(runId:string,regionId:string){this.runId=runId;this.regionId=regionId}
  accept(value:SimulationSnapshot) {validateSnapshot(value,this.runId,this.regionId);if(value.sequenceNumber<=this.sequence)return false;this.sequence=value.sequenceNumber;return true}
}
export function validateSimulationRoute(route:SimulationRoute,snapshot:SimulationSnapshot,vehicle:SimulationVehicle) {
  if(route.schemaVersion!=='gsm-simulation-route/v1' || route.runId!==snapshot.runId || route.regionId!==snapshot.regionId || route.routeRef!==vehicle.routeRef || !sameRoutingIdentity(route.routingIdentity,snapshot.routingIdentities[vehicle.vehicleType]) || !Array.isArray(route.coordinates) || route.coordinates.length<2 || !route.coordinates.every(point) || !Number.isFinite(route.distance) || route.distance<0 || !Number.isFinite(route.duration) || route.duration<0) throw new Error('SIMULATION_ROUTE_IDENTITY_MISMATCH')
  return route
}
export function vehicleFeatures(snapshot:SimulationSnapshot):GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {type:'FeatureCollection',features:snapshot.vehicles.map(v=>({type:'Feature',id:v.id,geometry:{type:'Point',coordinates:v.position},properties:{id:v.id,vehicleType:v.vehicleType,state:v.serviceState,heading:v.headingDegrees}}))}
}
/** Standalone rendering load only: no dispatch/ETA/research outcome and no synthetic road routes. */
export function fixtureSnapshot(size:number,timeSeconds=0):SimulationSnapshot {
  if(![100,500,1000,3000,5000].includes(size))throw new Error('INVALID_FIXTURE_SIZE')
  const random=seededRandom('m4-render-fixture/v1'), count={total:size,offline:0,online:0,idle:0,assigned:0,onTrip:0,moving:0}
  const vehicles:SimulationVehicle[]=Array.from({length:size},(_,i)=>{
    const state=i%10===0?'OFFLINE':i%5===0?'ASSIGNED':i%3===0?'ON_TRIP':'IDLE'
    if(state==='OFFLINE')count.offline++;else count.online++
    if(state==='IDLE')count.idle++;if(state==='ASSIGNED')count.assigned++;if(state==='ON_TRIP')count.onTrip++
    const moving=state==='ASSIGNED'||state==='ON_TRIP';if(moving)count.moving++
    const lon=105.78+random()*.12,lat=20.98+random()*.12
    return {id:`fixture-${String(i).padStart(5,'0')}`,vehicleType:i<size*.4?'CAR':'MOTORBIKE',serviceState:state,position:[lon+(moving?Math.sin(timeSeconds/30+i)*.0005:0),lat+(moving?Math.cos(timeSeconds/30+i)*.0005:0)],headingDegrees:0,activeBookingId:null,routeRef:null}
  })
  const identity=(vehicleType:VehicleType):RoutingIdentity=>({regionId:'nvmr-hanoi-core',vehicleType,profile:'synthetic-render-only',profileSha256:'synthetic',graphManifestSha256:'synthetic-no-router',sourceSha256:'synthetic',extractSha256:'synthetic',algorithm:'none'})
  return {schemaVersion:'gsm-simulation-snapshot/v1',runId:`fixture-${size}`,regionId:'nvmr-hanoi-core',sequenceNumber:Math.floor(timeSeconds*1000),simulationTimeSeconds:timeSeconds,counts:count,vehicles,routingIdentities:{CAR:identity('CAR'),MOTORBIKE:identity('MOTORBIKE')}}
}
