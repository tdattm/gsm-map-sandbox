import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import ConnectedWorkspace from '../src/components/connected-workspace'

const mocks=vi.hoisted(()=>({profile:vi.fn(),create:vi.fn(),open:vi.fn(),select:vi.fn(),map:vi.fn(),seek:vi.fn(),clockSnapshot:{simulationTimeSeconds:0,speedMultiplier:1,playbackStatus:'paused' as const}}))
vi.mock('../src/lib/use-connected-simulation',()=>({useConnectedSimulation:(profile:string)=>{mocks.profile(profile);return ({
  loading:false,job:null,result:null,error:'',routeError:'',detailLoading:false,selectedId:null,journey:null,route:null,vehicle:null,create:mocks.create,open:mocks.open,selectVehicle:mocks.select,seek:mocks.seek,retry:vi.fn(),cancel:vi.fn(),
  clock:{getSnapshot:()=>mocks.clockSnapshot,subscribe:()=>()=>{},play:vi.fn(),pause:vi.fn(),setSpeed:vi.fn()},
  snapshot:{schemaVersion:'gsm-nvmr-connected-snapshot/v1',runId:'global',regionId:'nvmr-connected',simulationTimeSeconds:0,sequenceNumber:0,routingIdentities:{},counts:{total:2,online:2,offline:0,idle:2,assigned:0,onTrip:0,moving:0},zoneCounts:{hanoi:{total:1,online:1,offline:0,idle:1,assigned:0,onTrip:0,moving:0},'bac-ninh':{total:1,online:1,offline:0,idle:1,assigned:0,onTrip:0,moving:0}},vehicles:[{id:'GLOBAL-HANOI',vehicleType:'CAR',homeZoneId:'hanoi',currentZoneId:'hanoi',serviceState:'IDLE',isMoving:false,position:[105.8,21.02]},{id:'GLOBAL-BACNINH',vehicleType:'MOTORBIKE',homeZoneId:'bac-ninh',currentZoneId:'bac-ninh',serviceState:'IDLE',isMoving:false,position:[106.0,21.1]}]},
})}}))
vi.mock('../src/components/ui/map',()=>({Map:({children}:{children:React.ReactNode})=><div data-testid="one-map">{children}</div>,MapControls:()=>null}))
vi.mock('../src/components/connected-map',()=>({ConnectedCamera:()=>null,ConnectedMapHealth:()=>null}))
vi.mock('../src/components/simulation-runtime',()=>({SimulationRuntime:()=>null,simulationErrorText:(s:string)=>s}))
vi.mock('../src/components/simulation-map',()=>({emptyTelemetry:()=>({focus:vi.fn(),focusTrip:vi.fn()}),SimulationMap:(props:unknown)=>{mocks.map(props);return null}}))
beforeEach(()=>{vi.clearAllMocks();window.history.replaceState(null,'','/')})
it('submits exact global 5000 allocation while demand defaults equal independently',()=>{
  render(<ConnectedWorkspace/>);expect(screen.getAllByTestId('one-map')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button',{name:'Tạo mô phỏng liên thông'}))
  const config=mocks.create.mock.calls[0][0]
  expect(config.fleetSize).toBe(5000);expect(config.carCount).toBe(2000);expect(config.motorbikeCount).toBeUndefined()
  expect(config.fleetAllocations.map((r:{carCount:number;motorbikeCount:number})=>r.carCount+r.motorbikeCount)).toEqual([4000,250,250,250,250])
  expect(Object.values(config.demandWeights)).toEqual([1,1,1,1,1])
  fireEvent.change(screen.getByLabelText('Connected fleet preset'),{target:{value:'100'}})
  fireEvent.click(screen.getByRole('button',{name:'Tạo mô phỏng liên thông'}));expect(mocks.create.mock.calls[1][0].fleetSize).toBe(100)
})
it('filters map data across zones without changing global conservation and searches globally',()=>{
  render(<ConnectedWorkspace/>);expect(screen.getByTestId('connected-conservation')).toHaveTextContent('2/2')
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
  fireEvent.change(screen.getByLabelText('Mã run Connected NVMR'),{target:{value:'connected-previous'}})
  fireEvent.click(screen.getByRole('button',{name:'Mở run liên thông',hidden:true}))
  expect(mocks.open).toHaveBeenCalledWith('connected-previous')
})

it('honors launcher meeting URL and updates presentation cadence without a new simulation',()=>{
  window.history.replaceState(null,'','/?runtime=simulation&scenario=connected&profile=meeting')
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
