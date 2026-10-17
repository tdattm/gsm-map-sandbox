import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from '../src/App'
import recorded from '../../docs/nvmr/m2-evidence/mixed-plan.json'

vi.mock('../src/lib/use-region',()=>({useRegion:()=>({regionId:'nvmr-hanoi-core',regions:[{id:'nvmr-hanoi-core',label:'Hanoi fixture'}],
  metadata:{label:'Hanoi fixture'},selectRegion:vi.fn(),connectionError:'',dataset:{ready:true,state:'ready',
    pbf:{state:'present_verified',format_verified:true},artifacts:{map_ready:true,graph_ready:true},osrm:{state:'connected'},
    region:{name:'Hanoi fixture',routing_bbox:[105.76,20.96,105.92,21.10],display_bbox:[105.80,21.00,105.88,21.06]}}})}))
vi.mock('../src/components/sandbox-map',()=>({SandboxMap:(p:{enabled:boolean;vehicleType:string;onSelect:(point:[number,number])=>void})=><div data-testid="mode-map" data-type={p.vehicleType}>
  <button disabled={!p.enabled} onClick={()=>p.onSelect([105.84,21.03])}>Fixture A</button>
  <button disabled={!p.enabled} onClick={()=>p.onSelect([105.85,21.04])}>Fixture B</button>
</div>}))
const response=(data:unknown)=>({ok:true,json:async()=>data})
describe('M2 mode selector orchestration (mock map)',()=>{
  it('keeps unavailable MOTORBIKE selected, blocks live actions, and preserves CAR availability',async()=>{
    const fetcher=vi.fn(async()=>response({regionId:'nvmr-hanoi-core',modes:[{vehicleType:'MOTORBIKE',ready:false,reason:'fixture unavailable'}]}))
    vi.stubGlobal('fetch',fetcher);render(<App/> )
    expect(screen.getByRole('button',{name:'Fixture A'})).toBeEnabled()
    fireEvent.change(screen.getByLabelText('Loại dịch vụ'),{target:{value:'MOTORBIKE'}})
    await waitFor(()=>expect(fetcher).toHaveBeenCalled())
    expect(screen.getByLabelText('Loại dịch vụ')).toHaveValue('MOTORBIKE')
    expect(screen.getByRole('button',{name:'Fixture A'})).toBeDisabled()
    expect(screen.getByText(/MOTORBIKE NOT READY/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Loại dịch vụ'),{target:{value:'CAR'}})
    expect(screen.getByRole('button',{name:'Fixture A'})).toBeEnabled()
    expect(fetcher.mock.calls).toHaveLength(1)
  })
  it('routes MOTORBIKE explicitly and cancels late geometry after switching back to CAR',async()=>{
    let finish!:(value:unknown)=>void,signal!:AbortSignal
    const fetcher=vi.fn((url:string,options:RequestInit)=>url.endsWith('/modes') ? Promise.resolve(response({regionId:'nvmr-hanoi-core',modes:[
      {vehicleType:'MOTORBIKE',ready:true,routingIdentity:recorded.routingIdentities.MOTORBIKE}]})) : new Promise(resolve=>{finish=resolve;signal=options.signal as AbortSignal}))
    vi.stubGlobal('fetch',fetcher);render(<App/> )
    const map=screen.getByTestId('mode-map')
    fireEvent.change(screen.getByLabelText('Loại dịch vụ'),{target:{value:'MOTORBIKE'}})
    await waitFor(()=>expect(screen.getByRole('button',{name:'Fixture A'})).toBeEnabled())
    fireEvent.click(screen.getByRole('button',{name:'Fixture A'}));fireEvent.click(screen.getByRole('button',{name:'Fixture B'}))
    await waitFor(()=>expect(finish).toBeDefined())
    expect(fetcher.mock.calls.at(-1)?.[0]).toBe('/api/v2/regions/nvmr-hanoi-core/modes/MOTORBIKE/route')
    fireEvent.change(screen.getByLabelText('Loại dịch vụ'),{target:{value:'CAR'}})
    expect(signal.aborted).toBe(true)
    await act(async()=>finish(response({schemaVersion:'gsm-mode-route/v1',routingIdentity:recorded.routingIdentities.MOTORBIKE,route:{distance:9900,duration:100}})))
    expect(screen.queryByText('9,90 km')).not.toBeInTheDocument()
    expect(screen.getByTestId('mode-map')).toBe(map)
    expect(map).toHaveAttribute('data-type','CAR')
  })
})
