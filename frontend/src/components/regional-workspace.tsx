import { useMemo, useRef, useState } from 'react'
import { Button } from './ui/button'
import { Map, MapControls } from './ui/map'
import { PlaybackDock } from './playback-dock'
import { SimulationMap, emptyTelemetry } from './simulation-map'
import { SimulationMapBoundary, SimulationMapHealth, type MapHealth } from './simulation-map-health'
import { SimulationRuntime, simulationErrorText } from './simulation-runtime'
import { RegionalCamera, RegionalOverview } from './regional-overview'
import { MobilityIcon } from './mobility-icon'
import { emptyStyle, localStyle, regionMapStyle } from '@/lib/map-style'
import { allocationTotals, regionLabel, syntheticAllocation, type RegionAllocation } from '@/lib/regional-simulation'
import { useRegionalSimulation } from '@/lib/use-regional-simulation'
import { useFleetClock } from '@/lib/use-fleet'
import { legProgress } from '@/lib/simulation'
import { initialPresentationProfile, type PresentationProfile } from '@/lib/simulation-profile'

const stateLabels: Record<string,string> = {total:'Tổng đội xe', online:'Online', offline:'Offline', idle:'Rảnh', assigned:'Đến đón', onTrip:'Chở khách', moving:'Di chuyển'}
const statuses: Record<string,string> = {QUEUED:'Đang chờ worker', RUNNING:'Đang tính toán hai vùng', COMPLETED:'Đã tính xong', FAILED:'Không hoàn thành', CANCELLED:'Đã hủy', INTERRUPTED:'Bị gián đoạn'}
type Session = ReturnType<typeof useRegionalSimulation>

