import { numberText } from '@/lib/vi'
import { stateLabels, stateText, errorText } from '@/lib/vi'
import { InspectorSection } from './inspector-section'
import { useState } from 'react'
import { Pause, Play, RotateCcw, Navigation, RefreshCw } from 'lucide-react'
import { Button } from './ui/button'
import { Slider } from './ui/slider'
import { fleetOverview, vehicleAt, type Vehicle } from '@/lib/fleet'
import { useFleetClock, type FleetSession } from '@/lib/use-fleet'

const distance = (m: number) => `${numberText((m/1000), 2)} km`
const statusLabel = stateLabels
export interface FleetFocus { id: string; kind: 'vehicle' | 'route'; sequence: number }
export function FleetPanel({ fleet, ready, onFocus, docked = false }: { fleet: FleetSession; ready: boolean; docked?: boolean; onFocus: (id: string, kind: FleetFocus['kind']) => void }) {
  const [count, setCount] = useState(5), [seed, setSeed] = useState('hcm-fleet-2026')
  const clock = useFleetClock(fleet.clock), scenario = fleet.scenario
  const vehicles = scenario?.vehicles.map(v => vehicleAt(v, clock.simulationTimeSeconds)) ?? []
  const overview = fleetOverview(vehicles), selected = vehicles.find(v => v.id === fleet.selectedVehicleId)
  const duration = scenario?.simulationDurationSeconds ?? 0, usable = vehicles.length > 0 && ready && !fleet.loading
  const playing = clock.playbackStatus === 'playing'
  const metrics = fleet.clock.getMetrics()
  return <div className="fleet-panel" data-simulation-time={clock.simulationTimeSeconds} data-fleet-state={clock.playbackStatus}>
    <InspectorSection title="Cấu hình đội xe" defaultOpen prepared={docked && !!scenario}>
      <div className="section-heading"><Navigation size={17} /><h2>Mô phỏng đội xe</h2></div>
      <p className="simulation-disclaimer">Đội xe mô phỏng · không phải GPS thực tế</p>
      <div className="fleet-inputs"><label>Số xe<select aria-label="Số xe" value={count} onChange={event => setCount(Number(event.target.value))}>{Array.from({ length: 10 }, (_, i) => <option key={i+1} value={i+1}>{i+1}</option>)}</select></label><label>Seed (khởi tạo ngẫu nhiên)<input aria-label="Seed kịch bản" value={seed} maxLength={80} onChange={event => setSeed(event.target.value)} /></label></div>
      <div className="fleet-generate"><Button disabled={!ready || !seed.trim()} onClick={() => void fleet.generate(seed.trim(), count)}><RefreshCw size={15} />Tạo kịch bản</Button><Button variant="outline" onClick={() => setSeed(value => `${value.replace(/-new-\d+$/, '')}-new-${Date.now()}`)}>Seed mới</Button></div>
      {!ready && <p className="disabled-note">Cần bản đồ và OSRM cục bộ sẵn sàng.</p>}
      {fleet.loading && <p role="status">Đang chuẩn bị tuyến đường · {fleet.completedRequests}/{count} · tối đa 2 yêu cầu đồng thời</p>}
      {fleet.error && <p role="alert" className="error-text">{errorText(fleet.error)}</p>}
      {scenario && <div className="scenario-summary"><p>Đã tạo {vehicles.length}/{scenario.requestedVehicles} xe · {numberText((scenario.preparationMilliseconds/1000), 2)} giây</p><p>{scenario.routeRequests} yêu cầu tuyến · {scenario.cacheHits} lần dùng bộ nhớ đệm</p><p>Seed: {scenario.seed}</p><details><summary>Nguồn dữ liệu kịch bản</summary><p>Dấu nhận dạng dữ liệu: {scenario.datasetFingerprint}</p><p>{scenario.routingSource} · {String(scenario.provenance.profile)} · độ lệch điểm trên đường ≤ {String(scenario.provenance.max_snap_meters)} m</p></details></div>}
      {!!scenario?.failures.length && <details open className="fleet-errors"><summary>{scenario.failures.length} xe không được tạo</summary>{scenario.failures.map(f => <p key={f.id}>{f.id}: {errorText(f.reason)}</p>)}</details>}
      {!scenario && !fleet.loading && <p className="small-note">Tạo kịch bản từ các điểm đường OSM cục bộ. Chỉ nhận xe sau khi OSRM xác nhận tuyến và vị trí trên đường.</p>}
    </InspectorSection>
    <InspectorSection title="Tổng quan đội xe" defaultOpen>
      <div className="section-heading"><Play size={17} /><h2>Tổng quan đội xe</h2></div>
      {!docked && <>
      <div className="playback-buttons"><Button className="play-button" disabled={!usable || playing} onClick={fleet.clock.play}><Play size={16} />{clock.simulationTimeSeconds > 0 && clock.playbackStatus === 'paused' ? "Tiếp tục" : "Phát"}</Button><Button variant="outline" disabled={!usable || !playing} onClick={fleet.clock.pause}><Pause size={16} />Tạm dừng</Button><Button variant="outline" disabled={!usable} aria-label="Đưa đội xe về đầu" onClick={fleet.clock.reset}><RotateCcw size={16} /></Button></div>
      <div className="progress-label"><label id="fleet-progress-label">Dòng thời gian đội xe</label><span>{duration ? Math.round(clock.simulationTimeSeconds/duration*100) : 0}%</span></div>
      <Slider aria-labelledby="fleet-progress-label" disabled={!usable} min={0} max={duration || 1} step={0.1} value={[clock.simulationTimeSeconds]} onValueChange={value => fleet.clock.seek(typeof value === 'number' ? value : value[0])} />
      <div className="speed-row"><span>Tốc độ toàn đội xe</span><div>{[1, 2, 4].map(speed => <Button size="sm" key={speed} disabled={!usable} variant={clock.speedMultiplier === speed ? 'secondary' : 'ghost'} aria-pressed={clock.speedMultiplier === speed} onClick={() => fleet.clock.setSpeed(speed)}>{speed}x</Button>)}</div></div>
      <p className="playback-time">{numberText(clock.simulationTimeSeconds, 1)} / {numberText(duration, 1)} giây · {stateText(clock.playbackStatus)}</p>
      </>}
      <div className="fleet-overview" aria-label="Tổng quan đội xe">{[["Tổng số", overview.total], ["Chưa bắt đầu", overview.scheduled], ["Đang di chuyển", overview.moving], ["Hoàn tất", overview.completed]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <p className="small-note">Kế hoạch: {distance(overview.plannedMeters)} · Đã đi mô phỏng: {distance(overview.traveledMeters)}</p>
      <details className="scenario-summary"><summary>Hiệu năng phiên phát lại</summary><p data-clock-metrics={JSON.stringify(metrics)}>{metrics.frameSamples} mẫu RAF · trung bình {numberText(metrics.meanFrameMilliseconds, 1)} ms · khoảng cách khung lớn nhất {numberText(metrics.maxFrameMilliseconds, 1)} ms</p><p>Đồng hồ cập nhật trạng thái tối đa 30 Hz; khoảng cách RAF gồm cả ảnh hưởng trình duyệt/GPU. Không phải chứng nhận FPS.</p></details>
    </InspectorSection>
    {!!vehicles.length && <InspectorSection title="Danh sách xe" defaultOpen><div className="section-heading"><Navigation size={17} /><h2>Danh sách xe</h2></div>
      <div className="vehicle-list">{vehicles.map(v => <VehicleRow key={v.id} vehicle={v} selected={v.id === fleet.selectedVehicleId} onSelect={() => fleet.setSelectedVehicleId(v.id)} onFocus={() => onFocus(v.id, 'vehicle')} />)}</div>
    </InspectorSection>}
    {selected && <InspectorSection title="Chi tiết phương tiện" selection={fleet.selectedVehicleId ?? ""}><h2>{selected.label}{selected.vehicleType ? ` · ${selected.vehicleType}` : ''} · {statusLabel[selected.status]}</h2><p>{selected.currentPosition.map(v => v.toFixed(6)).join(', ')}</p><p>Tiến độ {numberText((selected.progress*100), 1)}% · còn {numberText(((1-selected.progress)*selected.durationSeconds), 1)} giây</p><p>Độ lệch điểm A/B trên đường: {selected.route.snap_points.map(p => `${numberText(p.distance, 1)} m`).join(' / ')}</p><div className="fleet-generate"><Button size="sm" variant="outline" onClick={() => onFocus(selected.id, 'vehicle')}>Quan sát xe</Button><Button size="sm" variant="outline" onClick={() => onFocus(selected.id, 'route')}>Xem toàn tuyến</Button></div></InspectorSection>}
  </div>
}
function VehicleRow({ vehicle: v, selected, onSelect, onFocus }: { vehicle: Vehicle; selected: boolean; onSelect: () => void; onFocus: () => void }) {
  return <div className={`vehicle-row ${selected ? 'selected' : ''}`} data-vehicle-row={v.id} data-status={v.status} data-progress={v.progress}>
    <button className="vehicle-select" aria-label={`Chọn ${v.id}`} aria-pressed={selected} onClick={onSelect}><strong>{v.id}{v.vehicleType ? ` · ${v.vehicleType}` : ''}</strong><span className={`vehicle-status ${v.status}`}>{statusLabel[v.status]}</span><span>{distance(v.distanceMeters)} · {numberText(v.durationSeconds, 1)} giây · xuất phát +{v.departureOffsetSeconds} giây</span><span>{Math.round(v.progress*100)}%</span></button>
    <button className="vehicle-focus" aria-label={`Quan sát ${v.id}`} onClick={onFocus}><Navigation size={14} /></button>
  </div>
}
