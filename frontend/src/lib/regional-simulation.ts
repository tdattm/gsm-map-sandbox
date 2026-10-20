import type { SimulationResult, SimulationSnapshot, SimulationVehicle } from './simulation'
import { validateSnapshot } from './simulation'

export const regionalBase = '/api/v4/simulation/jobs'
export const regionalIds = ['nvmr-hanoi-core', 'nvmr-bac-ninh-core'] as const
export type RegionalId = typeof regionalIds[number]
export interface RegionAllocation {
  regionId: RegionalId
  fleetSize: number
  carCount: number
  bookingCount: number
  onlineFraction: number
}
export interface RegionalConfig {
  schemaVersion: 'gsm-nvmr-regional-scenario/v1'
  seed: string
  horizonSeconds: number
  maxWaitSeconds: number
  regions: RegionAllocation[]
}
export interface RegionalResult {
  schemaVersion: 'gsm-nvmr-regional-result/v1'
  runId: string
  config: RegionalConfig
  simulationDurationSeconds: number
  counts: SimulationResult['counts']
  globalTotals?: {fleetSize:number;carCount:number;motorbikeCount:number;bookingCount:number}
  regions: (SimulationResult & {config: RegionAllocation})[]
  metrics?: Record<string, unknown>
}
export interface RegionalSnapshot {
  schemaVersion: 'gsm-nvmr-regional-snapshot/v1'
  runId: string
  simulationTimeSeconds: number
  sequenceNumber: number
  counts: SimulationSnapshot['counts']
  regions: SimulationSnapshot[]
  vehicles: (SimulationVehicle & {regionId: string})[]
}
export const regionLabel = (id: string) => id === 'nvmr-hanoi-core' ? 'Hanoi Core' : id === 'nvmr-bac-ninh-core' ? 'Bắc Ninh Core · pilot' : id
export const syntheticAllocation = (): RegionAllocation[] => regionalIds.map(regionId => ({regionId, fleetSize: 10, carCount: 5, bookingCount: 12, onlineFraction: 1}))

export function allocationTotals(regions: RegionAllocation[]) {
  return regions.reduce((total, r) => ({fleetSize: total.fleetSize + r.fleetSize, carCount: total.carCount + r.carCount,
    motorbikeCount: total.motorbikeCount + r.fleetSize - r.carCount, bookingCount: total.bookingCount + r.bookingCount}),
  {fleetSize: 0, carCount: 0, motorbikeCount: 0, bookingCount: 0})
}

export function validateRegionalResult(value: RegionalResult, runId: string) {
  if (!value || value.schemaVersion !== 'gsm-nvmr-regional-result/v1' || value.runId !== runId ||
      !Number.isFinite(value.simulationDurationSeconds) || value.simulationDurationSeconds < 0 ||
      !Array.isArray(value.regions) || value.regions.length !== 2 ||
      new Set(value.regions.map(r => r.regionId)).size !== 2 ||
      !regionalIds.every(id => value.regions.some(r => r.regionId === id))) throw new Error('INVALID_REGIONAL_RESULT')
  for (const key of ['requested', 'assigned', 'completed', 'unserved'] as const) {
    if (!Number.isInteger(value.counts?.[key]) || value.counts[key] < 0 ||
        value.regions.reduce((sum, r) => sum + r.counts[key], 0) !== value.counts[key]) throw new Error('REGIONAL_RESULT_COUNTS_MISMATCH')
  }
  return value
}

export function validateRegionalSnapshot(value: RegionalSnapshot, runId: string) {
  if (!value || value.schemaVersion !== 'gsm-nvmr-regional-snapshot/v1' || value.runId !== runId ||
      !Number.isFinite(value.simulationTimeSeconds) || value.simulationTimeSeconds < 0 ||
      !Number.isInteger(value.sequenceNumber) || value.sequenceNumber < 0 || !Array.isArray(value.regions) || value.regions.length !== 2 ||
      new Set(value.regions.map(r => r.regionId)).size !== 2 || !regionalIds.every(id => value.regions.some(r => r.regionId === id))) throw new Error('INVALID_REGIONAL_SNAPSHOT')
  const ids = new Set<string>()
  for (const region of value.regions) {
    validateSnapshot(region, runId, region.regionId)
    if (Math.abs(region.simulationTimeSeconds - value.simulationTimeSeconds) > .001) throw new Error('REGIONAL_CLOCK_MISMATCH')
    for (const vehicle of region.vehicles) {
      if (ids.has(vehicle.id) || !vehicle.id.startsWith(`${region.regionId}:`)) throw new Error('REGIONAL_VEHICLE_ID_MISMATCH')
      ids.add(vehicle.id)
    }
  }
  for (const key of ['total', 'offline', 'online', 'idle', 'assigned', 'onTrip', 'moving'] as const) {
    if (value.regions.reduce((sum, r) => sum + r.counts[key], 0) !== value.counts?.[key]) throw new Error('REGIONAL_COUNTS_MISMATCH')
  }
  return value
}