export default function RegionalWorkspace() {
  const [profile, setProfile] = useState<PresentationProfile>(initialPresentationProfile)
  const session = useRegionalSimulation(profile)
  const [allocation, setAllocation] = useState(syntheticAllocation)
  const [seed, setSeed] = useState('r1a-synthetic-20-v1'), [horizon, setHorizon] = useState(900), [wait, setWait] = useState(300)
  const [openId, setOpenId] = useState(''), [query, setQuery] = useState(''), [activeOnly, setActiveOnly] = useState(true)
  const [mapHealth, setMapHealth] = useState<MapHealth>({state:'loading', message:'Đang tải lớp địa lý…', loaded:0, milliseconds:0})
  const [mapRetry, setMapRetry] = useState(0), [measurement, setMeasurement] = useState<Record<string, unknown> | null>(null), [measuring, setMeasuring] = useState(false)
  const telemetry = useRef(emptyTelemetry())
  const total = allocationTotals(allocation), selectedRegion = session.regions.find(r => r.id === session.regionId)
  const overview = !selectedRegion
  const styles = useMemo(() => {
    const style = overview ? {...emptyStyle, 'font-faces':localStyle['font-faces']} : regionMapStyle(session.regionId!)
    if (!overview && mapRetry) for (const source of Object.values(style.sources)) if (source.type === 'geojson' && typeof source.data === 'string') source.data += `?retry=${mapRetry}`
    return {light:style, dark:style}
  }, [overview, session.regionId, mapRetry])
  const update = (index: number, key: keyof Omit<RegionAllocation,'regionId'>, value: number) => setAllocation(rows => rows.map((r,i) => i === index ? {...r,[key]:value} : r))
  const busy = measuring || session.loading || !!session.job && ['QUEUED','RUNNING'].includes(session.job.status)
  const allVehicles = session.snapshot?.regions.flatMap(r => r.vehicles.map(v => ({...v,regionId:r.regionId}))) ?? []
  const matches = allVehicles.filter(v => v.id.toLowerCase().includes(query.toLowerCase()) && (!activeOnly || ['ASSIGNED','ON_TRIP'].includes(v.serviceState)))
  const vehicle = session.vehicle, detail = session.journey?.detail
  const chooseRegion = (id: string | null) => {session.selectRegion(id); setMeasurement(null); setMapHealth({state:'loading',message:'Đang tải lớp địa lý…',loaded:0,milliseconds:0})}
  const measure = async () => {
    setMeasuring(true); setMeasurement(null)
    try {setMeasurement({...await telemetry.current.measure(5, () => {session.clock.pause(); return session.clock.getSnapshot().simulationTimeSeconds}, {pan:true}),regionalScenarioRunId:session.result?.runId,totalScenarioFleet:session.snapshot?.counts.total,regionId:session.regionId,presentationProfile:profile})}
    finally {setMeasuring(false)}
  }
  return <div className="simulation-shell regional-workspace" data-testid="regional-workspace">
    <header className="simulation-intro"><span className="eyebrow">R1a · NVMR REGIONAL</span><h1>Hà Nội + Bắc Ninh Core</h1><p>Một kịch bản, hai vùng, một đồng hồ phát lại. Fleet và nhu cầu synthetic; điều phối chỉ trong cùng vùng và cùng loại xe.</p></header>
    <div className="simulation-layout">
      <aside className="simulation-panel" aria-label="Cấu hình regional simulation">
        <section className="simulation-card"><h2>Thiết lập mô phỏng mới</h2><p className="small-note">Phân bổ dưới đây dùng tạo run mới. Cấu hình run đang mở nằm ở Tiến trình. Preset synthetic 20 xe · seed r1a-synthetic-20-v1 · 5 CAR + 5 MOTORBIKE mỗi vùng; không phải số liệu vận hành GSM.</p>
          <form onSubmit={event => {event.preventDefault(); void session.create({schemaVersion:'gsm-nvmr-regional-scenario/v1',seed,horizonSeconds:horizon,maxWaitSeconds:wait,regions:allocation})}}>
            <label>Chế độ sử dụng<select aria-label="Chế độ regional" value={profile} disabled={measuring} onChange={e => setProfile(e.target.value as PresentationProfile)}><option value="standard">Standard</option><option value="meeting">Meeting · tiết kiệm cập nhật</option><option value="benchmark">Benchmark</option></select></label>
            {allocation.map((row,index) => <fieldset key={row.regionId} className="regional-allocation"><legend>{regionLabel(row.regionId)}</legend>
              <div className="simulation-form-grid"><label>Tổng xe<input aria-label={`${row.regionId} tổng xe`} type="number" min={1} max={4999} required value={row.fleetSize} onChange={e => update(index,'fleetSize',+e.target.value)}/></label><label>CAR<input aria-label={`${row.regionId} CAR`} type="number" min={0} max={row.fleetSize} required value={row.carCount} onChange={e => update(index,'carCount',+e.target.value)}/></label></div>
              <p>{row.fleetSize-row.carCount} MOTORBIKE</p><div className="simulation-form-grid"><label>Yêu cầu<input aria-label={`${row.regionId} yêu cầu`} type="number" min={0} max={20000} required value={row.bookingCount} onChange={e => update(index,'bookingCount',+e.target.value)}/></label><label>Tỷ lệ online<input aria-label={`${row.regionId} online`} type="number" min={0} max={1} step={.05} required value={row.onlineFraction} onChange={e => update(index,'onlineFraction',+e.target.value)}/></label></div>
            </fieldset>)}
            <p data-testid="regional-allocation-total"><strong>{total.fleetSize}/5.000 xe tổng</strong> · {total.carCount} CAR + {total.motorbikeCount} MOTORBIKE · {total.bookingCount} yêu cầu</p>
            <label>Seed<input aria-label="Regional seed" required maxLength={80} value={seed} onChange={e => setSeed(e.target.value)}/></label>
            <div className="simulation-form-grid"><label>Thời gian sinh yêu cầu (s)<input aria-label="Regional horizon" type="number" required min={1} max={86400} value={horizon} onChange={e => setHorizon(+e.target.value)}/></label><label>Chờ đón tối đa (s)<input type="number" required min={0} max={3600} value={wait} onChange={e => setWait(+e.target.value)}/></label></div>
            {total.fleetSize>5000 && <p role="alert">Tổng hai vùng vượt 5.000 xe.</p>}
            <Button type="submit" disabled={busy || total.fleetSize>5000}>Tạo mô phỏng hai vùng</Button>
          </form>
          <details><summary>Mở regional run đã lưu</summary><form onSubmit={e => {e.preventDefault(); void session.open(openId)}}><label>Mã regional run<input aria-label="Mã regional run" required value={openId} onChange={e => setOpenId(e.target.value)}/></label><Button type="submit" disabled={busy} variant="outline">Mở regional run</Button></form></details>
        </section>
        <section className="simulation-card"><h2>Tiến trình và readiness</h2><SimulationRuntime intervalMs={profile==='meeting'?30000:15000}/>
          <p role="status" aria-live="polite">{session.loading?'Đang kết nối API…':session.job?`${statuses[session.job.status]} · ${session.job.status}`:'Chưa mở regional run'}</p>
          {session.job && <><progress max={1} value={session.job.progress} aria-label="Tiến trình regional"/><p className="small-note">{session.job.id} · {Math.round(session.job.progress*100)}%</p><details><summary>Cấu hình đã lưu</summary><pre>{JSON.stringify(session.job.config,null,2)}</pre></details></>}
          {session.job?.error && <p role="alert" className="error-text">{typeof session.job.error === 'string' ? session.job.error : `${session.job.error.code}: ${session.job.error.message}`}</p>}
          {session.error && <p role="alert" className="error-text">{simulationErrorText(session.error)} {session.error}</p>}
          <Button variant="outline" onClick={session.retry}>Kiểm tra / tải lại dữ liệu</Button>
          {session.job && ['QUEUED','RUNNING'].includes(session.job.status) && <Button variant="outline" onClick={() => void session.cancel()}>Hủy regional job</Button>}
          <p className="small-note">Mỗi vùng/mode phải có graph và local router đúng identity. Không tự gửi lại POST khi mất kết nối. Job chưa hoàn tất không có kết quả phát lại.</p>
          {session.regions.map(r => <p key={r.id}>{regionLabel(r.id)}: {r.ready?'CAR sẵn sàng':r.reason} · bản đồ {r.mapReady?'sẵn sàng':'chưa sẵn sàng'}</p>)}
        </section>
        <section className="simulation-card"><h2>Toàn scenario</h2><Counts counts={session.snapshot?.counts}/>
          {session.result?.globalTotals&&<p>{session.result.globalTotals.carCount} CAR + {session.result.globalTotals.motorbikeCount} MOTORBIKE trong run đang mở</p>}
          {session.result && <><p data-testid="regional-final">{session.result.counts.requested} yêu cầu · {session.result.counts.completed} hoàn tất · {session.result.counts.unserved} không phục vụ</p><p className="small-note">Kết quả cuối run; không đổi theo viewport.</p><details><summary>KPI, routing và provenance</summary><pre>{JSON.stringify(session.result,null,2)}</pre></details></>}
          <h3>Theo vùng tại cùng thời điểm</h3>{session.snapshot?.regions.map(r => {const final=session.result?.regions.find(row=>row.regionId===r.regionId)?.counts;return <div key={r.regionId}><button className="regional-region-link" onClick={() => chooseRegion(r.regionId)}>{regionLabel(r.regionId)}</button><Counts counts={r.counts}/><p>{r.vehicles.filter(v=>v.vehicleType==='CAR').length} CAR · {r.vehicles.filter(v=>v.vehicleType==='MOTORBIKE').length} MOTORBIKE</p>{final&&<p>Kết quả cuối vùng: {final.requested} yêu cầu · {final.assigned} đã gán · {final.completed} hoàn tất · {final.unserved} không phục vụ</p>}</div>})}
        </section>
        <section className="simulation-card"><h2>Xe và hành trình</h2><label>Tìm global vehicle ID<input aria-label="Tìm global vehicle ID" value={query} onChange={e => setQuery(e.target.value)} placeholder="nvmr-bac-ninh-core:GSM-…"/></label><label><input type="checkbox" checked={activeOnly} onChange={e => setActiveOnly(e.target.checked)}/> Chỉ xe đến đón / chở khách</label>
          <p className="small-note">{matches.length} xe khớp trên cả hai vùng · hiển thị tối đa 12</p><div className="simulation-vehicle-results">{matches.slice(0,12).map(v => <button key={v.id} aria-pressed={v.id===session.selectedId} onClick={() => session.selectVehicle(v.id)}><MobilityIcon kind={v.vehicleType==='CAR'?'car':'motorbike'} size={22}/>{v.id} · {v.serviceState}</button>)}</div>
          {vehicle && <><h3>{vehicle.id}</h3><p>{vehicle.vehicleType} · {vehicle.serviceState} · {regionLabel(session.regionId!)}</p><p>Booking: {vehicle.activeBookingId??'Không có'}</p><Button variant="outline" onClick={() => telemetry.current.focus(vehicle.id)}>Theo dõi vị trí xe</Button><Button variant="outline" disabled={!detail} onClick={() => telemetry.current.focusTrip()}>Xem toàn hành trình</Button></>}
          {session.detailLoading && <p role="status">Đang tải immutable booking và tuyến…</p>}
          {session.routeError && <p role="alert">{session.routeError}<Button variant="outline" onClick={session.retry}>Thử lại chi tiết</Button></p>}
          <Journey session={session}/>
        </section>
      </aside>
      <section className="simulation-map-area" aria-label="Bản đồ NVMR regional"><div className="simulation-map-heading"><div><span className="eyebrow">OSM CỤC BỘ · TECHNICAL PILOT</span><h2>{overview?'NVMR overview':regionLabel(selectedRegion.id)}</h2></div><label>Vùng hiển thị<select aria-label="Vùng hiển thị" value={session.regionId??''} disabled={measuring} onChange={e => chooseRegion(e.target.value||null)}><option value="">NVMR overview</option>{session.regions.map(r => <option key={r.id} value={r.id}>{regionLabel(r.id)}</option>)}</select></label></div>
        <p className="small-note">{overview?'Extent nét đứt là operating area kỹ thuật, không phải ranh giới hành chính. Nhấp vùng để xem bản đồ chi tiết. Khoảng trống giữa hai vùng chưa có dữ liệu đường.':'Chỉ tải năm lớp địa lý của vùng đang xem. CAR/MOTORBIKE dùng graph riêng; biểu tượng và tuyến lấy từ completed run.'}</p>
        <div className="simulation-map"><SimulationMapBoundary><Map styles={styles} theme="light" center={[105.98,21.12]} zoom={10} attributionControl={{customAttribution:'© OpenStreetMap contributors · Geofabrik · ODbL 1.0',compact:false}}><MapControls showCompass/>
          {overview?<RegionalOverview regions={session.regions} snapshot={session.snapshot} onSelect={chooseRegion}/>:<><RegionalCamera region={selectedRegion}/><SimulationMapHealth key={`${selectedRegion.id}-${mapRetry}`} enabled onChange={setMapHealth} regionName={regionLabel(selectedRegion.id)}/><SimulationMap snapshot={session.regionalSnapshot} selectedId={session.selectedId} route={session.route} journey={session.journey} onSelect={session.selectVehicle} telemetry={telemetry}/></>}
        </Map></SimulationMapBoundary>{!overview && mapHealth.state==='error' && <div className="simulation-map-notice" role="alert">{mapHealth.message}<Button onClick={() => setMapRetry(n=>n+1)}>Tải lại bản đồ</Button></div>}</div>
        {!overview && <><p role="status">{mapHealth.message}</p><div className="simulation-legend"><span><MobilityIcon kind="car"/> CAR</span><span><MobilityIcon kind="motorbike"/> MOTORBIKE</span><span><MobilityIcon kind="passenger"/> Chờ đón</span><span><MobilityIcon kind="dropoff"/> Trả khách</span><span>P: đến đón · T: chở khách · R: rảnh · ×: offline</span></div><details className="simulation-card"><summary>Đo render regional</summary><p className="small-note">Capture WebGL 5 giây tại vùng đang xem; không phải đo throughput của worker hoặc chứng nhận 5.000 xe.</p><Button disabled={measuring || !session.regionalSnapshot || mapHealth.state!=='ready'} onClick={()=>void measure()}>{measuring?'Đang đo…':'Đo WebGL vùng 5 giây'}</Button>{measurement && <pre>{JSON.stringify(measurement,null,2)}</pre>}</details></>}
      </section>
    </div><RegionalPlayback session={session}/>
  </div>
}

