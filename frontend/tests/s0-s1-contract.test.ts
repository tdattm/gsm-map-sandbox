import { expect, it } from 'vitest'
import { simulationErrorText } from '../src/components/simulation-runtime'
import { fixtureSnapshot, validateSnapshot } from '../src/lib/simulation'

it('never invents fixture bookings or routes',()=>{
  const value=fixtureSnapshot(5000,100)
  expect(value.vehicles.every(v=>v.activeBookingId===null&&v.routeRef===null)).toBe(true)
  expect(validateSnapshot(value,value.runId,value.regionId)).toBe(value)
})
it('distinguishes API/proxy from graph, router and domain NoRoute errors',()=>{
  expect(simulationErrorText('API trả về HTTP 502')).toContain('Backend FastAPI chưa kết nối')
  expect(simulationErrorText('MODE_NOT_READY: graph')).toContain('Graph/profile')
  expect(simulationErrorText('ROUTER_UNAVAILABLE: refused')).toContain('Router OSRM')
  expect(simulationErrorText('NoRoute: outside')).toContain('cặp điểm')
})
