import { useEffect, useMemo, useRef, useState } from 'react'
import { Button } from './ui/button'
import { Map, MapControls } from './ui/map'
import { PlaybackDock } from './playback-dock'
import { SimulationMap, emptyTelemetry } from './simulation-map'
import { SimulationMapBoundary, SimulationMapHealth, type MapHealth } from './simulation-map-health'
import { useSimulation } from '@/lib/use-simulation'
import { useFleetClock } from '@/lib/use-fleet'
import { emptyStyle, localStyle, regionMapStyle } from '@/lib/map-style'
import { MobilityIcon } from './mobility-icon'
import { SimulationRuntime, simulationErrorText } from './simulation-runtime'
import { legProgress } from '@/lib/simulation'
import { initialPresentationProfile, presentationPolicy, type PresentationProfile } from '@/lib/simulation-profile'
import RegionalWorkspace from './regional-workspace'
import ConnectedWorkspace from './connected-workspace'

const scales=[100,500,1000,3000,5000]
const countLabels:Record<string,string>={total:'Tổng đội xe',online:'Online',offline:'Offline',idle:'Rảnh',assigned:'Đang đến đón',onTrip:'Đang chở khách',moving:'Đang di chuyển'}
const stateLabels:Record<string,string>={OFFLINE:'Offline',IDLE:'Rảnh',ASSIGNED:'Đang đến đón',ON_TRIP:'Đang chở khách'}
const statuses:Record<string,string>={QUEUED:'Đang chờ worker',RUNNING:'Đang tính toán',COMPLETED:'Đã tính xong',FAILED:'Không hoàn thành',CANCELLED:'Đã hủy',INTERRUPTED:'Bị gián đoạn'}
export default function SimulationWorkspace({previousRegion}:{previousRegion:string}) {
  const currentScenario=()=>{const value=new URLSearchParams(window.location.search).get('scenario');return value==='regional'||value==='connected'?value:'hanoi'}
  const [scenario,setScenario]=useState(currentScenario)
  useEffect(()=>{const sync=()=>setScenario(currentScenario());window.addEventListener('popstate',sync);return ()=>window.removeEventListener('popstate',sync)},[])
  const select=(value:string)=>{const url=new URL(window.location.href);if(value==='hanoi')url.searchParams.delete('scenario');else url.searchParams.set('scenario',value);window.history.pushState(null,'',url);setScenario(value);window.dispatchEvent(new PopStateEvent('popstate'))}
  if (scenario==='connected') return <ConnectedWorkspace/>
  return <div className="simulation-container"><div className="simulation-scenario-selector"><label>Kịch bản mô phỏng<select aria-label="Kịch bản mô phỏng" value={scenario} onChange={e=>select(e.target.value)}><option value="connected">Miền Bắc liên thông · Connected NVMR v5</option><option value="hanoi">Hanoi Core · legacy v3</option><option value="regional">Hanoi + Bắc Ninh Core · historical v4</option></select></label><p className="small-note">Lưu mã run trước khi đổi kịch bản. Job đã gửi vẫn được worker xử lý.</p></div>{scenario==='connected'?<ConnectedWorkspace/>:scenario==='regional'?<RegionalWorkspace/>:<HanoiSimulationWorkspace previousRegion={previousRegion}/>}</div>
}
function HanoiSimulationWorkspace({previousRegion}:{previousRegion:string}){
  const [profile,setProfile]=useState<PresentationProfile>(initialPresentationProfile)
  const session=useSimulation(profile),telemetry=useRef(emptyTelemetry())
  const clock=session.clock.getSnapshot()
  const query=useMemo(()=>new URLSearchParams(window.location.search),[])
  const [size,setSize]=useState(()=>{const n=Number(query.get('fleet'));return scales.includes(n)?n:100}),[carCount,setCarCount]=useState(()=>Math.round((Number(query.get('fleet'))||100)*.4)),[bookings,setBookings]=useState(20),[online,setOnline]=useState(.8),[seed,setSeed]=useState('m4-ux-pilot')
  const [horizon,setHorizon]=useState(900),[wait,setWait]=useState(300),[workload,setWorkload]=useState('typical'),[openId,setOpenId]=useState(''),[blank,setBlank]=useState(false),[retryMap,setRetryMap]=useState(0)
  const [mapHealth,setMapHealth]=useState<MapHealth>({state:'loading',message:'Đang tải bản đồ Hà Nội…',loaded:0,milliseconds:0})
  const [measurement,setMeasurement]=useState<Record<string,unknown>|null>(null),[measuring,setMeasuring]=useState(false),[seconds,setSeconds]=useState(30),[fixtureSize,setFixtureSize]=useState(100),[history,setHistory]=useState<Record<string,unknown>[]>([]),[queuedSeconds,setQueuedSeconds]=useState(0)
  const [benchmarkPan,setBenchmarkPan]=useState(true),[benchmarkPlay,setBenchmarkPlay]=useState(true)
  const mounted=useRef(true)
  const [vehicleQuery,setVehicleQuery]=useState(''),[vehicleFilter,setVehicleFilter]=useState('ACTIVE'),[candidates,setCandidates]=useState<string[]>([])
  useEffect(()=>{setCandidates([]);setVehicleQuery('')},[session.snapshot?.runId])
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false}},[])
  const styles=useMemo(()=>{
    const style=blank?{...emptyStyle,'font-faces':localStyle['font-faces']}:regionMapStyle('nvmr-hanoi-core')
    if(!blank&&retryMap)for(const source of Object.values(style.sources))if(source.type==='geojson'&&typeof source.data==='string')source.data+=`?retry=${retryMap}`
    return {light:style,dark:style}
  },[blank,retryMap])
  useEffect(()=>{if(query.get('fixture')==='1')session.fixture(size)},[]) // Explicit developer deep link only.
  useEffect(()=>{setQueuedSeconds(0);if(session.job?.status!=='QUEUED')return;const begun=Date.now(),timer=window.setInterval(()=>setQueuedSeconds(Math.floor((Date.now()-begun)/1000)),1000);return ()=>clearInterval(timer)},[session.job?.id,session.job?.status])
  const busy=measuring||session.loading||!!session.job&&['QUEUED','RUNNING'].includes(session.job.status),c=session.snapshot?.counts,vehicle=session.vehicle
  const jobError=session.job?.error?(typeof session.job.error==='string'?session.job.error:`${session.job.error.code}: ${session.job.error.message}`):''
  const matches=session.snapshot?.vehicles.filter(v=>(vehicleFilter==='ALL'||vehicleFilter==='ACTIVE'&&['ASSIGNED','ON_TRIP'].includes(v.serviceState)||v.serviceState===vehicleFilter)&&v.id.toLowerCase().includes(vehicleQuery.toLowerCase()))??[]
  const detail=session.journey?.detail
  const measure=async(series=false)=>{
    setMeasuring(true);setMeasurement(null)
    const wasPlaying=clock.playbackStatus==='playing',healthAtStart=mapHealth
    try {
      const rows:Record<string,unknown>[]=[]
      for(const zoom of series?[11,13,16]:[null]) {
        if(!mounted.current)break
        if(benchmarkPlay)session.clock.play();else session.clock.pause()
        if(zoom!==null)telemetry.current.zoomTo(zoom,zoom>=14)
        await new Promise<void>(resolve=>window.setTimeout(resolve,700))
        if(!mounted.current)break
        const row=await telemetry.current.measure(seconds,()=>{session.clock.pause();return session.clock.getSnapshot().simulationTimeSeconds},{pan:benchmarkPan})
        rows.push({...row,basemap:blank?'OFF':'HANOI_LOCAL_ON',mapHealth:healthAtStart})
      }
      if(mounted.current){setMeasurement(series?{series:rows}:rows[0]??null);setHistory(old=>[...old,...rows].slice(-100))}
    }catch(e){if(mounted.current)setMeasurement({error:e instanceof Error?e.message:String(e)})}finally{if(mounted.current){if(wasPlaying)session.clock.play();else session.clock.pause();setMeasuring(false)}}
  }
  const download=()=>{const blob=new Blob([JSON.stringify(history,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='m4-browser-measurements.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
  return <div className="simulation-shell">
    <div className="simulation-layout">
      <aside className="simulation-panel" aria-label="Cấu hình mô phỏng quy mô lớn">
        <section className="simulation-card"><span className="eyebrow">KỊCH BẢN MÔ HÌNH</span><h2>Mô phỏng quy mô lớn</h2>
          <p className="simulation-region">Hanoi Core · CAR + MOTORBIKE</p><p className="small-note">Hiện chỉ hỗ trợ Hà Nội. Khu vực ở chế độ cũ ({previousRegion}) được giữ lại khi quay về. Bản đồ dưới đây luôn là Hà Nội.</p>
          <p className="small-note">Tính toán trước, phát lại sau. Vị trí mô phỏng, không phải GPS trực tiếp.</p>
          <p className="small-note">5.000 xe là stress case Hanoi Core, chưa phải phân bổ trên toàn NVMR. Mở rộng vùng là nhiệm vụ R1.</p>
        </section>
        <section className="simulation-card"><h2>Thiết lập mô phỏng mới</h2>
        <label>Chế độ sử dụng<select aria-label="Chế độ sử dụng" value={profile} disabled={measuring} onChange={e=>{const next=e.target.value as PresentationProfile;setProfile(next);const url=new URL(window.location.href);url.searchParams.set('profile',next);window.history.replaceState(null,'',url)}}><option value="standard">Standard</option><option value="meeting">Meeting · tiết kiệm cập nhật</option><option value="benchmark">Benchmark</option></select></label>
        <p className="small-note">{profile==='meeting'?'Meeting: snapshot tối đa 4 lần/giây, đồng hồ hiển thị 10 Hz. Phù hợp thử 10–100 xe; số xe, booking, seed và thuật toán không bị thay đổi.':'Standard/Benchmark: snapshot tối đa 10 lần/giây, đồng hồ hiển thị 30 Hz.'} Khi tạm dừng và thời gian không đổi, không poll snapshot. Meeting chưa phải chứng nhận Google Meet.</p>
        <form onSubmit={e=>{e.preventDefault();setMeasurement(null);void session.create(size,bookings,online,seed,{carCount,horizonSeconds:horizon,maxWaitSeconds:wait,workload})}}>
          <div className="simulation-form-grid"><label>Tổng đội xe<input aria-label="Tổng đội xe" type="number" min="1" max="5000" required value={size} onChange={e=>{const n=Number(e.target.value);setSize(n);setCarCount(Math.min(carCount,n))}}/></label>
          <label>Số xe CAR<input aria-label="Số xe CAR" type="number" min="0" max={size} required value={carCount} onChange={e=>setCarCount(+e.target.value)}/></label></div>
          <p className="simulation-mix">{carCount} CAR + {size-carCount} MOTORBIKE</p>
          <div className="simulation-form-grid"><label>Số yêu cầu<input aria-label="Số yêu cầu" type="number" min="0" max="20000" required value={bookings} onChange={e=>setBookings(+e.target.value)}/></label>
          <label>Tỷ lệ online<input aria-label="Tỷ lệ online" type="number" min="0" max="1" step=".05" required value={online} onChange={e=>setOnline(+e.target.value)}/></label></div>
          <label>Seed<input aria-label="Seed" required value={seed} onChange={e=>setSeed(e.target.value)}/></label>
          <details><summary>Tham số nhu cầu</summary><label>Thời gian sinh yêu cầu (giây)<input type="number" required min="1" max="86400" value={horizon} onChange={e=>setHorizon(+e.target.value)}/></label><label>Chờ đón tối đa (giây)<input type="number" required min="0" max="3600" value={wait} onChange={e=>setWait(+e.target.value)}/></label><label>Phân bố nhu cầu<select value={workload} onChange={e=>setWorkload(e.target.value)}><option value="low">Thưa (low)</option><option value="typical">Thông thường (typical)</option><option value="burst">Dồn đầu kỳ (burst)</option></select></label></details>
          <Button className="simulation-submit" disabled={busy} type="submit">{session.loading?'Đang gửi yêu cầu…':'Tạo mô phỏng'}</Button>
        </form>
        <details><summary>Mở run đã có</summary><form onSubmit={e=>{e.preventDefault();setMeasurement(null);void session.open(openId)}}><label>Mã run<input aria-label="Mã run" required value={openId} onChange={e=>setOpenId(e.target.value)}/></label><Button variant="outline" disabled={busy} type="submit">Mở kết quả</Button></form></details>
        </section>
        <section className="simulation-card"><h2>Tiến trình</h2><div role="status" aria-live="polite" className={`simulation-status status-${session.job?.status??'EMPTY'}`}>{session.loading?'Đang kết nối API…':session.job?`${statuses[session.job.status]} · ${session.job.status}`:'Chưa có mô phỏng · thiết lập kịch bản để bắt đầu'}</div>
        <SimulationRuntime intervalMs={presentationPolicy[profile].healthMs}/>
        {session.job&&<><progress max="1" value={session.job.progress} aria-label="Tiến trình tính toán"/><p className="small-note">{Math.round(session.job.progress*100)}% · {session.job.id}</p></>}
        {session.job?.status==='QUEUED'&&<p className="small-note">Chờ {queuedSeconds} giây. {queuedSeconds>=10?'Worker có thể chưa chạy hoặc đang xử lý job khác. Kiểm tra terminal worker và cùng thư mục store.':'Job đã được lưu, chờ worker nhận.'} UI không có heartbeat để xác nhận worker đang hoạt động.</p>}
        {session.job?.config&&<details><summary>Cấu hình run và seed đã lưu</summary><pre>{JSON.stringify(session.job.config,null,2)}</pre></details>}
        {session.job?.status==='RUNNING'&&<p>Đang chuẩn bị tuyến / tính toán. Chưa có kết quả cuối để phát lại.</p>}
        {session.job?.status==='COMPLETED'&&!session.result&&!session.error&&<p role="status">Đang tải kết quả run…</p>}
        {session.result&&!session.snapshot&&!session.error&&<p role="status">Đang tải snapshot theo thời điểm phát lại…</p>}
        {jobError&&<p role="alert" className="error-text">{simulationErrorText(jobError)} {jobError.includes('RESOURCE_STOP')?'RAM khả dụng dưới ngưỡng an toàn. Giải phóng bộ nhớ trước khi tạo run khác. ':''}{jobError} Tạo run mới sau khi khắc phục.</p>}
        {session.error&&<div role="alert" className="error-text">{simulationErrorText(session.error)} {session.error}{session.job?<Button variant="outline" onClick={session.retry}>Thử lại dữ liệu run</Button>:<p>Không tự gửi lại POST: kết nối có thể mất sau khi server đã nhận job. Kiểm tra store/job ID trước khi tạo lại.</p>}</div>}
        {session.job&&['QUEUED','RUNNING'].includes(session.job.status)&&<Button variant="outline" onClick={()=>void session.cancel()}>Hủy job</Button>}
        <Button variant="ghost" onClick={()=>{session.reset();setMeasurement(null)}} disabled={measuring}>Xóa phiên hiển thị</Button><p className="small-note">Rời chế độ chỉ dừng phát lại và requests của màn hình; job đã gửi vẫn được worker xử lý. Hãy lưu mã run hoặc hủy job trước khi rời.</p>
        </section>
        <section className="simulation-card"><h2>Đội xe tại thời điểm phát lại</h2>
        {c?<dl className="simulation-kpis">{Object.entries(c).map(([key,value])=><div key={key}><dt>{countLabels[key]}</dt><dd>{value.toLocaleString('vi-VN')}</dd></div>)}</dl>:<p>Chưa có snapshot. Tạo hoặc mở run để xem đội xe.</p>}
        <p className="small-note">Tổng = Offline + Online. Online = Rảnh + Đến đón + Chở khách. Đang di chuyển là tập con của xe đến đón/chở khách.</p>
        {session.result&&<div className="simulation-final"><h3>Kết quả cuối toàn run</h3><p>{session.result.counts.requested} yêu cầu · {session.result.counts.assigned} đã gán · {session.result.counts.completed} hoàn tất · {session.result.counts.unserved} không phục vụ</p><p className="small-note">Không phải số booking hoàn tất tại thời điểm playback. Contract hiện chưa cung cấp số đó.</p></div>}
        {session.fixtureSize!==null&&<p className="simulation-warning">Fixture đồ họa — không phải hành trình OSRM. Chuyển động synthetic; không có booking, hành khách hoặc tuyến nghiệp vụ.</p>}
        </section>
        <section className="simulation-card"><h2>Xe được chọn</h2>
        <label>Mã phương tiện<input aria-label="Vehicle inspector" placeholder="Nhấp xe hoặc nhập ID chính xác" value={session.selectedId??''} onChange={e=>session.setSelectedId(e.target.value||null)}/></label>
        <label>Tìm xe<input aria-label="Tìm xe" value={vehicleQuery} onChange={e=>setVehicleQuery(e.target.value)} placeholder="Một phần mã xe"/></label><label>Lọc trạng thái<select aria-label="Lọc trạng thái xe" value={vehicleFilter} onChange={e=>setVehicleFilter(e.target.value)}><option value="ACTIVE">Đến đón / Chở khách</option><option value="ALL">Tất cả</option><option value="ASSIGNED">Đang đến đón</option><option value="ON_TRIP">Đang chở khách</option><option value="IDLE">Rảnh</option><option value="OFFLINE">Offline</option></select></label>
        <p className="small-note">{matches.length} xe phù hợp · hiển thị tối đa 12. Nhập ID để thu hẹp khi xe cùng depot.</p><div className="simulation-vehicle-results">{matches.slice(0,12).map(v=><button key={v.id} onClick={()=>session.setSelectedId(v.id)} aria-pressed={session.selectedId===v.id}><MobilityIcon kind={v.vehicleType==='CAR'?'car':'motorbike'} size={22}/>{v.id} · {stateLabels[v.serviceState]}</button>)}</div>
        {candidates.length>1&&<details open><summary>Nhiều xe tại vị trí vừa nhấp ({candidates.length}, tối đa 30)</summary><div className="simulation-vehicle-results">{candidates.map(id=><button key={id} onClick={()=>session.setSelectedId(id)}>{id}</button>)}</div></details>}
        {vehicle?<><p className="simulation-vehicle-title"><MobilityIcon kind={vehicle.vehicleType==='CAR'?'car':'motorbike'}/><strong>{vehicle.id}</strong> · {vehicle.vehicleType}</p><p>{stateLabels[vehicle.serviceState]} · {vehicle.serviceState}</p><p className="small-note">Hanoi Core · t={session.snapshot?.simulationTimeSeconds.toFixed(3)} s<br/>{vehicle.routeRef?`Hướng đoạn tuyến ${vehicle.headingDegrees.toFixed(0)}°`:'Không có hướng di chuyển active'} · [{vehicle.position.map(p=>p.toFixed(6)).join(', ')}]</p><p>Booking: {vehicle.activeBookingId??'Không có'}</p><Button variant="outline" onClick={()=>telemetry.current.focus(vehicle.id)}>Theo dõi vị trí xe</Button><Button variant="outline" disabled={!detail} onClick={()=>telemetry.current.focusTrip()}>Xem toàn hành trình</Button>
        {!vehicle.activeBookingId&&<p>{session.fixtureSize!==null?'Fixture chỉ kiểm thử biểu tượng/render, không có hành trình.':`${stateLabels[vehicle.serviceState]}: không có booking/tuyến active. Dùng bộ lọc để chọn xe đang phục vụ.`}</p>}
        {session.detailLoading&&<p role="status">Đang tải booking và hai chặng đã lưu…</p>}
        {detail&&<div className="simulation-booking-detail" data-testid="selected-booking-detail"><h3>{detail.bookingId} · {detail.serviceType}</h3><p>Yêu cầu t={detail.requestTimeSeconds.toFixed(3)} s · hạn đón t={detail.pickupDeadlineSeconds.toFixed(3)} s</p><p><MobilityIcon kind={vehicle.serviceState==='ASSIGNED'?'passenger':'pickup'} size={24}/> Điểm đón [{detail.pickup.map(n=>n.toFixed(6)).join(', ')}] · {vehicle.serviceState==='ASSIGNED'?'Khách đang chờ':'Đã đón khách'}</p><p><MobilityIcon kind="dropoff" size={24}/> Điểm trả [{detail.dropoff.map(n=>n.toFixed(6)).join(', ')}]</p>{[detail.pickupLeg,detail.tripLeg].map(leg=><div key={leg.phase}><strong>{leg.phase==='pickup'?'Chặng 1 · Đến đón (nét đứt)':'Chặng 2 · Chở khách (nét liền)'}</strong><p>{vehicle.serviceState===(leg.phase==='pickup'?'ASSIGNED':'ON_TRIP')?'ACTIVE · ':''}{!leg.routeRef?'Đón tại chỗ · không có tuyến di chuyển · ':''}{leg.distance.toFixed(1)} m · {leg.duration.toFixed(1)} s</p><progress aria-label={`Tiến độ ${leg.phase}`} max={1} value={legProgress(leg,session.snapshot!.simulationTimeSeconds)}/><span> {(legProgress(leg,session.snapshot!.simulationTimeSeconds)*100).toFixed(1)}%</span><p className="small-note">t={leg.startTimeSeconds.toFixed(3)} → {leg.endTimeSeconds.toFixed(3)} s<br/>Route ref: {leg.routeRef??'Không có (stationary pickup)'}</p></div>)}<details><summary>Điểm yêu cầu gốc và provenance</summary><p>Pickup yêu cầu: {detail.requestedPickup.join(', ')}<br/>Dropoff yêu cầu: {detail.requestedDropoff.join(', ')}</p><p>Markers dùng endpoint đã snap của immutable OSRM trip.</p><pre>{JSON.stringify(detail.routingIdentity,null,2)}</pre></details></div>}
        <details><summary>Định danh tuyến active</summary><p>Route ref: {vehicle.routeRef??'Không có'}</p>{session.route&&<pre>{JSON.stringify(session.route.routingIdentity,null,2)}</pre>}</details></>:<p>{session.selectedId?'ID không có trong snapshot hiện tại.':'Nhấp cụm để phóng to, chọn một xe hoặc dùng bộ lọc xe active.'}</p>}
        {session.routeError&&<p role="alert" className="error-text">Chi tiết/tuyến không khả dụng: {session.routeError}. Không tính lại bằng graph khác.<Button variant="outline" onClick={session.retryDetail}>Thử lại chi tiết</Button></p>}
        {session.snapshot&&<details><summary>Chi tiết snapshot</summary><p className="small-note">{session.snapshot.runId} · sequence {session.snapshot.sequenceNumber}<br/>Thời gian {session.snapshot.simulationTimeSeconds.toFixed(1)} s · chênh clock {(clock.simulationTimeSeconds-session.snapshot.simulationTimeSeconds).toFixed(1)} s</p></details>}
        </section>
        <details className="simulation-card simulation-developer"><summary>Benchmark / Developer Tools</summary><p className="small-note">Đo render độc lập với throughput M3. Giữ tab foreground, không stress backend đồng thời. Theo dõi RAM/commit và paging khi tăng tải; ngưỡng tạo job theo workload được hiển thị ở Tiến trình. Nền Hà Nội mặc định bật. Mỗi zoom đo theo thời lượng chọn.</p>
        <p><a href="/performance.html" target="_blank" rel="noreferrer">Mở Performance Lab · plain RAF / MapLibre isolation</a></p>
        <label><input type="checkbox" checked={benchmarkPan} disabled={measuring} onChange={e=>setBenchmarkPan(e.target.checked)}/> Pan trong phép đo</label><label><input type="checkbox" checked={benchmarkPlay} disabled={measuring} onChange={e=>setBenchmarkPlay(e.target.checked)}/> Phát trong phép đo</label>
        <p className="small-note" data-testid="selected-detail-latency">Selected booking + hai route HTTP/validation: {session.detailLatencyMs===null?'chưa đo':`${session.detailLatencyMs.toFixed(1)} ms`}. Một sample, chưa phải p95/render latency.</p>
        <label>Quy mô fixture<select aria-label="Quy mô fixture" value={fixtureSize} onChange={e=>setFixtureSize(+e.target.value)}>{scales.map(n=><option key={n}>{n}</option>)}</select></label>
        <Button disabled={busy} variant="outline" onClick={()=>{session.fixture(fixtureSize);setMeasurement(null)}}>Tải fixture render {fixtureSize} xe</Button>
        <div className="simulation-actions">{[11,13,16].map(z=><Button key={z} variant="outline" disabled={measuring} onClick={()=>telemetry.current.zoomTo(z,z>=14)}>Zoom {z}</Button>)}</div>
        <label><input type="checkbox" checked={blank} disabled={measuring} onChange={e=>{setMapHealth({state:'loading',message:'Đang đổi nền bản đồ…',loaded:0,milliseconds:0});setBlank(e.target.checked)}}/> Nền trống (chỉ benchmark nâng cao)</label>
        <label>Thời lượng đo mỗi zoom<select aria-label="Thời lượng đo" value={seconds} onChange={e=>setSeconds(+e.target.value)}>{[5,30,60].map(n=><option key={n} value={n}>{n} giây</option>)}</select></label>
        <Button disabled={measuring||!session.snapshot||mapHealth.state==='loading'||mapHealth.state==='error'} onClick={()=>void measure()}>{measuring?'Đang đo…':`Đo WebGL ${seconds} giây`}</Button><Button disabled={measuring||!session.snapshot||mapHealth.state==='loading'||mapHealth.state==='error'} variant="outline" onClick={()=>void measure(true)}>Đo 3 zoom cho quy mô hiện tại</Button><Button variant="outline" disabled={!history.length||measuring} onClick={download}>Tải JSON số đo ({history.length})</Button>
        {measurement&&<pre className="simulation-metrics" data-testid="m4-benchmark-result">{JSON.stringify(measurement,null,2)}</pre>}
        </details>
      </aside>
      <section className="simulation-map-area" aria-label="Bản đồ mô phỏng Hà Nội"><div className="simulation-map-heading"><div><span className="eyebrow">BẢN ĐỒ CỤC BỘ · OSM</span><h2>Hà Nội · Hanoi Core</h2></div><span className={`simulation-map-status map-${mapHealth.state}`} role="status" data-testid="simulation-map-status">{mapHealth.message}</span><Button variant="outline" disabled={measuring} onClick={()=>{setMapHealth({state:'loading',message:'Đang tải lại bản đồ…',loaded:0,milliseconds:0});setRetryMap(n=>n+1)}}>Tải lại bản đồ</Button></div>
      <div className="simulation-map"><div className={`simulation-mode-banner ${session.fixtureSize!==null?'fixture':''}`} role="status">{session.fixtureSize!==null?'Fixture đồ họa — không phải hành trình OSRM':session.result?'Live Simulation · Phát lại kết quả OSRM đã lưu':'Bản đồ Hanoi Core · chưa mở kết quả Live'}</div><SimulationMapBoundary><Map styles={styles} theme="light" center={[105.84,21.04]} zoom={Number(query.get('zoom'))||13} attributionControl={{customAttribution:'© OpenStreetMap contributors · Geofabrik · ODbL 1.0',compact:false}}><MapControls showCompass/><SimulationMapHealth key={`${blank}-${retryMap}`} enabled={!blank} onChange={setMapHealth}/><SimulationMap snapshot={session.snapshot} selectedId={session.selectedId} route={session.route} journey={session.journey} onSelect={session.setSelectedId} onCandidates={setCandidates} telemetry={telemetry}/></Map></SimulationMapBoundary>
      {(mapHealth.state==='loading'||mapHealth.state==='error')&&<div className="simulation-map-notice" role={mapHealth.state==='error'?'alert':'status'}>{mapHealth.message}{mapHealth.state==='error'&&<p>Lỗi hiển thị bản đồ, độc lập với OSRM / worker. Dùng “Tải lại bản đồ” sau khi khắc phục.</p>}</div>}
      <div className="simulation-legend"><span><MobilityIcon kind="car"/> CAR</span><span><MobilityIcon kind="motorbike"/> MOTORBIKE</span><span><MobilityIcon kind="passenger"/> Chờ đón</span><span><MobilityIcon kind="dropoff"/> Trả khách</span><span>P: đến đón · T: chở khách · R: rảnh · ×/mờ: offline · vòng cam: chọn</span></div></div>
      <p className="simulation-replay-note">{mapHealth.state==='error'?'Chờ khôi phục bản đồ địa lý':session.result?'Phát lại kịch bản đã tính xong':'Bản đồ Hà Nội sẵn có trước khi tạo job'} · Nhấp cụm để phóng to, nhấp xe để xem tuyến.</p>
      </section>
    </div>
    <SimulationPlayback session={session}/>
  </div>
}

// Only the dock subscribes to the 30Hz presentation clock. The form/map shell
// updates on snapshots/job changes, rather than rendering all controls per tick.
function SimulationPlayback({session}:{session:ReturnType<typeof useSimulation>}) {
  const clock=useFleetClock(session.clock)
  return <PlaybackDock label={session.fixtureSize!==null?'Fixture render · synthetic':'Phát lại mô phỏng đã tính xong'} enabled={!!session.snapshot} time={clock.simulationTimeSeconds} duration={session.result?.simulationDurationSeconds??(session.fixtureSize!==null?3600:0)} speed={clock.speedMultiplier} status={clock.playbackStatus} play={session.clock.play} pause={session.clock.pause} reset={()=>session.seek(0)} seek={session.seek} setSpeed={session.clock.setSpeed}/>
}
