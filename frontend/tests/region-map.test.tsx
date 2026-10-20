import { render } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { SandboxMap } from '../src/components/sandbox-map'
import type { RegionViewport } from '../src/lib/api'

const mocks=vi.hoisted(()=>({
  mounted:vi.fn(),canvas:{dataset:{} as Record<string,string>},
  map:{jumpTo:vi.fn(),on:vi.fn(),off:vi.fn(),resize:vi.fn(),getContainer:()=>document.createElement('div'),getCanvas:()=>mocks.canvas},
}))
vi.mock('../src/components/ui/map',async()=>{
  const {useEffect}=await import('react')
  const Child=({children}:{children?:React.ReactNode})=><>{children}</>
  return {
    Map:({children}:{children:React.ReactNode})=>{useEffect(()=>{mocks.mounted()},[]);return <div>{children}</div>},
    useMap:()=>({map:mocks.map,isLoaded:true}),MapControls:()=>null,
    MapMarker:Child,MarkerContent:Child,MapRoute:Child,RouteProgress:Child,RouteMarker:Child,
  }
})
beforeEach(()=>{
  vi.clearAllMocks()
  vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})
})
it('applies each region viewport once, preserves the map mount and does not reset on ordinary rerenders',()=>{
  const hcm:RegionViewport={center:[106.7,10.7725],zoom:14.2,bounds:[106.675,10.75,106.725,10.795]}
  const hanoi:RegionViewport={center:[105.85,21.025],zoom:11.5,bounds:[105.75,20.95,105.95,21.1]}
  const base={dataset:null,start:null,end:null,route:null,progress:0,enabled:false,onSelect:vi.fn(),onError:vi.fn()}
  const {rerender}=render(<SandboxMap {...base} regionId="hcm-center" viewport={hcm}/>)
  expect(mocks.map.jumpTo).toHaveBeenLastCalledWith({center:hcm.center,zoom:hcm.zoom})
  rerender(<SandboxMap {...base} regionId="nvmr-hanoi-core" viewport={hanoi}/>)
  expect(mocks.map.jumpTo).toHaveBeenLastCalledWith({center:hanoi.center,zoom:hanoi.zoom})
  const calls=mocks.map.jumpTo.mock.calls.length
  rerender(<SandboxMap {...base} regionId="nvmr-hanoi-core" viewport={{...hanoi,center:[...hanoi.center]}}/>)
  expect(mocks.map.jumpTo).toHaveBeenCalledTimes(calls)
  rerender(<SandboxMap {...base} regionId="hcm-center" viewport={hcm}/>)
  expect(mocks.map.jumpTo).toHaveBeenLastCalledWith({center:hcm.center,zoom:hcm.zoom})
  expect(mocks.mounted).toHaveBeenCalledTimes(1)
})
