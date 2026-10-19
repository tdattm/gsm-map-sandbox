import { act, render } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { ConnectedCamera, ConnectedMapHealth } from '../src/components/connected-map'
import { api } from '../src/lib/api'

const state=vi.hoisted(()=>({map:null as unknown,loaded:true}))
vi.mock('../src/components/ui/map',()=>({useMap:()=>({map:state.map,isLoaded:state.loaded})}))
vi.mock('../src/lib/api',()=>({api:vi.fn()}))
const mocked=vi.mocked(api)
function setup() {
  const listeners=new Map<string,(event:unknown)=>void>(),canvas=document.createElement('canvas')
  const map={getSource:vi.fn(()=>({})),isSourceLoaded:vi.fn(()=>true),getLayer:vi.fn(()=>({})),getCanvas:()=>canvas,getContainer:()=>document.createElement('div'),resize:vi.fn(),fitBounds:vi.fn(),on:vi.fn((name:string,callback:(event:unknown)=>void)=>listeners.set(name,callback)),off:vi.fn()}
  state.map=map;return {map,listeners,canvas}
}
beforeEach(()=>{vi.clearAllMocks();state.loaded=true;vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})})
it('reports initial artifact failure before the MapLibre load event can fire',async()=>{
  const {listeners}=setup();state.loaded=false
  mocked.mockResolvedValue({ready:false,reason:'Basemap incomplete'});const onChange=vi.fn()
  await act(async()=>{render(<ConnectedMapHealth onChange={onChange}/>)})
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'error',message:expect.stringContaining('Basemap incomplete')}))
  expect(listeners.has('error')).toBe(true)
})
it('requires manifest readiness even when map source reports loaded',async()=>{
  setup();mocked.mockResolvedValue({ready:false,reason:'INCOMPLETE'});const onChange=vi.fn()
  await act(async()=>{render(<ConnectedMapHealth onChange={onChange}/> )})
  expect(onChange.mock.calls.some(([v])=>v.state==='ready')).toBe(false)
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'error',message:expect.stringContaining('INCOMPLETE')}))
})
it('reports local viewport tiles ready independently of worker and shows later tile errors',async()=>{
  const {map,listeners}=setup();mocked.mockResolvedValue({ready:true});const onChange=vi.fn();let unmount!:()=>void
  await act(async()=>{({unmount}=render(<ConnectedMapHealth onChange={onChange}/>))})
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'ready',loaded:1}))
  act(()=>listeners.get('error')!({sourceId:'connected-basemap',error:{message:'503 CONNECTED_MAP_NOT_READY'}}))
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'error',message:expect.stringContaining('503')}))
  unmount();expect(map.off.mock.calls.map(([key])=>key).sort()).toEqual(['error','sourcedata','styledata'])
})
it('keeps loading until current viewport source is loaded',async()=>{
  const {map}=setup();map.isSourceLoaded.mockReturnValue(false);mocked.mockResolvedValue({ready:true});const onChange=vi.fn()
  await act(async()=>{render(<ConnectedMapHealth onChange={onChange}/>)})
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'loading',loaded:0}))
})
it('explicit retry remount rereads artifact readiness and recovers a previous missing-artifact error',async()=>{
  setup();mocked.mockResolvedValueOnce({ready:false,reason:'Missing manifest'}).mockResolvedValueOnce({ready:true});const onChange=vi.fn();let rerender!:(element:React.ReactNode)=>void
  await act(async()=>{({rerender}=render(<ConnectedMapHealth key={0} onChange={onChange}/>))})
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'error'}))
  await act(async()=>rerender(<ConnectedMapHealth key={1} onChange={onChange}/>))
  expect(mocked).toHaveBeenCalledTimes(2)
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({state:'ready'}))
})
it('fits continuous coverage once without refitting on ordinary rerenders',()=>{
  const {map}=setup();vi.stubGlobal('requestAnimationFrame',(callback:FrameRequestCallback)=>{callback(0);return 1});vi.stubGlobal('cancelAnimationFrame',vi.fn())
  const {rerender}=render(<ConnectedCamera/>);rerender(<ConnectedCamera/>)
  expect(map.fitBounds).toHaveBeenCalledExactlyOnceWith([[104.35,20.06],[107.25,22.85]],{padding:35,duration:0})
})
