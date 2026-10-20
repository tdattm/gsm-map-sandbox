import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import App from '../src/App'
import ConnectedWorkspace from '../src/components/connected-workspace'

const mocks=vi.hoisted(()=>({empty:false, result:null as unknown,selectedId:null as string|null, profile:vi.fn(),create:vi.fn(),open:vi.fn(),select:vi.fn(),map:vi.fn(),seek:vi.fn(),clockSnapshot:{simulationTimeSeconds:0,speedMultiplier:1,playbackStatus:'paused' as const}}))
vi.mock('../src/lib/use-connected-simulation',()=>({useConnectedSimulation:(profile:string)=>{mocks.profile(profile);return ({
  loading:false,job:null,result:mocks.result,error:'',routeError:'',detailLoading:false,selectedId:mocks.selectedId,journey:null,route:null,vehicle:null,create:mocks.create,open:mocks.open,selectVehicle:mocks.select,seek:mocks.seek,retry:vi.fn(),cancel:vi.fn(),
  clock:{getSnapshot:()=>mocks.clockSnapshot,subscribe:()=>()=>{},play:vi.fn(),pause:vi.fn(),setSpeed:vi.fn()},
  snapshot:mocks.empty?null:{schemaVersion:'gsm-nvmr-connected-snapshot/v1',runId:'global',regionId:'nvmr-connected',simulationTimeSeconds:0,sequenceNumber:0,routingIdentities:{},counts:{total:2,online:2,offline:0,idle:2,assigned:0,onTrip:0,moving:0},zoneCounts:{hanoi:{total:1,online:1,offline:0,idle:1,assigned:0,onTrip:0,moving:0},'bac-ninh':{total:1,online:1,offline:0,idle:1,assigned:0,onTrip:0,moving:0}},vehicles:[{id:'GLOBAL-HANOI',vehicleType:'CAR',homeZoneId:'hanoi',currentZoneId:'hanoi',serviceState:'IDLE',isMoving:false,position:[105.8,21.02]},{id:'GLOBAL-BACNINH',vehicleType:'MOTORBIKE',homeZoneId:'bac-ninh',currentZoneId:'bac-ninh',serviceState:'IDLE',isMoving:false,position:[106.0,21.1]}]},
})}}))
vi.mock('../src/components/ui/map',()=>({Map:({children}:{children:React.ReactNode})=><div data-testid="one-map">{children}</div>,MapControls:()=>null}))
vi.mock('../src/components/connected-map',()=>({ConnectedCamera:()=>null,ConnectedMapHealth:()=>null}))
vi.mock('../src/components/simulation-runtime',()=>({SimulationRuntime:()=>null,simulationErrorText:(s:string)=>s}))
vi.mock('../src/components/simulation-map',()=>({emptyTelemetry:()=>({focus:vi.fn(),focusTrip:vi.fn()}),SimulationMap:(props:unknown)=>{mocks.map(props);return null}}))
beforeEach(()=>{vi.clearAllMocks();mocks.empty=false;mocks.result=null;mocks.selectedId=null;mocks.clockSnapshot.simulationTimeSeconds=0;window.history.replaceState(null,'','/')})
it('submits exact global 5000 allocation while demand defaults equal independently',()=>{
  window.history.replaceState(null,'','/?dev=1');render(<ConnectedWorkspace/>);expect(screen.getAllByTestId('one-map')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button',{name:'Tạo mô phỏng liên thông'}))
  const config=mocks.create.mock.calls[0][0]
  expect(config.fleetSize).toBe(5000);expect(config.carCount).toBe(2000);expect(config.motorbikeCount).toBeUndefined()
  expect(config.fleetAllocations.map((r:{carCount:number;motorbikeCount:number})=>r.carCount+r.motorbikeCount)).toEqual([4000,250,250,250,250])
  expect(Object.values(config.demandWeights)).toEqual([1,1,1,1,1])
  fireEvent.change(screen.getByLabelText('Connected fleet preset'),{target:{value:'100'}})
  fireEvent.click(screen.getByRole('button',{name:'Tạo mô phỏng liên thông'}));expect(mocks.create.mock.calls[1][0].fleetSize).toBe(100)
})
it('filters map data across zones without changing global conservation and searches globally',()=>{
  render(<ConnectedWorkspace/>);fireEvent.click(screen.getByRole('button',{name:'Analytics'}));expect(screen.getByTestId('connected-conservation')).toHaveTextContent('2/2')
  fireEvent.change(screen.getByLabelText('Lọc operating zone'),{target:{value:'bac-ninh'}})
  expect(mocks.map.mock.lastCall?.[0].snapshot.vehicles.map((v:{id:string})=>v.id)).toEqual(['GLOBAL-BACNINH'])
  expect(screen.getByTestId('connected-conservation')).toHaveTextContent('2/2 xe · đang hiển thị 1')
  fireEvent.change(screen.getByLabelText('Tìm connected vehicle ID'),{target:{value:'HANOI'}})
  fireEvent.click(screen.getByRole('button',{name:/GLOBAL-HANOI/}));expect(mocks.select).toHaveBeenCalledWith('GLOBAL-HANOI')
  expect(screen.getByLabelText('Lọc operating zone')).toHaveValue('')
  expect(mocks.map.mock.lastCall?.[0].snapshot.vehicles).toHaveLength(2)
})
it('opens immutable v5 history by ID',()=>{
  render(<ConnectedWorkspace/>)
  fireEvent.click(screen.getByRole('button',{name:'Mở run'}))
  fireEvent.change(screen.getByLabelText('Mã run Connected NVMR'),{target:{value:'connected-previous'}})
  fireEvent.click(screen.getByRole('button',{name:'Mở run liên thông',hidden:true}))
  expect(mocks.open).toHaveBeenCalledWith('connected-previous')
})

it('map selection preserves State A or B, clears filters and keeps the same map and playback',()=>{
  mocks.clockSnapshot.simulationTimeSeconds=42
  const view=render(<ConnectedWorkspace/>)
  const map=screen.getByTestId('one-map'),analytics=screen.getByRole('button',{name:'Analytics'})
  fireEvent.change(screen.getByLabelText('Lọc loại xe connected'),{target:{value:'MOTORBIKE'}})
  act(()=>mocks.map.mock.lastCall?.[0].onSelect('GLOBAL-HANOI'))
  expect(analytics).toHaveAttribute('aria-expanded','false')
  expect(screen.getByTestId('connected-kpi-strip')).toBeVisible()
  expect(mocks.select).toHaveBeenLastCalledWith('GLOBAL-HANOI')
  expect(screen.getByLabelText('Lọc loại xe connected')).toHaveValue('')
  // The real hook publishes the selected identity; ensure it reaches the same map.
  mocks.selectedId='GLOBAL-HANOI';view.rerender(<ConnectedWorkspace/>)
  expect(mocks.map.mock.lastCall?.[0].selectedId).toBe('GLOBAL-HANOI')
  fireEvent.click(analytics)
  fireEvent.change(screen.getByLabelText('Lọc operating zone'),{target:{value:'hanoi'}})
  act(()=>mocks.map.mock.lastCall?.[0].onSelect('GLOBAL-BACNINH'))
  expect(analytics).toHaveAttribute('aria-expanded','true')
  expect(screen.getByRole('complementary',{name:'Analytics Connected NVMR'})).toBeVisible()
  expect(mocks.select).toHaveBeenLastCalledWith('GLOBAL-BACNINH')
  expect(screen.getByLabelText('Lọc operating zone')).toHaveValue('')
  expect(screen.getByTestId('one-map')).toBe(map)
  expect(document.querySelector('.playback-dock')).toHaveAttribute('data-dock-time','42')
  expect(mocks.seek).not.toHaveBeenCalled()
  expect(mocks.create).not.toHaveBeenCalled()
})

it('honors launcher meeting URL and updates presentation cadence without a new simulation',()=>{
  window.history.replaceState(null,'','/?runtime=simulation&scenario=connected&profile=meeting&dev=1')
  render(<ConnectedWorkspace/>)
  expect(screen.getByLabelText('Chế độ Connected NVMR')).toHaveValue('meeting')
  expect(mocks.profile).toHaveBeenLastCalledWith('meeting')
  expect(screen.getByTestId('connected-presentation-policy')).toHaveTextContent('250 ms')
  expect(screen.getByTestId('connected-presentation-policy')).toHaveTextContent('10 Hz')
  fireEvent.change(screen.getByLabelText('Chế độ Connected NVMR'),{target:{value:'standard'}})
  expect(mocks.profile).toHaveBeenLastCalledWith('standard')
  expect(screen.getByTestId('connected-presentation-policy')).toHaveTextContent('100 ms')
  expect(mocks.create).not.toHaveBeenCalled()
})

it('keeps one map and current filters/playback across both presentation states',()=>{
  render(<ConnectedWorkspace/>)
  const map=screen.getByTestId('one-map')
  expect(screen.getByTestId('connected-kpi-strip')).toHaveTextContent('Tổng xe2CAR1MOTORBIKE1Yêu cầu—')
  expect(screen.queryByRole('button',{name:'Tạo mô phỏng liên thông'})).toBeNull()
  fireEvent.change(screen.getByLabelText('Lọc loại xe connected'),{target:{value:'MOTORBIKE'}})
  fireEvent.click(screen.getByRole('button',{name:'Analytics'}))
  expect(screen.queryByTestId('connected-kpi-strip')).toBeNull()
  expect(screen.getByRole('complementary',{name:'Analytics Connected NVMR'})).toBeVisible()
  fireEvent.change(screen.getByLabelText('Tìm connected vehicle ID'),{target:{value:'BACNINH'}})
  fireEvent.click(screen.getByRole('button',{name:'Analytics'}))
  expect(screen.getByTestId('one-map')).toBe(map)
  expect(screen.getByLabelText('Lọc loại xe connected')).toHaveValue('MOTORBIKE')
  fireEvent.click(screen.getByRole('button',{name:'Analytics'}))
  expect(screen.getByLabelText('Tìm connected vehicle ID')).toHaveValue('BACNINH')
  expect(mocks.seek).not.toHaveBeenCalled()
  expect(mocks.create).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Chú giải loại xe').parentElement).toHaveClass('simulation-map')
})

vi.mock('../src/lib/use-region',()=>({useRegion:()=>({regionId:'hcm-center',regions:[],metadata:null,dataset:null,connectionError:'',selectRegion:vi.fn()})}))
vi.mock('../src/components/sandbox-map',()=>({SandboxMap:()=> <div data-testid="legacy-map"/>}))
it('root renders Connected and history restores explicit Single Trip and Saved Replay',async()=>{
  render(<App/>);
  expect(await screen.findByTestId('connected-workspace')).toBeInTheDocument()
  const visit=(url:string)=>act(()=>{window.history.pushState(null,'',url);window.dispatchEvent(new PopStateEvent('popstate'))})
  visit('/?mode=single');expect(screen.getByTestId('legacy-map')).toBeInTheDocument()
  expect(screen.getByRole('button',{name:'Một hành trình'})).toHaveAttribute('aria-current','page')
  visit('/?runtime=saved');expect(screen.getByText('TP.HCM · phát lại đã lưu')).toBeInTheDocument()
  await act(async()=>{window.history.back();await new Promise(resolve=>setTimeout(resolve,30))})
  expect(screen.getByRole('button',{name:'Một hành trình'})).toHaveAttribute('aria-current','page')
  await act(async()=>{window.history.back();await new Promise(resolve=>setTimeout(resolve,30))})
  expect(await screen.findByTestId('connected-workspace')).toBeInTheDocument()
  await act(async()=>{window.history.forward();await new Promise(resolve=>setTimeout(resolve,30))})
  expect(screen.getByTestId('legacy-map')).toBeInTheDocument()
})
it('empty root has no invented fleet or booking counts and never creates a job',()=>{
  mocks.empty=true;render(<ConnectedWorkspace/>);
  expect(screen.getByTestId('connected-kpi-strip').querySelectorAll('dd')).toHaveLength(4)
  expect(screen.getByTestId('connected-kpi-strip').textContent).not.toMatch(/5[.,]?000/)
  expect([...screen.getByTestId('connected-kpi-strip').querySelectorAll('dd')].map(n=>n.textContent)).toEqual(['—','—','—','—'])
  expect(screen.getByText('Chưa mở run v5')).toBeVisible()
  expect(mocks.create).not.toHaveBeenCalled()
})
it('uses loaded result counts independently of filters, preserves selection and clock on snapshot updates',()=>{
  mocks.result={config:{fleetSize:2,carCount:1},counts:{requested:17,completed:12,unserved:5},simulationDurationSeconds:120}
  mocks.selectedId='GLOBAL-BACNINH';mocks.clockSnapshot.simulationTimeSeconds=42
  const {rerender}=render(<ConnectedWorkspace/>);const map=screen.getByTestId('one-map')
  expect(screen.getByTestId('connected-kpi-strip')).toHaveTextContent('Yêu cầu17')
  fireEvent.change(screen.getByLabelText('Lọc operating zone'),{target:{value:'bac-ninh'}})
  fireEvent.click(screen.getByRole('button',{name:'Analytics'}))
  expect(screen.getByText('17 yêu cầu · 12 hoàn tất · 5 không phục vụ')).toBeVisible()
  mocks.clockSnapshot.simulationTimeSeconds=43;rerender(<ConnectedWorkspace/>);
  fireEvent.click(screen.getByRole('button',{name:'Analytics'}))
  expect(screen.getByTestId('one-map')).toBe(map)
  expect(mocks.map.mock.lastCall?.[0].selectedId).toBe('GLOBAL-BACNINH')
  expect(screen.getByLabelText('Lọc operating zone')).toHaveValue('bac-ninh')
  expect(document.querySelector('.playback-dock')).toHaveAttribute('data-dock-time','43')
  expect(mocks.seek).not.toHaveBeenCalled()
})

it('uses shared navigation and opens Connected from the large-scale menu with a single header',async()=>{
  render(<App/>);await screen.findByTestId('connected-workspace')
  expect(screen.getByTestId('application-shell')).toBeInTheDocument()
  expect(document.querySelectorAll('header')).toHaveLength(1)
  const map=screen.getByTestId('one-map')
  fireEvent.click(screen.getByRole('button',{name:'Mở menu chính'}))
  expect(screen.getByRole('button',{name:'Mô phỏng quy mô lớn'})).toHaveAttribute('aria-current','page')
  fireEvent.click(screen.getByRole('button',{name:'Một hành trình'}))
  expect(await screen.findByTestId('legacy-map')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'Mô phỏng quy mô lớn'}))
  expect(await screen.findByTestId('connected-workspace')).toBeInTheDocument()
  expect(window.location.search).toBe('?runtime=simulation&scenario=connected')
  expect(document.querySelectorAll('header')).toHaveLength(1)
  const connectedMap=screen.getByTestId('one-map')
  fireEvent.click(screen.getByRole('button',{name:'Mở menu chính'}))
  fireEvent.click(screen.getByRole('button',{name:'Đóng menu'}))
  expect(screen.getByTestId('one-map')).toBe(connectedMap)
  expect(map).not.toBe(connectedMap) // Switching engine creates a session; opening menus does not.
  expect(mocks.create).not.toHaveBeenCalled()
})

it('removes the saved-run dialog backdrop before returning to analytics interaction',async()=>{
 render(<ConnectedWorkspace/>);fireEvent.click(screen.getByRole('button',{name:'Mở run'}))
 fireEvent.change(screen.getByLabelText('Mã run Connected NVMR'),{target:{value:'saved-id'}})
 fireEvent.click(screen.getByRole('button',{name:'Mở run liên thông'}))
 await waitFor(()=>expect(document.querySelector('.sheet-backdrop')).toBeNull())
 fireEvent.click(screen.getByRole('button',{name:'Analytics'}))
 expect(screen.getByRole('button',{name:'Analytics'})).toHaveAttribute('aria-expanded','true')
 expect(mocks.open).toHaveBeenCalledWith('saved-id')
})
