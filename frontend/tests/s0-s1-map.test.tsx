import { act, render, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { SimulationMap, emptyTelemetry } from '../src/components/simulation-map'
import { fixtureSnapshot } from '../src/lib/simulation'
import type { SelectedJourney, SimulationRoute } from '../src/lib/simulation'

const {map, sources, layers, icons, listeners}=vi.hoisted(()=>{
  const sources=new Map<string,{setData:ReturnType<typeof vi.fn>}>(),layers=new Map<string,unknown>(),icons=new Set<string>(),listeners=new Map<string,Set<unknown>>()
  const map={
    getStyle:vi.fn<()=>unknown>(()=>({version:8})),
    addSource:vi.fn((id:string)=>sources.set(id,{setData:vi.fn()})),getSource:(id:string)=>sources.get(id),removeSource:vi.fn((id:string)=>sources.delete(id)),
    addLayer:vi.fn((layer:{id:string})=>layers.set(layer.id,layer)),getLayer:(id:string)=>layers.get(id),removeLayer:vi.fn((id:string)=>layers.delete(id)),
    hasImage:(id:string)=>icons.has(id),removeImage:vi.fn((id:string)=>icons.delete(id)),
    getCanvas:()=>({dataset:{mapLifetime:'test'}}),
    queryRenderedFeatures:vi.fn(()=>[] as {id:string|number;properties:Record<string,unknown>}[]),
    on:vi.fn((name:string,cb:unknown)=>{if(!listeners.has(name))listeners.set(name,new Set());listeners.get(name)!.add(cb)}),
    off:vi.fn((name:string,cb:unknown)=>listeners.get(name)?.delete(cb)),
  }
  return {map,sources,layers,icons,listeners}
})
vi.mock('../src/components/ui/map',()=>({useMap:()=>({map,isLoaded:true})}))
vi.mock('../src/lib/simulation-map-icons',()=>({iconKinds:['car','motorbike','passenger','pickup','dropoff'],registerMobilityIcons:async()=>{for(const k of ['car','motorbike','passenger','pickup','dropoff'])icons.add(`gsm-${k}`)}}))
afterEach(()=>{sources.clear();layers.clear();icons.clear();listeners.clear();vi.clearAllMocks()})

it('renders native silhouettes, keeps authoritative selected positions, and cleans up on remount',async()=>{
  const telemetry={current:emptyTelemetry()},a=fixtureSnapshot(100),selected=a.vehicles[3].id
  const props={snapshot:a,selectedId:selected,route:null,onSelect:vi.fn(),telemetry}
  const view=render(<SimulationMap {...props}/>)
  await waitFor(()=>expect(view.queryByRole('status')).toBeNull())
  const layer=layers.get('m4-vehicles') as {type:string;layout:Record<string,unknown>}
  expect(layer.type).toBe('symbol');expect(layer.layout['icon-image']).toContain('gsm-motorbike')
  const source=sources.get('m4-selection')!,next=structuredClone(a)
  next.vehicles[3].position=[105.81,21.02];next.simulationTimeSeconds=10
  await act(async()=>view.rerender(<SimulationMap {...props} snapshot={next}/>))
  expect(source.setData.mock.calls.at(-1)?.[0].geometry.coordinates).toEqual(next.vehicles[3].position)
  expect(source.setData.mock.calls).toHaveLength(2) // No RAF-generated chord points.
  view.unmount()
  expect(sources.size).toBe(0);expect(layers.size).toBe(0);expect(icons.size).toBe(0)
  expect([...listeners.values()].every(set=>set.size===0)).toBe(true)
  const again=render(<SimulationMap {...props}/>);await waitFor(()=>expect(icons.size).toBe(5));again.unmount()
  expect([...listeners.values()].every(set=>set.size===0)).toBe(true)
})

it('uses waiting-passenger only in pickup phase and clears both legs for idle selection',async()=>{
  const s=fixtureSnapshot(100),v=s.vehicles[3],telemetry={current:emptyTelemetry()}
  v.serviceState='ASSIGNED';v.activeBookingId='booking'
  const route=(ref:string):SimulationRoute=>({schemaVersion:'gsm-simulation-route/v1',runId:s.runId,regionId:s.regionId,routeRef:ref,routingIdentity:s.routingIdentities.CAR,coordinates:[[105.8,21],[105.81,21.01]],distance:100,duration:10})
  const journey={detail:{pickup:[105.8,21],dropoff:[105.81,21.01]},pickupRoute:route('pickup'),tripRoute:route('trip')} as SelectedJourney
  const props={snapshot:s,selectedId:v.id,route:journey.pickupRoute,journey,onSelect:vi.fn(),telemetry}
  const view=render(<SimulationMap {...props}/>);await waitFor(()=>expect(view.queryByRole('status')).toBeNull())
  const stops=()=>sources.get('s1-stops')!.setData.mock.calls.at(-1)?.[0].features
  expect(stops()[0].properties.kind).toBe('passenger')
  const next=structuredClone(s);next.vehicles[3].serviceState='ON_TRIP'
  await act(async()=>view.rerender(<SimulationMap {...props} snapshot={next}/>))
  expect(stops()[0].properties.kind).toBe('pickup')
  expect(stops()[0].properties.label).toContain('đã đón')
  await act(async()=>view.rerender(<SimulationMap {...props} snapshot={next} selectedId={s.vehicles[1].id} journey={null} route={null}/>))
  expect(stops()).toEqual([])
  expect(sources.get('s1-journey')!.setData.mock.calls.at(-1)?.[0].features).toEqual([])
})

it('can unmount after its parent already removed the MapLibre style',async()=>{
  const view=render(<SimulationMap snapshot={null} selectedId={null} route={null} onSelect={vi.fn()} telemetry={{current:emptyTelemetry()}}/> )
  await waitFor(()=>expect(view.queryByRole('status')).toBeNull())
  map.getStyle.mockReturnValueOnce(undefined)
  sources.clear();layers.clear();icons.clear() // Parent map.remove() already disposed them.
  expect(()=>view.unmount()).not.toThrow()
  expect([...listeners.values()].every(set=>set.size===0)).toBe(true)
})

it('resolves native overlay hits to current vehicle IDs and bounds overlap candidates',async()=>{
  const snapshot=fixtureSnapshot(100),onSelect=vi.fn(),onCandidates=vi.fn()
  const view=render(<SimulationMap snapshot={snapshot} selectedId={snapshot.vehicles[0].id} route={null} onSelect={onSelect} onCandidates={onCandidates} telemetry={{current:emptyTelemetry()}}/> )
  await waitFor(()=>expect(view.queryByRole('status')).toBeNull())
  map.queryRenderedFeatures.mockReturnValue([
    {id:0,properties:{id:snapshot.vehicles[0].id}},
    {id:1,properties:{id:'unknown'}},
    ...snapshot.vehicles.map((v,i)=>({id:i,properties:{id:v.id}})),
  ])
  const click=[...listeners.get('click')!][0] as (e:{point:[number,number]})=>void
  await act(async()=>click({point:[0,0]}))
  expect(onSelect).toHaveBeenLastCalledWith(snapshot.vehicles[0].id)
  expect(onCandidates).toHaveBeenLastCalledWith(snapshot.vehicles.slice(0,30).map(v=>v.id))
  map.queryRenderedFeatures.mockReturnValue([{id:0,properties:{id:'unknown'}}])
  await act(async()=>click({point:[0,0]}))
  expect(onSelect).toHaveBeenCalledTimes(1)
  expect(onCandidates).toHaveBeenLastCalledWith([])
  view.unmount()
})
