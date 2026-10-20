import type { SimulationResult, SimulationSnapshot, SimulationVehicle } from './simulation'
import { validateSnapshot } from './simulation'

export const connectedBase = '/api/v5/simulation/jobs'
export const zoneIds = ['hanoi', 'bac-ninh', 'hung-yen', 'phu-tho', 'thai-nguyen'] as const
export type ZoneId = typeof zoneIds[number]
export const zoneLabels: Record<ZoneId, string> = { hanoi: 'Hà Nội', 'bac-ninh': 'Bắc Ninh', 'hung-yen': 'Hưng Yên', 'phu-tho': 'Phú Thọ', 'thai-nguyen': 'Thái Nguyên' }
export const zoneLabel = (id: string) => zoneLabels[id as ZoneId] ?? (id === 'outside-operating-zones' ? 'Ngoài operating zones' : id)
export interface FleetAllocation { zoneId: ZoneId; carCount: number; motorbikeCount: number }
export interface ConnectedConfig {
  schemaVersion: 'gsm-nvmr-connected-scenario/v1'; seed: string; fleetSize: number; carCount: number; bookingCount: number
  horizonSeconds: number; maxWaitSeconds: number; onlineFraction: number; fleetAllocations: FleetAllocation[]
  demandWeights: Record<ZoneId, number>; demandCarFraction: number; crossZoneDemandFraction: number
}
export type ConnectedVehicle = SimulationVehicle & { homeZoneId: string; currentZoneId: string;isMoving:boolean }
export type ConnectedSnapshot = Omit<SimulationSnapshot, 'schemaVersion' | 'vehicles'> & {
  schemaVersion: 'gsm-nvmr-connected-snapshot/v1'; vehicles: ConnectedVehicle[]
  zoneCounts: Record<string, SimulationSnapshot['counts']>
}
export interface ConnectedKpis {
  fleetSize:number; counts:SimulationResult['counts']
  pickupWait:{sumSeconds:number;count:number;meanSeconds:number|null;maximumSeconds:number|null}
  utilization:{busyVehicleSeconds:number;onlineVehicleSeconds:number;fleetVehicleSeconds:number;busyFractionOfOnline:number|null;busyFractionOfFleet:number|null}
}
export type ConnectedResult = Omit<SimulationResult, 'schemaVersion'> & {
  schemaVersion: 'gsm-nvmr-connected-result/v1'; config: ConnectedConfig
  kpis?: {global: ConnectedKpis; byZone: Record<string, ConnectedKpis>; byMode: Record<string, ConnectedKpis>;attribution?:string}
  distributionQuality?: Record<string, unknown>; operatingZones?: unknown
}

/** Largest remainder allocation, stable tie order; totals are exact at every scale. */
export function allocateIntegers(total: number, weights: number[]) {
  if (!Number.isInteger(total) || total < 0 || !weights.length || weights.some(w => !Number.isFinite(w) || w < 0) || weights.reduce((a,b) => a+b,0) <= 0) throw new Error('INVALID_ALLOCATION')
  const sum = weights.reduce((a,b) => a+b,0), raw = weights.map(w => total*w/sum), values = raw.map(Math.floor)
  const order = raw.map((value,index) => ({index,remainder:value-values[index]})).sort((a,b) => b.remainder-a.remainder || a.index-b.index)
  const remaining=total-values.reduce((a,b) => a+b,0)
  for (let i=0; i<remaining; i++) values[order[i].index]++
  return values
}
export function defaultAllocations(size = 5000): FleetAllocation[] {
  const cars = allocateIntegers(Math.round(size*.4), [80,5,5,5,5]), bikes = allocateIntegers(size-Math.round(size*.4), [80,5,5,5,5])
  return zoneIds.map((zoneId,index) => ({zoneId,carCount:cars[index],motorbikeCount:bikes[index]}))
}
export function allocationTotals(rows: FleetAllocation[]) {
  return rows.reduce((sum,row) => ({fleetSize:sum.fleetSize+row.carCount+row.motorbikeCount,carCount:sum.carCount+row.carCount,motorbikeCount:sum.motorbikeCount+row.motorbikeCount}), {fleetSize:0,carCount:0,motorbikeCount:0})
}

