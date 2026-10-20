import { useMemo, useRef, useState } from 'react'
import { Dialog } from '@base-ui/react/dialog'
import { ApplicationBrand, ApplicationMenuButton } from './application-shell'
import { ConnectedRunDialog } from './connected-run-dialog'
import { ConnectedFleetChart } from './connected-fleet-chart'
import { ConnectedReplayDiagnostics } from './connected-replay-diagnostics'
import { Button } from './ui/button'
import { Map, MapControls } from './ui/map'
import { PlaybackDock } from './playback-dock'
import { SimulationMap, emptyTelemetry } from './simulation-map'
import { SimulationMapBoundary, type MapHealth } from './simulation-map-health'
import { simulationErrorText } from './simulation-runtime'
import { ConnectedMapHealth, ConnectedCamera } from './connected-map'
import { MobilityIcon } from './mobility-icon'
import { connectedMapStyle, connectedInitialCamera } from '@/lib/map-style'
import { allocationTotals, defaultAllocations, filterConnectedSnapshot, zoneIds, zoneLabel, type ConnectedKpis, type ZoneId } from '@/lib/connected-simulation'
import { useConnectedSimulation } from '@/lib/use-connected-simulation'
import { useFleetClock } from '@/lib/use-fleet'
import { legProgress } from '@/lib/simulation'
import { initialPresentationProfile, presentationPolicy, type PresentationProfile } from '@/lib/simulation-profile'

const stateLabels: Record<string,string> = {total:'Tổng xe',online:'Online',offline:'Offline',idle:'Rảnh',assigned:'Đến đón',onTrip:'Chở khách',moving:'Di chuyển'}
const statuses: Record<string,string> = {QUEUED:'Đang chờ worker',RUNNING:'Đang tính mô phỏng liên thông',COMPLETED:'Đã lưu kết quả',FAILED:'Không hoàn thành',CANCELLED:'Đã hủy',INTERRUPTED:'Bị gián đoạn'}

