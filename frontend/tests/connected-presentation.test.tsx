import { fireEvent, render, screen, waitFor, act } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { Dialog } from '@base-ui/react/dialog'
import { ConnectedRunDialog } from '../src/components/connected-run-dialog'
import { ConnectedFleetChart } from '../src/components/connected-fleet-chart'
import { api, ApiError } from '../src/lib/api'

vi.mock('../src/lib/api',async original=>({...await original<typeof import('../src/lib/api')>(),api:vi.fn()}))
const mocked=vi.mocked(api)
const areas=vi.hoisted(()=>vi.fn())
vi.mock('../src/components/ui/chart',()=>({ChartContainer:({children}:{children:React.ReactNode})=><div data-testid="chart-container">{children}</div>,ChartTooltip:()=>null,ChartTooltipContent:()=>null,ChartLegend:()=>null,ChartLegendContent:()=>null}))
vi.mock('recharts',()=>({AreaChart:({data,children}:{data:unknown;children:React.ReactNode})=><div data-testid="area-chart" data-series={JSON.stringify(data)}>{children}</div>,Area:(p:unknown)=>{areas(p);return null},CartesianGrid:()=>null,XAxis:()=>null,YAxis:()=>null}))
const raw=(id:string)=>({runId:id,fleetSize:2,durationSeconds:20,transitionPointCount:2,sampled:false,points:[{timeSeconds:0,OFFLINE:1,IDLE:1,ASSIGNED:0,ON_TRIP:0},{timeSeconds:20,OFFLINE:0,IDLE:1,ASSIGNED:0,ON_TRIP:1}]})
beforeEach(()=>{vi.clearAllMocks()})
const dialog=(open=vi.fn())=>render(<Dialog.Root open><Dialog.Portal><ConnectedRunDialog busy={false} onOpen={open} onClose={()=>{}}/></Dialog.Portal></Dialog.Root>)
it('lists completed Connected runs and opens a selection without enqueueing',async()=>{
 const onOpen=vi.fn();mocked.mockResolvedValue({jobs:[{id:'saved-100',status:'COMPLETED',config:{schemaVersion:'gsm-nvmr-connected-scenario/v1',fleetSize:100,bookingCount:25,seed:'saved-seed'}},{id:'queued',status:'QUEUED',config:{schemaVersion:'gsm-nvmr-connected-scenario/v1'}},{id:'other',status:'COMPLETED',config:{schemaVersion:'other'}}]})
 dialog(onOpen);fireEvent.click(await screen.findByRole('button',{name:/100 xe/}));expect(onOpen).toHaveBeenCalledWith('saved-100')
 expect(mocked).toHaveBeenCalledExactlyOnceWith('/api/v5/simulation/jobs',expect.objectContaining({signal:expect.any(AbortSignal)}))
 expect(screen.queryByText('queued')).toBeNull()
})
it('keeps manual ID entry available when listing is unavailable',async()=>{
 mocked.mockRejectedValue(new ApiError('Unavailable',503,'UNAVAILABLE'));const onOpen=vi.fn();dialog(onOpen)
 expect(await screen.findByText('Danh sách run chưa khả dụng.')).toBeVisible()
 fireEvent.change(screen.getByLabelText('Mã run Connected NVMR'),{target:{value:' manual-id '}});fireEvent.click(screen.getByRole('button',{name:'Mở run liên thông'}))
 expect(onOpen).toHaveBeenCalledWith('manual-id')
})
it('distinguishes loading, empty listing and retryable error',async()=>{
 let finish!:(data:unknown)=>void;mocked.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}))
 dialog();expect(screen.getByText('Đang tải danh sách…')).toBeVisible()
 await act(async()=>finish({jobs:[]}));expect(screen.getByText('Chưa có run hoàn tất.')).toBeVisible()
})
it('uses a bounded aggregate once per run, conserved state series and nonanimated steps',async()=>{
 mocked.mockResolvedValue(raw('chart-cache'))
 const view=render(<ConnectedFleetChart runId="chart-cache" fleetSize={2} duration={20}/>)
 expect(await screen.findByTestId('area-chart')).toHaveAttribute('data-series',JSON.stringify(raw('chart-cache').points))
 expect(areas.mock.calls.map(([p])=>p.dataKey)).toEqual(['OFFLINE','IDLE','ASSIGNED','ON_TRIP'])
 expect(areas.mock.calls.every(([p])=>p.type==='stepAfter'&&p.isAnimationActive===false&&p.stackId==='fleet')).toBe(true)
 view.rerender(<ConnectedFleetChart runId="chart-cache" fleetSize={2} duration={20}/>);view.unmount()
 render(<ConnectedFleetChart runId="chart-cache" fleetSize={2} duration={20}/>)
 expect(screen.getByTestId('area-chart')).toBeVisible();expect(mocked).toHaveBeenCalledTimes(1)
 expect(mocked.mock.calls[0][0]).toBe('/api/v5/simulation/jobs/chart-cache/analytics/fleet-states')
})
it('does not render invented chart data for invalid or missing timelines',async()=>{
 mocked.mockResolvedValue({...raw('bad-chart'),points:[]})
 render(<ConnectedFleetChart runId="bad-chart" fleetSize={2} duration={20}/>)
 expect(await screen.findByRole('alert')).toHaveTextContent('Chưa có chuỗi thời gian hợp lệ.')
 expect(screen.queryByTestId('area-chart')).toBeNull()
})
it('cancels a pending chart request when analytics closes',async()=>{
 mocked.mockImplementation(()=>new Promise(()=>{}));const view=render(<ConnectedFleetChart runId="abort-chart" fleetSize={2} duration={20}/>)
 await waitFor(()=>expect(mocked).toHaveBeenCalledTimes(1));const signal=mocked.mock.calls[0][1]?.signal
 view.unmount();expect(signal?.aborted).toBe(true)
})
