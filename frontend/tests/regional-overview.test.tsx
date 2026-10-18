import { act, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { RegionalOverview } from '../src/components/regional-overview'
import type { RegionMetadata } from '../src/lib/api'

const state=vi.hoisted(()=>({map:null as unknown}))
vi.mock('../src/components/ui/map',()=>({useMap:()=>({map:state.map,isLoaded:true})}))
afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers()})

it('fits both geographic extents after layout/resize and never refits for playback',()=>{
  vi.useFakeTimers()
  const canvas=document.createElement('canvas'),source={setData:vi.fn()}
  let resize!:()=>void
  const disconnect=vi.fn()
  vi.stubGlobal('ResizeObserver',class {constructor(callback:()=>void){resize=callback} observe(){} disconnect=disconnect})
  const map={addSource:vi.fn(),addLayer:vi.fn(),getSource:()=>source,on:vi.fn(),off:vi.fn(),resize:vi.fn(),stop:vi.fn(),
    fitBounds:vi.fn(),getBounds:()=>({contains:()=>true}),getCanvas:()=>canvas,getContainer:()=>document.createElement('div'),
    getStyle:()=>({}),getLayer:()=>true,removeLayer:vi.fn(),removeSource:vi.fn()}
  state.map=map
  const regions:RegionMetadata[]=[
    {id:'nvmr-hanoi-core',label:'Hanoi',viewport:{center:[105.84,21.03],zoom:13,bounds:[105.802,21.002,105.875,21.055]},coverage:{operating:[105.815,21.012,105.855,21.045],routing:null,render:null},ready:true,mapReady:true,state:'ready',reason:''},
    {id:'nvmr-bac-ninh-core',label:'Bac Ninh',viewport:{center:[106.06,21.18],zoom:12,bounds:[106,21.13,106.12,21.23]},coverage:{operating:[106.02,21.15,106.1,21.21],routing:null,render:null},ready:true,mapReady:true,state:'ready',reason:''},
  ]
  const onSelect=vi.fn(),view=render(<RegionalOverview regions={regions} snapshot={null} onSelect={onSelect}/>)
  act(()=>vi.advanceTimersByTime(30))
  expect(map.resize).toHaveBeenCalledOnce()
  expect(map.fitBounds).toHaveBeenCalledWith([[105.802,21.002],[106.12,21.23]],{padding:40,duration:0})
  expect(canvas.dataset.regionalOverviewContainsBoth).toBe('true')
  view.rerender(<RegionalOverview regions={regions} snapshot={null} onSelect={()=>{}}/>)
  expect(map.fitBounds).toHaveBeenCalledOnce()
  act(()=>resize())
  expect(map.fitBounds).toHaveBeenCalledTimes(2)
  view.unmount();expect(disconnect).toHaveBeenCalledOnce();expect(canvas.dataset.regionalOverviewContainsBoth).toBeUndefined()
})
