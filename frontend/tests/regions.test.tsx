import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App'
import { useRegion } from '../src/lib/use-region'
import { useBooking } from '../src/lib/use-booking'
import { useFleet } from '../src/lib/use-fleet'
import { useVoucher } from '../src/lib/use-voucher'
import { regionMapStyle } from '../src/lib/map-style'
import { exportArtifact } from '../src/lib/artifact'
import type { BookingPlan } from '../src/lib/booking'
import type { DatasetStatus, RegionMetadata } from '../src/lib/api'
import type { Experiment } from '../src/lib/voucher'
import recorded from '../../docs/evidence/a4/default.json'
import manifest from '../../contracts/replay-asset-manifest.json'

const mocks = vi.hoisted(() => ({ assets: vi.fn() }))
vi.mock('../src/lib/replay-assets', async importOriginal => ({
  ...await importOriginal<typeof import('../src/lib/replay-assets')>(), loadReplayAssets: mocks.assets,
}))
// Product orchestration is tested here. Actual WebGL/map lifetime is checked separately.
vi.mock('../src/components/sandbox-map', () => ({ SandboxMap: (props: {
  enabled: boolean; regionId: string; viewport?: { center: number[] }; onSelect: (point: [number,number]) => void
}) => <div data-testid="region-map" data-region={props.regionId} data-center={JSON.stringify(props.viewport?.center)}>
  <button disabled={!props.enabled} onClick={() => props.onSelect([106.69,10.77])}>Fixture A</button>
  <button disabled={!props.enabled} onClick={() => props.onSelect([106.7,10.78])}>Fixture B</button>
</div> }))

const hcm: RegionMetadata = { id: 'hcm-center', label: 'TP.HCM fixture',
  viewport: {center:[106.7,10.7725],zoom:14.2,bounds:[106.675,10.75,106.725,10.795]},
  coverage:{operating:[106.675,10.75,106.725,10.795],routing:[106.66,10.735,106.74,10.81],render:[106.675,10.75,106.725,10.795]},
  ready:true,mapReady:true,state:'ready',reason:'' }
const hanoi: RegionMetadata = { id:'nvmr-hanoi-core',label:'Hà Nội fixture',
  viewport:{center:[105.85,21.025],zoom:11.5,bounds:[105.75,20.95,105.95,21.1]},
  coverage:{operating:null,routing:null,render:null},ready:false,mapReady:false,state:'not_ready',reason:'Hà Nội chưa có graph CAR · M1b' }
const status = (region:RegionMetadata):DatasetStatus => ({
  regionId:region.id, viewport:region.viewport,ready:region.ready,state:region.state,readinessReason:region.reason,
  pbf:{state:region.ready?'present_verified':'not_prepared',size_bytes:null,format_verified:region.ready,osmium_available:false},
  artifacts:{map_ready:region.mapReady,graph_ready:region.ready,extracted_ready:region.ready},osrm:{state:region.ready?'connected':'not_configured'},
  region:{name:region.label,display_bbox:region.viewport.bounds,routing_bbox:region.coverage.routing,source:'fixture only',attribution:'OpenStreetMap',boundary_note:'Technical viewport fixture'},
})
const response = (value:unknown) => ({ok:true,json:async()=>value})
const fixtureRoute = {coordinates:[[106.69,10.77],[106.7,10.78]],distance:1200,duration:100,
  snap_points:[{location:[106.69,10.77],distance:0},{location:[106.7,10.78],distance:0}],duration_source:'explicit test fixture'}
const fixtureCatalog = {candidates:[{id:'a',coordinate:[106.69,10.77]},{id:'b',coordinate:[106.7,10.78]}],
  datasetFingerprint:'deliberately-same-fixture-fingerprint',provenance:{display_bbox:hcm.viewport.bounds,max_snap_meters:100}}
const fetchStatus = (url:string) => response(url==='/api/regions'?{regions:[hcm,hanoi]}:status(url.includes('nvmr-hanoi-core')?hanoi:hcm))

beforeEach(() => { window.history.replaceState({},'', '/'); mocks.assets.mockResolvedValue({manifest,layers:{}}) })
afterEach(() => { window.history.replaceState({},'', '/') })

