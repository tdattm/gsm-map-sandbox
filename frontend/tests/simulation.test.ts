import { describe, expect, it } from 'vitest'
import { fixtureSnapshot, SnapshotGate, validateSnapshot, validateSimulationRoute, vehicleFeatures, type SimulationRoute } from '../src/lib/simulation'

describe('M3/M4 snapshot boundary',()=>{
  it('uses deterministic WGS84 stable IDs and conservative counts at every fixture scale',()=>{
    for(const n of [100,500,1000,3000,5000]) {
      const a=fixtureSnapshot(n,0),b=fixtureSnapshot(n,20)
      expect(validateSnapshot(a,a.runId,a.regionId)).toBe(a)
      expect(validateSnapshot(b,b.runId,b.regionId)).toBe(b)
      expect(a.vehicles.map(v=>v.id)).toEqual(b.vehicles.map(v=>v.id))
      expect(a.vehicles.filter(v=>v.vehicleType==='CAR')).toHaveLength(n*.4)
      expect(a).toEqual(fixtureSnapshot(n,0))
      expect(vehicleFeatures(a).features.map(f=>f.id)).toEqual(a.vehicles.map(v=>v.id))
      expect(a.vehicles.every(v=>v.routeRef===null)).toBe(true)
    }
  })
  it('rejects duplicates, bad coordinates/counts, missing assignment and wrong graph scope',()=>{
    const snapshot=()=>fixtureSnapshot(100)
    for(const mutate of [
      (s:ReturnType<typeof snapshot>)=>{s.vehicles[1].id=s.vehicles[0].id},
      (s:ReturnType<typeof snapshot>)=>{s.vehicles[1].position=[200,20]},
      (s:ReturnType<typeof snapshot>)=>{s.counts.total++},
      (s:ReturnType<typeof snapshot>)=>{s.vehicles[3].activeBookingId='fabricated'},
      (s:ReturnType<typeof snapshot>)=>{s.routingIdentities.CAR.regionId='hcm-center'},
      (s:ReturnType<typeof snapshot>)=>{s.counts.moving=101},
      (s:ReturnType<typeof snapshot>)=>{delete (s.counts as Partial<typeof s.counts>).moving},
      (s:ReturnType<typeof snapshot>)=>{s.runId='live-run';s.routingIdentities.CAR.algorithm='none'},
    ]) {const s=snapshot();mutate(s);expect(()=>validateSnapshot(s,s.runId,s.regionId)).toThrow()}
  })
  it('rejects stale/out of order/same snapshots and cross-run/region; explicit seek creates new epoch',()=>{
    const gate=new SnapshotGate('fixture-100','nvmr-hanoi-core'),a=fixtureSnapshot(100,10),b=fixtureSnapshot(100,20)
    expect(gate.accept(a)).toBe(true);expect(gate.accept(a)).toBe(false);expect(gate.accept(b)).toBe(true);expect(gate.accept(a)).toBe(false)
    expect(()=>gate.accept(fixtureSnapshot(500,30))).toThrow()
    expect(new SnapshotGate(a.runId,a.regionId).accept(fixtureSnapshot(100,0))).toBe(true)
    expect(()=>new SnapshotGate(a.runId,'hcm-center').accept(a)).toThrow()
  })
  it('accepts only selected immutable run route with matching complete provenance',()=>{
    const s=fixtureSnapshot(100),v=s.vehicles[3];v.routeRef='abc123'
    const route:SimulationRoute={schemaVersion:'gsm-simulation-route/v1',runId:s.runId,regionId:s.regionId,routeRef:v.routeRef,routingIdentity:s.routingIdentities[v.vehicleType],coordinates:[[105.8,21],[105.81,21.01]],distance:1500,duration:100}
    expect(validateSimulationRoute(route,s,v)).toBe(route)
    expect(()=>validateSimulationRoute({...route,runId:'other'},s,v)).toThrow()
    expect(()=>validateSimulationRoute({...route,routeRef:'different'},s,v)).toThrow()
    expect(()=>validateSimulationRoute({...route,routingIdentity:{...route.routingIdentity,graphManifestSha256:'other'}},s,v)).toThrow()
  })
})
