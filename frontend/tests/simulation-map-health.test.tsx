import { act, render } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SimulationMapHealth } from '../src/components/simulation-map-health'

const state=vi.hoisted(()=>({map:null as unknown}))
vi.mock('../src/components/ui/map',()=>({useMap:()=>({map:state.map})}))

function setup() {
  const listeners=new Map<string,(event:unknown)=>void>()
  const canvas=document.createElement('canvas')
  const map={getSource:vi.fn(()=>({})),isSourceLoaded:vi.fn(()=>true),isStyleLoaded:vi.fn(()=>false),getLayer:vi.fn(()=>({})),getCanvas:()=>canvas,getContainer:()=>document.createElement('div'),resize:vi.fn(),
    on:vi.fn((name:string,callback:(event:unknown)=>void)=>listeners.set(name,callback)),off:vi.fn()}
  state.map=map
  return {map,listeners,canvas}
}
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})})

describe('Hanoi map readiness is independent of simulation source/worker readiness',()=>{
  it('is ready when five geographic assets loaded even while the fleet source is updating',()=>{
    setup();const onChange=vi.fn()
    render(<SimulationMapHealth enabled onChange={onChange}/> )
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'ready',loaded:5}))
  })
  it('shows asset errors and unregisters map listeners on unmount',()=>{
    const {map,listeners}=setup(),onChange=vi.fn()
    const {unmount}=render(<SimulationMapHealth enabled onChange={onChange}/> )
    act(()=>listeners.get('error')!({sourceId:'streets',error:{message:'404 missing GeoJSON'}}))
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'error',message:expect.stringContaining('404 missing GeoJSON')}))
    unmount()
    expect(map.off.mock.calls.map(([name])=>name).sort()).toEqual(['error','sourcedata','styledata'])
  })
  it('does not claim ready from a canvas or from fewer than five loaded assets',()=>{
    const {map}=setup();map.isSourceLoaded.mockReturnValue(false);const onChange=vi.fn()
    render(<SimulationMapHealth enabled onChange={onChange}/> )
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'loading',loaded:0}))
  })
})