describe('M1a region integration', () => {
  it('switches HCM → Hanoi → HCM, clears the route, preserves map DOM and ignores a late HCM route', async () => {
    let finish!:(value:unknown)=>void, signal!:AbortSignal
    const fetcher=vi.fn((url:string,options?:RequestInit)=>url==='/api/route'
      ? new Promise(resolve=>{finish=resolve;signal=options!.signal as AbortSignal}) : Promise.resolve(fetchStatus(url)))
    vi.stubGlobal('fetch',fetcher); render(<App/> )
    await waitFor(()=>expect(screen.getByRole('button',{name:'Fixture A'})).toBeEnabled())
    const map=screen.getByTestId('region-map')
    fireEvent.click(screen.getByRole('button',{name:'Fixture A'}));fireEvent.click(screen.getByRole('button',{name:'Fixture B'}))
    await waitFor(()=>expect(finish).toBeDefined())
    fireEvent.change(screen.getByLabelText('Khu vực mô phỏng'),{target:{value:hanoi.id}})
    expect(signal.aborted).toBe(true)
    await waitFor(()=>expect(screen.getAllByText(hanoi.reason).length).toBeGreaterThan(0))
    expect(screen.getByRole('button',{name:'Fixture A'})).toBeDisabled()
    expect(map).toHaveAttribute('data-center',JSON.stringify(hanoi.viewport.center))
    expect(screen.getByRole('button',{name:'Xóa điểm A/B và chọn lại'})).toBeDisabled()
    await act(async()=>finish(response({...fixtureRoute,distance:9900})))
    expect(screen.queryByText('9,90 km')).not.toBeInTheDocument()
    for (const [mode,prepare] of [['Mô phỏng đội xe','Tạo kịch bản'],['Đặt xe và điều phối','Tạo kịch bản đặt xe'],['Phòng thí nghiệm voucher','Chuẩn bị thí nghiệm']]) {
      fireEvent.click(screen.getByRole('button',{name:mode,exact:true}))
      expect(screen.getByRole('button',{name:prepare,exact:true})).toBeDisabled()
    }
    fireEvent.click(screen.getByRole('button',{name:'Một hành trình',exact:true}))
    fireEvent.change(screen.getByLabelText('Khu vực mô phỏng'),{target:{value:hcm.id}})
    await waitFor(()=>expect(screen.getByRole('button',{name:'Fixture A'})).toBeEnabled())
    expect(screen.getByTestId('region-map')).toBe(map)
    expect(map).toHaveAttribute('data-center',JSON.stringify(hcm.viewport.center))
    expect(fetcher.mock.calls.filter(([url])=>url.includes('nvmr-hanoi-core')).every(([url])=>url.endsWith('/dataset/status'))).toBe(true)
  })

  it('discards slow/out-of-order dataset responses, including a mismatched region',async()=>{
    const pending:{url:string;signal:AbortSignal;resolve:(value:unknown)=>void}[]=[]
    vi.stubGlobal('fetch',vi.fn((url:string,options:RequestInit)=>url==='/api/regions'?Promise.resolve(fetchStatus(url)):
      new Promise(resolve=>pending.push({url,signal:options.signal as AbortSignal,resolve}))))
    const {result}=renderHook(()=>useRegion(false,0))
    await waitFor(()=>expect(pending).toHaveLength(1))
    act(()=>result.current.selectRegion(hanoi.id))
    await waitFor(()=>expect(pending).toHaveLength(2))
    expect(pending[0].signal.aborted).toBe(true)
    await act(async()=>pending[1].resolve(response(status(hanoi))))
    await act(async()=>pending[0].resolve(response(status(hcm))))
    expect(result.current.dataset?.regionId).toBe(hanoi.id)
    expect(result.current.dataset?.ready).toBe(false)
    act(()=>result.current.selectRegion(hcm.id))
    await waitFor(()=>expect(pending).toHaveLength(3))
    await act(async()=>pending[2].resolve(response(status(hcm))))
    act(()=>result.current.selectRegion(hanoi.id))
    await waitFor(()=>expect(pending).toHaveLength(4))
    await act(async()=>pending[3].resolve(response(status(hcm))))
    expect(result.current.dataset).toBeNull()
    expect(result.current.connectionError).toContain('không đúng khu vực')
  })

  it('aborts Booking and Voucher preparations on a ready-to-ready region switch without replacing their clocks',async()=>{
    for(const kind of ['booking','voucher'] as const) {
      const pending:{signal:AbortSignal;resolve:(value:unknown)=>void}[]=[]
      vi.stubGlobal('fetch',vi.fn((_url:string,options:RequestInit)=>new Promise(resolve=>pending.push({signal:options.signal as AbortSignal,resolve}))))
      const {result,rerender,unmount}=renderHook(({id})=>{
        const booking=useBooking(true,true,id),voucher=useVoucher(true,true,'live',id)
        return {booking,voucher}
      },{initialProps:{id:hcm.id}})
      const clock=result.current[kind].clock
      let work!:Promise<void>
      act(()=>{ work=kind==='booking'?result.current.booking.generate(recorded.baseline.plan.config):result.current.voucher.generate(recorded.config) })
      rerender({id:hanoi.id})
      expect(pending[0].signal.aborted).toBe(true)
      await act(async()=>{pending[0].resolve(response(recorded));await work})
      expect(result.current.booking.plan).toBeNull();expect(result.current.voucher.experiment).toBeNull()
      expect(result.current[kind].clock).toBe(clock)
      expect(result.current[kind].loading).toBe(false); unmount()
    }
  })

  it('scopes Fleet cache across regions even if a fixture reuses a fingerprint',async()=>{
    const fetcher=vi.fn((url:string)=>Promise.resolve(response(url.endsWith('/fleet/candidates')?
      {...fixtureCatalog,provenance:{...fixtureCatalog.provenance,...(url.includes(hanoi.id)?{region_id:hanoi.id}:{})}}:fixtureRoute)))
    vi.stubGlobal('fetch',fetcher)
    const {result,rerender}=renderHook(({id})=>useFleet(true,true,id),{initialProps:{id:hcm.id}})
    await act(async()=>{await result.current.generate('same',1)})
    const clock=result.current.clock
    expect(result.current.scenario?.vehicles).toHaveLength(1)
    rerender({id:hanoi.id});expect(result.current.scenario).toBeNull()
    await act(async()=>{await result.current.generate('same',1)})
    expect(result.current.scenario?.routeRequests).toBe(1)
    expect(fetcher.mock.calls.some(([url])=>url===`/api/regions/${hanoi.id}/route`)).toBe(true)
    expect(result.current.clock).toBe(clock)
  })

  it('uses the new region scope for successful Booking and Voucher preparation',async()=>{
    const plan=structuredClone(recorded.baseline.plan) as unknown as BookingPlan
    plan.config.bookingCount=plan.demand.length
    plan.provenance.region_id=hanoi.id
    const experiment=structuredClone(recorded) as unknown as Experiment
    experiment.provenance.region_id=hanoi.id
    for (const arm of ['baseline','treatment'] as const) experiment[arm].plan.provenance.region_id=hanoi.id
    const fetcher=vi.fn((url:string)=>Promise.resolve(response(url.endsWith('/booking-simulation/prepare')?plan:experiment)))
    vi.stubGlobal('fetch',fetcher)
    const {result}=renderHook(()=>({booking:useBooking(true,true,hanoi.id),voucher:useVoucher(true,true,'live',hanoi.id)}))
    await act(async()=>{await result.current.booking.generate(plan.config);await result.current.voucher.generate(recorded.config)})
    expect(result.current.booking.plan?.id).toBe(plan.id)
    expect(result.current.voucher.experiment?.id).toBe(recorded.id)
    expect(fetcher.mock.calls.map(([url])=>url)).toEqual([
      `/api/regions/${hanoi.id}/booking-simulation/prepare`,`/api/regions/${hanoi.id}/voucher-experiment/prepare`])
    // These are contract fixtures, not evidence of actual Hanoi routing.
  })

  it('rejects HCM provenance returned to a new-region preparation',async()=>{
    vi.stubGlobal('fetch',vi.fn(()=>Promise.resolve(response(recorded))))
    const {result}=renderHook(()=>useVoucher(true,true,'live',hanoi.id))
    await act(async()=>{await result.current.generate(recorded.config)})
    expect(result.current.experiment).toBeNull()
    expect(result.current.error).toContain('REGION_RESPONSE_MISMATCH')
  })

  it('Saved v1 import/seek/replay is independent of selected region, backend and OSRM',async()=>{
    const artifact=await exportArtifact(recorded as unknown as Experiment,manifest.id)
    vi.stubGlobal('fetch',vi.fn(()=>{throw new Error('LIVE_FETCH_FORBIDDEN')}))
    const {result,rerender}=renderHook(({id})=>useVoucher(true,false,'saved',id),{initialProps:{id:hcm.id}})
    await act(async()=>{await result.current.loadSaved({size:JSON.stringify(artifact).length,text:async()=>JSON.stringify(artifact)} as File)})
    const experiment=result.current.experiment,clock=result.current.clock
    act(()=>clock.seek(500));rerender({id:hanoi.id})
    expect(result.current.experiment).toBe(experiment)
    expect(result.current.clock).toBe(clock);expect(clock.getSnapshot().simulationTimeSeconds).toBe(500)
    act(()=>{clock.play();clock.pause();clock.seek(0)})
    expect(result.current.experiment?.id).toBe(artifact.experimentId)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('Saved entry never requests the registry/dataset and does not select a live region',async()=>{
    window.history.replaceState({},'', '/?runtime=saved')
    vi.stubGlobal('fetch',vi.fn(()=>{throw new Error('LIVE_FETCH_FORBIDDEN')}));render(<App/> )
    await waitFor(()=>expect(screen.getByLabelText('Khu vực mô phỏng')).toBeDisabled())
    expect(screen.getByTestId('region-map')).toHaveAttribute('data-region',hcm.id)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('builds each region map source from its explicit namespace without modifying legacy style',()=>{
    const first=regionMapStyle(hcm.id),second=regionMapStyle(hanoi.id)
    expect(JSON.stringify(first.sources)).toContain('/api/regions/hcm-center/map/streets')
    expect(JSON.stringify(second.sources)).toContain('/api/regions/nvmr-hanoi-core/map/streets')
    expect(JSON.stringify(second.sources)).not.toContain('hcm-center')
  })
})