/** Explicit presentation adapter only. The transport and persisted version remain v5. */
export function connectedMapSnapshot(value: ConnectedSnapshot): SimulationSnapshot {
  return {...value,schemaVersion:'gsm-simulation-snapshot/v1'}
}
export function validateConnectedSnapshot(value: ConnectedSnapshot, runId: string, expectedFleet?: number) {
  if (!value || value.schemaVersion !== 'gsm-nvmr-connected-snapshot/v1' || value.regionId !== 'nvmr-connected') throw new Error('INVALID_CONNECTED_SNAPSHOT')
  validateSnapshot(connectedMapSnapshot(value), runId, 'nvmr-connected')
  if (expectedFleet !== undefined && value.counts.total !== expectedFleet) throw new Error('CONNECTED_FLEET_CONSERVATION')
  if (value.vehicles.some(v => !zoneIds.includes(v.homeZoneId as ZoneId) || ![...zoneIds,'outside-operating-zones'].includes(v.currentZoneId as ZoneId) || typeof v.isMoving!=='boolean')) throw new Error('CONNECTED_ZONE_IDENTITY')
  if (!value.zoneCounts || typeof value.zoneCounts !== 'object') throw new Error('CONNECTED_ZONE_COUNTS_MISSING')
  if (Object.keys(value.zoneCounts).some(id=>![...zoneIds,'outside-operating-zones'].includes(id as ZoneId))) throw new Error('CONNECTED_ZONE_IDENTITY')
  const rows = Object.values(value.zoneCounts)
  const countKeys=['total','online','offline','idle','assigned','onTrip','moving'] as const
  if (rows.some(row=>!row||countKeys.some(key=>!Number.isInteger(row[key])||row[key]<0))) throw new Error('CONNECTED_ZONE_COUNTS_MISMATCH')
  for (const key of countKeys) {
    if (rows.reduce((sum,row) => sum + row[key],0) !== value.counts[key]) throw new Error('CONNECTED_ZONE_COUNTS_MISMATCH')
  }
  if (value.vehicles.filter(v=>v.isMoving).length!==value.counts.moving) throw new Error('CONNECTED_MOVING_COUNTS_MISMATCH')
  if (value.vehicles.some(v=>v.isMoving&&(!['ASSIGNED','ON_TRIP'].includes(v.serviceState)||!v.routeRef))) throw new Error('CONNECTED_MOVING_STATE_MISMATCH')
  for (const [id,counts] of Object.entries(value.zoneCounts)) {
    const actual=filterConnectedSnapshot(value,id,'')!.counts
    for (const key of countKeys) if (counts[key]!==actual[key]) throw new Error('CONNECTED_ZONE_COUNTS_MISMATCH')
  }
  return value
}
export function validateConnectedResult(value: ConnectedResult, runId: string) {
  if (!value || value.schemaVersion !== 'gsm-nvmr-connected-result/v1' || value.runId !== runId || value.regionId !== 'nvmr-connected' || !Number.isFinite(value.simulationDurationSeconds) || value.simulationDurationSeconds < 0 || !value.config || value.config.schemaVersion !== 'gsm-nvmr-connected-scenario/v1') throw new Error('INVALID_CONNECTED_RESULT')
  const c=value.counts
  if (!c || !['requested','assigned','completed','unserved'].every(k => Number.isInteger(c[k as keyof typeof c]) && c[k as keyof typeof c]>=0) || c.completed+c.unserved!==c.requested || c.completed>c.assigned) throw new Error('CONNECTED_RESULT_COUNTS_MISMATCH')
  return value
}
export function filterConnectedSnapshot(snapshot: ConnectedSnapshot | null, zoneId: string, mode: string) {
  if (!snapshot) return null
  const vehicles=snapshot.vehicles.filter(v => (!zoneId || v.currentZoneId===zoneId) && (!mode || v.vehicleType===mode))
  const idle=vehicles.filter(v=>v.serviceState==='IDLE').length,assigned=vehicles.filter(v=>v.serviceState==='ASSIGNED').length,onTrip=vehicles.filter(v=>v.serviceState==='ON_TRIP').length,offline=vehicles.filter(v=>v.serviceState==='OFFLINE').length
  return {...connectedMapSnapshot(snapshot),vehicles,counts:{total:vehicles.length,offline,online:idle+assigned+onTrip,idle,assigned,onTrip,moving:vehicles.filter(v=>v.isMoving).length}}
}