function Counts({counts}: {counts: Record<string,number> | undefined}) {
  return counts?<dl className="simulation-kpis">{Object.entries(counts).map(([key,value])=><div key={key}><dt>{stateLabels[key]??key}</dt><dd>{value.toLocaleString('vi-VN')}</dd></div>)}</dl>:<p>Chưa có snapshot.</p>
}
function Journey({session}: {session: Session}) {
  const detail = session.journey?.detail
  if (!detail || !session.regionalSnapshot) return null
  return <div className="simulation-booking-detail" data-testid="regional-journey"><h3>{detail.bookingId} · {detail.serviceType}</h3><p>Pickup [{detail.pickup.map(n=>n.toFixed(6)).join(', ')}]<br/>Dropoff [{detail.dropoff.map(n=>n.toFixed(6)).join(', ')}]</p>{[detail.pickupLeg,detail.tripLeg].map(leg=><div key={leg.phase}><strong>{leg.phase==='pickup'?'Đến đón · nét đứt':'Chở khách · nét liền'}</strong><p>{leg.distance.toFixed(1)} m · {leg.duration.toFixed(1)} s {leg.routeRef?'':'· đón tại chỗ'}</p><progress aria-label={`Regional ${leg.phase} progress`} max={1} value={legProgress(leg,session.regionalSnapshot!.simulationTimeSeconds)}/><p>t={leg.startTimeSeconds.toFixed(3)} → {leg.endTimeSeconds.toFixed(3)} s</p></div>)}<details><summary>Routing identity và provenance</summary><pre>{JSON.stringify(detail.routingIdentity,null,2)}</pre></details></div>
}
function RegionalPlayback({session}: {session: Session}) {
  const clock = useFleetClock(session.clock)
  return <PlaybackDock label="Phát lại đồng bộ hai vùng" enabled={!!session.snapshot} time={clock.simulationTimeSeconds} duration={session.result?.simulationDurationSeconds??0} speed={clock.speedMultiplier} status={clock.playbackStatus} play={session.clock.play} pause={session.clock.pause} reset={()=>session.seek(0)} seek={session.seek} setSpeed={session.clock.setSpeed}/>
}