export default function ConnectedWorkspace() {
  const developer=new URLSearchParams(window.location.search).get('dev')==='1'
  const [analytics,setAnalytics]=useState(false),[openRun,setOpenRun]=useState(false)
  const [profile,setProfile]=useState<PresentationProfile>(initialPresentationProfile)
  const session=useConnectedSimulation(profile), telemetry=useRef(emptyTelemetry())
  const [allocations,setAllocations]=useState(()=>defaultAllocations()),[weights,setWeights]=useState<Record<ZoneId,number>>({hanoi:1,'bac-ninh':1,'hung-yen':1,'phu-tho':1,'thai-nguyen':1})
  const [seed,setSeed]=useState('r1b-connected-research-v1'),[bookingCount,setBookingCount]=useState(100),[horizon,setHorizon]=useState(900),[maxWait,setMaxWait]=useState(300),[online,setOnline]=useState(.8),[demandCar,setDemandCar]=useState(.4),[crossZone,setCrossZone]=useState(.25)
  const [query,setQuery]=useState(''),[zone,setZone]=useState(''),[mode,setMode]=useState(''),[candidates,setCandidates]=useState<string[]>([]),[mapRetry,setMapRetry]=useState(0)
  const [health,setHealth]=useState<MapHealth>({state:'loading',message:'Đang tải vector tiles cục bộ…',loaded:0,milliseconds:0})
  const totals=allocationTotals(allocations),busy=session.loading || !!session.job && ['QUEUED','RUNNING'].includes(session.job.status)
  const styles=useMemo(()=>{const style=connectedMapStyle(mapRetry);return {light:style,dark:style}},[mapRetry])
  const visible=useMemo(()=>filterConnectedSnapshot(session.snapshot,zone,mode),[session.snapshot,zone,mode])
  const matches=(session.snapshot?.vehicles??[]).filter(v=>v.id.toLowerCase().includes(query.toLowerCase()))
  const vehicle=session.vehicle,detail=session.journey?.detail
  const allocationValid=totals.fleetSize>=1&&totals.fleetSize<=5000&&allocations.every(r=>Number.isInteger(r.carCount)&&r.carCount>=0&&Number.isInteger(r.motorbikeCount)&&r.motorbikeCount>=0)
  const update=(index:number,key:'carCount'|'motorbikeCount',value:number)=>setAllocations(rows=>rows.map((r,i)=>i===index?{...r,[key]:value}:r))
  const select=(id:string)=>{setZone('');setMode('');session.selectVehicle(id)}
  const loadedConfig=session.result?.config??session.job?.config
  const loadedTotal=typeof loadedConfig?.fleetSize==='number'?loadedConfig.fleetSize:session.snapshot?.counts.total
  const loadedCars=typeof loadedConfig?.carCount==='number'?loadedConfig.carCount:(session.snapshot?session.snapshot.vehicles.filter(v=>v.vehicleType==='CAR').length:undefined)
  const loadedBikes=loadedTotal!==undefined&&loadedCars!==undefined?loadedTotal-loadedCars:undefined
  return <div className={`simulation-shell connected-workspace ${analytics?'analytics-open':'map-first'} ${developer?'connected-developer':''}`} data-testid="connected-workspace">
    <header className="connected-header"><div className="connected-header-identity"><ApplicationMenuButton/><ApplicationBrand compact subtitle="Mô phỏng quy mô lớn · NVMR v5"/></div><div className="connected-header-actions"><Button variant="outline" onClick={()=>setOpenRun(true)}>Mở run</Button><Button variant={analytics?'secondary':'outline'} aria-expanded={analytics} aria-controls="connected-analytics" onClick={()=>setAnalytics(v=>!v)}>Analytics</Button></div></header>
    <Dialog.Root open={openRun} onOpenChange={setOpenRun}><Dialog.Portal><Dialog.Backdrop className="sheet-backdrop"/><ConnectedRunDialog busy={busy} onOpen={id=>void session.open(id)} onClose={()=>setOpenRun(false)}/></Dialog.Portal></Dialog.Root>
    {!analytics&&<dl className="connected-kpi-strip" data-testid="connected-kpi-strip">{([['Tổng xe',loadedTotal],['CAR',loadedCars],['MOTORBIKE',loadedBikes],['Yêu cầu',session.result?.counts.requested??(typeof loadedConfig?.bookingCount==='number'?loadedConfig.bookingCount:undefined)]] as [string,number|undefined][]).map(([label,value])=><div key={label}><dt>{label}</dt><dd>{typeof value==='number'?value.toLocaleString('vi-VN'):'—'}</dd></div>)}</dl>}
    {session.error&&<div role="alert" className="connected-error">{simulationErrorText(session.error)} <Button variant="outline" onClick={session.retry}>Thử lại</Button></div>}
    {session.job?.error&&<p role="alert" className="connected-error">{typeof session.job.error==='string'?session.job.error:`${session.job.error.code}: ${session.job.error.message}`}</p>}
    {(session.loading||session.job&&['QUEUED','RUNNING'].includes(session.job.status))&&<div role="status" className="connected-error">{session.loading?'Đang tải…':statuses[session.job!.status]} {session.job&&<><progress max={1} value={session.job.progress}/><Button onClick={()=>void session.cancel()}>Hủy</Button></>}</div>}

    <div className="connected-layout"><aside id="connected-analytics" className="simulation-panel connected-analytics" hidden={!analytics&&!developer} aria-label="Analytics Connected NVMR">
      <Button className="connected-close-analytics" variant="outline" onClick={()=>setAnalytics(false)}>Đóng Analytics</Button>
      {developer&&<>
      <section className="simulation-card"><h2>Thiết lập mô phỏng mới</h2>
        <form onSubmit={e=>{e.preventDefault();void session.create({schemaVersion:'gsm-nvmr-connected-scenario/v1',seed,fleetSize:totals.fleetSize,carCount:totals.carCount,bookingCount,horizonSeconds:horizon,maxWaitSeconds:maxWait,onlineFraction:online,fleetAllocations:allocations,demandWeights:weights,demandCarFraction:demandCar,crossZoneDemandFraction:crossZone})}}>
          <label>Chế độ sử dụng<select aria-label="Chế độ Connected NVMR" value={profile} onChange={e=>setProfile(e.target.value as PresentationProfile)}><option value="standard">Standard</option><option value="meeting">Meeting · tiết kiệm cập nhật</option><option value="benchmark">Benchmark</option></select></label>
          <p className="small-note" data-testid="connected-presentation-policy">{profile} · snapshot tối đa mỗi {presentationPolicy[profile].snapshotMs} ms · đồng hồ {presentationPolicy[profile].clockHz} Hz. Tần suất hiển thị không thay đổi kết quả mô phỏng đã lưu.</p>
          <label>Quy mô mặc định<select aria-label="Connected fleet preset" value="" onChange={e=>setAllocations(defaultAllocations(+e.target.value))}><option value="" disabled>Chọn để đặt lại phân bổ 80/20</option>{[100,500,1000,5000].map(n=><option key={n} value={n}>{n.toLocaleString('vi-VN')} xe</option>)}</select></label>
          <p className="small-note">Mặc định 80% xe ở Hà Nội, mỗi vùng vệ tinh 5%. Phân bổ khách độc lập; trọng số mặc định bằng nhau. Các vùng vận hành kỹ thuật có phiên bản, không phải địa giới hành chính chính thức.</p>
          {allocations.map((row,index)=><fieldset key={row.zoneId} className="regional-allocation"><legend>{zoneLabel(row.zoneId)}</legend><div className="simulation-form-grid"><label>CAR<input aria-label={`${row.zoneId} CAR connected`} type="number" min={0} max={5000} required value={row.carCount} onChange={e=>update(index,'carCount',+e.target.value)}/></label><label>MOTORBIKE<input aria-label={`${row.zoneId} MOTORBIKE connected`} type="number" min={0} max={5000} required value={row.motorbikeCount} onChange={e=>update(index,'motorbikeCount',+e.target.value)}/></label></div><label>Trọng số nhu cầu<input aria-label={`${row.zoneId} demand weight`} type="number" min={0} step={.1} required value={weights[row.zoneId]} onChange={e=>setWeights(w=>({...w,[row.zoneId]:+e.target.value}))}/></label></fieldset>)}
          <p data-testid="connected-allocation-total"><strong>{totals.fleetSize.toLocaleString('vi-VN')}/5.000 xe</strong> · {totals.carCount} CAR · {totals.motorbikeCount} MOTORBIKE</p>
          <label>Seed<input aria-label="Connected seed" required maxLength={80} value={seed} onChange={e=>setSeed(e.target.value)}/></label>
          <div className="simulation-form-grid"><label>Số yêu cầu<input type="number" min={0} max={20000} required value={bookingCount} onChange={e=>setBookingCount(+e.target.value)}/></label><label>Thời gian sinh yêu cầu (s)<input type="number" min={1} max={86400} required value={horizon} onChange={e=>setHorizon(+e.target.value)}/></label><label>Chờ đón tối đa (s)<input type="number" min={0} max={3600} required value={maxWait} onChange={e=>setMaxWait(+e.target.value)}/></label><label>Tỷ lệ online<input type="number" min={0} max={1} step={.05} required value={online} onChange={e=>setOnline(+e.target.value)}/></label><label>Tỷ lệ nhu cầu CAR<input type="number" min={0} max={1} step={.05} required value={demandCar} onChange={e=>setDemandCar(+e.target.value)}/></label><label>Tỷ lệ OD xuyên vùng<input type="number" min={0} max={1} step={.05} required value={crossZone} onChange={e=>setCrossZone(+e.target.value)}/></label></div>
          {!allocationValid&&<p role="alert">Phân bổ phải là số nguyên không âm; tổng từ 1 đến 5.000 xe.</p>}
          <Button type="submit" disabled={busy||!allocationValid||Object.values(weights).reduce((a,b)=>a+b,0)<=0}>Tạo mô phỏng liên thông</Button>
        </form>
      </section></>}
      {session.result?<section className="simulation-card"><h2>Kết quả run</h2>{session.result.kpis?<FinalKpis kpis={session.result.kpis.global}/>:<p>{session.result.counts.requested} yêu cầu · {session.result.counts.completed} hoàn tất · {session.result.counts.unserved} không phục vụ</p>}</section>:<p>Chưa có kết quả run.</p>}
      {analytics&&session.result&&<ConnectedFleetChart key={session.result.runId} runId={session.result.runId} fleetSize={session.result.config.fleetSize} duration={session.result.simulationDurationSeconds}/>}
      {session.result?.kpis&&<section className="simulation-card"><KpiComparison title="Theo vùng" rows={Object.entries(session.result.kpis.byZone).map(([id,kpis])=>[zoneLabel(id),kpis])}/><KpiComparison title="Theo loại xe" rows={Object.entries(session.result.kpis.byMode)}/></section>}
      {session.snapshot&&<details className="simulation-card connected-current-fleet"><summary>Đội xe hiện tại · {session.snapshot.counts.total} xe</summary><Counts counts={session.snapshot.counts}/><p data-testid="connected-conservation">Bảo toàn {session.snapshot.vehicles.length}/{session.snapshot.counts.total} xe · đang hiển thị {visible?.vehicles.length??0}</p>{Object.entries(session.snapshot.zoneCounts).map(([id,counts])=><details key={id}><summary>{zoneLabel(id)} · {counts.total} xe</summary><Counts counts={counts}/></details>)}</details>}
      <section className="simulation-card"><h2>Xe và hành trình</h2><label>Tìm global vehicle ID<input aria-label="Tìm connected vehicle ID" value={query} onChange={e=>setQuery(e.target.value)}/></label>
<div className="simulation-vehicle-results">{matches.slice(0,12).map(v=><button key={v.id} aria-pressed={v.id===session.selectedId} onClick={()=>select(v.id)}><MobilityIcon kind={v.vehicleType==='CAR'?'car':'motorbike'}/>{v.id} · {zoneLabel(v.currentZoneId)}</button>)}</div>
        {candidates.length>1&&<details><summary>Xe tại vị trí vừa nhấp ({candidates.length})</summary>{candidates.map(id=><button key={id} onClick={()=>select(id)}>{id}</button>)}</details>}
        {vehicle&&<><h3>{vehicle.id}</h3><p>{vehicle.vehicleType} · {vehicle.serviceState}</p><p>Vùng gốc: {zoneLabel(vehicle.homeZoneId)}<br/>Vùng hiện tại: {zoneLabel(vehicle.currentZoneId)}</p><p>Booking: {vehicle.activeBookingId??'Không có'}</p><Button variant="outline" onClick={()=>telemetry.current.focus(vehicle.id)}>Theo dõi vị trí xe</Button><Button variant="outline" disabled={!detail} onClick={()=>telemetry.current.focusTrip()}>Xem toàn hành trình</Button></>}
        {session.detailLoading&&<p role="status">Đang đọc tuyến đã lưu…</p>}{session.routeError&&<p role="alert">{session.routeError}<Button onClick={session.retry}>Thử lại chi tiết</Button></p>}
        {detail&&<div data-testid="connected-journey"><h3>{detail.bookingId} · {detail.serviceType}</h3>{[detail.pickupLeg,detail.tripLeg].map(leg=><div key={leg.phase}><strong>{leg.phase==='pickup'?'Đến đón · nét đứt':'Chở khách · nét liền'}</strong><p>{leg.distance.toFixed(1)} m · {leg.duration.toFixed(1)} s</p><progress aria-label={`Connected ${leg.phase} progress`} max={1} value={legProgress(leg,session.snapshot?.simulationTimeSeconds??0)}/></div>)}</div>}
      </section>
      {new URLSearchParams(window.location.search).get('audit')==='1'&&<ConnectedReplayDiagnostics session={session} telemetry={telemetry} closeAnalytics={()=>setAnalytics(false)}/>}
    </aside>
    <section className="simulation-map-area" aria-label="Bản đồ miền Bắc liên thông">
      <div className="connected-filters"><label><span className="sr-only">Lọc operating zone</span><select aria-label="Lọc operating zone" value={zone} onChange={e=>setZone(e.target.value)}><option value="">Toàn vùng</option>{zoneIds.map(id=><option key={id} value={id}>{zoneLabel(id)}</option>)}<option value="outside-operating-zones">Ngoài operating zones</option></select></label><label><span className="sr-only">Lọc loại xe</span><select aria-label="Lọc loại xe connected" value={mode} onChange={e=>setMode(e.target.value)}><option value="">CAR + MOTORBIKE</option><option value="CAR">CAR</option><option value="MOTORBIKE">MOTORBIKE</option></select></label></div>
      <div className="simulation-map"><SimulationMapBoundary><Map styles={styles} theme="light" center={connectedInitialCamera.center} zoom={connectedInitialCamera.zoom} attributionControl={{compact:false}}><MapControls showCompass/><ConnectedCamera/><ConnectedMapHealth key={mapRetry} onChange={setHealth}/><SimulationMap snapshot={visible} selectedId={session.selectedId} route={session.route} journey={session.journey} onSelect={select} onCandidates={setCandidates} telemetry={telemetry}/></Map></SimulationMapBoundary>{health.state==='error'&&<div className="simulation-map-notice" role="alert">{health.message}<Button variant="outline" onClick={()=>setMapRetry(n=>n+1)}>Thử lại bản đồ</Button></div>}{!session.snapshot&&!session.loading&&!session.job&&<div className="connected-empty" role="status">Chưa mở run v5</div>}<div className="simulation-legend" aria-label="Chú giải loại xe"><span className="legend-car"><MobilityIcon kind="car"/> CAR</span><span className="legend-bike"><MobilityIcon kind="motorbike"/> MOTORBIKE</span></div></div>
    </section></div><ConnectedPlayback session={session}/>
  </div>
}
function Counts({counts}:{counts:Record<string,number>|undefined}) {return counts?<dl className="simulation-kpis">{Object.entries(counts).map(([key,value])=><div key={key}><dt>{stateLabels[key]??key}</dt><dd>{value.toLocaleString('vi-VN')}</dd></div>)}</dl>:<p>Chưa có snapshot.</p>}
function FinalKpis({kpis}:{kpis:ConnectedKpis}) {return <dl className="simulation-kpis"><div><dt>Yêu cầu</dt><dd>{kpis.counts.requested}</dd></div><div><dt>Hoàn tất</dt><dd>{kpis.counts.completed}</dd></div><div><dt>Không phục vụ</dt><dd>{kpis.counts.unserved}</dd></div><div><dt>Chờ đón trung bình</dt><dd>{kpis.pickupWait.meanSeconds===null?'—':`${kpis.pickupWait.meanSeconds.toFixed(1)} s`}</dd></div><div><dt>Bận / thời gian online</dt><dd>{kpis.utilization.busyFractionOfOnline===null?'—':`${(100*kpis.utilization.busyFractionOfOnline).toFixed(1)}%`}</dd></div></dl>}
function ConnectedPlayback({session}:{session:ReturnType<typeof useConnectedSimulation>}) {const clock=useFleetClock(session.clock);return <PlaybackDock compact label="Phát lại toàn miền Bắc liên thông" enabled={!!session.snapshot} time={clock.simulationTimeSeconds} duration={session.result?.simulationDurationSeconds??0} speed={clock.speedMultiplier} status={clock.playbackStatus} play={session.clock.play} pause={session.clock.pause} reset={()=>session.seek(0)} seek={session.seek} setSpeed={session.clock.setSpeed}/>}

function KpiComparison({title,rows}:{title:string;rows:[string,ConnectedKpis][]}) {
  if (!rows.length) return null
  return <div className="connected-comparison"><h3>{title}</h3><table><thead><tr><th scope="col">Nhóm</th><th scope="col">Xe</th><th scope="col">Yêu cầu</th><th scope="col">Hoàn tất</th><th scope="col">Không phục vụ</th></tr></thead><tbody>{rows.map(([id,k])=><tr key={id}><th scope="row">{id}</th><td>{k.fleetSize}</td><td>{k.counts.requested}</td><td>{k.counts.completed}</td><td>{k.counts.unserved}</td></tr>)}</tbody></table></div>
}
