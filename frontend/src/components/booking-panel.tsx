import { numberText } from '@/lib/vi'
import { stateLabels, stateText, errorText, presetText, percentText } from '@/lib/vi'
import { InspectorSection } from './inspector-section'
import { useMemo, useState } from 'react'
import { Play, Pause, RotateCcw, Users, RefreshCw } from 'lucide-react'
import { Button } from './ui/button'
import { Slider } from './ui/slider'
import { bookingProjection, type BookingConfig } from '@/lib/booking'
import { useFleetClock } from '@/lib/use-fleet'
import type { BookingSession } from '@/lib/use-booking'
import { download } from '@/lib/voucher'

export interface BookingFocus { kind: 'vehicle' | 'booking' | 'overview'; id: string; sequence: number }
const labels = stateLabels
const number = (value: number | null, suffix = ' giây') => value === null ? '—' : numberText(value, 1)+suffix
const percent = (value: number | null) => percentText(value)
export function BookingPanel({ session, ready, onFocus, docked = false }: { session: BookingSession; ready: boolean; docked?: boolean; onFocus: (focus: BookingFocus) => void }) {
  const [config, setConfig] = useState<BookingConfig>({ seed: 'hcm-booking-2026', fleetSize: 5, bookingCount: 20, horizonSeconds: 1800, maxWaitSeconds: 300, preset: 'Medium' })
  const [filter, setFilter] = useState('active')
  const [seekSeconds, setSeekSeconds] = useState('0')
  const clock = useFleetClock(session.clock), plan = session.plan
  const view = useMemo(() => plan ? bookingProjection(plan, clock.simulationTimeSeconds) : null, [plan, clock.simulationTimeSeconds])
  const planned = useMemo(() => plan ? bookingProjection(plan, plan.simulationDurationSeconds) : null, [plan])
  const usable = !!plan && ready && !session.loading, playing = clock.playbackStatus === 'playing'
  const selected = view?.bookings.find(b => b.id === session.selectedBookingId)
  const focus = (kind: BookingFocus['kind'], id: string) => onFocus({ kind, id, sequence: performance.now() })
  const metrics = view?.metrics
  const shown = view?.bookings.filter(b => filter === 'all' || (filter === 'active' ? ['waiting', 'assigned', 'picked_up'].includes(b.status) : b.status === filter)) ?? []
  return <div className="fleet-panel booking-panel" data-booking-time={clock.simulationTimeSeconds} data-booking-clock={clock.playbackStatus}>
    {session.multimodal && <Button variant="outline" onClick={()=>download(`gsm-multimodal-${plan!.id.slice(0,12)}.json`,JSON.stringify(session.multimodal,null,2),'application/json')}>Xuất JSON đa phương tiện · contract riêng</Button>}
    <InspectorSection title="Cấu hình đặt xe" defaultOpen prepared={docked && !!plan}><div className="section-heading"><Users size={17} /><h2>Đặt xe và điều phối</h2></div><p className="simulation-disclaimer">Mô phỏng nhu cầu · không phải hành khách/GPS GSM thực tế</p>
      <div className="booking-inputs">
        <label>Số xe<select aria-label="Số xe điều phối" value={config.fleetSize} onChange={e => setConfig({ ...config, fleetSize: +e.target.value })}>{Array.from({ length: 10 }, (_, i) => <option key={i+1}>{i+1}</option>)}</select></label>
        <label>Yêu cầu đặt xe<select aria-label="Số yêu cầu đặt xe" value={config.bookingCount} onChange={e => setConfig({ ...config, bookingCount: +e.target.value })}>{Array.from({ length: 21 }, (_, i) => <option key={i+10}>{i+10}</option>)}</select></label>
        <label className="wide">Seed (khởi tạo ngẫu nhiên)<input aria-label="Seed đặt xe" value={config.seed} maxLength={80} onChange={e => setConfig({ ...config, seed: e.target.value })} /></label>
        <label>Nhu cầu đặt xe<select aria-label="Phân bố nhu cầu" value={config.preset} onChange={e => setConfig({ ...config, preset: e.target.value as BookingConfig['preset'] })}>{['Low', 'Medium', 'High'].map(p => <option key={p} value={p}>{presetText(p)}</option>)}</select></label>
        <label>Khoảng phát sinh yêu cầu (giây)<input aria-label="Khoảng phát sinh yêu cầu (giây)" type="number" min={60} max={3600} value={config.horizonSeconds} onChange={e => setConfig({ ...config, horizonSeconds: +e.target.value })} /></label>
        <label className="wide">Giới hạn chờ đến lúc đón (giây)<input aria-label="Giới hạn chờ đến lúc đón (giây)" type="number" min={10} max={900} value={config.maxWaitSeconds} onChange={e => setConfig({ ...config, maxWaitSeconds: +e.target.value })} /></label>
      </div>
      <p className="small-note">Thấp: trải đều với độ lệch ngẫu nhiên nhỏ. Vừa: thời điểm phân bố đều ngẫu nhiên theo Seed. Cao: dồn vào ¼ đầu khoảng phát sinh. Mọi phân bố giữ nguyên số yêu cầu.</p>
      <Button disabled={!ready || !config.seed.trim() || config.horizonSeconds < 60 || config.horizonSeconds > 3600 || config.maxWaitSeconds < 10 || config.maxWaitSeconds > 900} onClick={() => { setSeekSeconds('0'); void session.generate({ ...config, seed: config.seed.trim() }) }}><RefreshCw size={15} />Tạo kịch bản đặt xe</Button>
      {session.loading && <p role="status">Đang chuẩn bị kế hoạch điều phối bằng OSRM cục bộ… Có thể mất vài chục giây; chưa thể phát mô phỏng.</p>}
      {session.error && <p role="alert" className="error-text">{errorText(session.error)}</p>}
      {plan && <details className="scenario-summary"><summary>Kế hoạch đã xác minh · {numberText((plan.preparationMilliseconds/1000), 2)} giây</summary><p>Seed: {plan.seed}<br />Dấu nhận dạng dữ liệu: {plan.datasetFingerprint}</p><p>{plan.routingRequests.table} bảng ETA · {plan.routingRequests.route} tuyến · {plan.routingRequests.routeCacheHits} lần dùng bộ nhớ đệm · {plan.routingSource}</p><p>Nhu cầu v1 · FIFO / ETA v1 · không tính tuyến khi phát lại</p></details>}
    </InspectorSection>
    <InspectorSection title="Diễn biến kịch bản" defaultOpen><div className="section-heading"><Play size={17} /><h2>Diễn biến kịch bản</h2></div>
      {!docked && <>
      <div className="playback-buttons"><Button disabled={!usable || playing} onClick={session.clock.play}><Play size={16} />{clock.simulationTimeSeconds > 0 && clock.playbackStatus === 'paused' ? "Tiếp tục" : "Phát"}</Button><Button variant="outline" disabled={!usable || !playing} onClick={session.clock.pause}><Pause size={16} />Tạm dừng</Button><Button variant="outline" disabled={!usable} aria-label="Đưa mô phỏng đặt xe về đầu" onClick={() => { setSeekSeconds('0'); session.clock.reset() }}><RotateCcw size={16} /></Button></div>
      <div className="progress-label"><label id="booking-timeline">Dòng thời gian đặt xe</label><span>{plan ? Math.round(clock.simulationTimeSeconds/plan.simulationDurationSeconds*100) : 0}%</span></div>
      <Slider aria-labelledby="booking-timeline" disabled={!usable} min={0} max={plan?.simulationDurationSeconds ?? 1} step={.1} value={[clock.simulationTimeSeconds]} onValueChange={v => session.clock.seek(typeof v === 'number' ? v : v[0])} />
      <div className="booking-seek"><input aria-label="Thời điểm mô phỏng (giây)" type="number" min={0} max={plan?.simulationDurationSeconds ?? 0} step="any" value={seekSeconds} disabled={!usable} onChange={e => setSeekSeconds(e.target.value)} /><Button size="sm" variant="outline" disabled={!usable || !seekSeconds.trim() || !Number.isFinite(Number(seekSeconds))} onClick={() => session.clock.seek(Number(seekSeconds))}>Đến thời điểm</Button></div>
      <p className="playback-time">{number(clock.simulationTimeSeconds)} / {number(plan?.simulationDurationSeconds ?? 0)} · {stateText(clock.playbackStatus)}</p>
      <details className="scenario-summary"><summary>Hiệu năng đồng hồ mô phỏng</summary><p data-booking-clock-metrics={JSON.stringify(session.clock.getMetrics())}>{session.clock.getMetrics().frameSamples} mẫu RAF · trung bình {numberText(session.clock.getMetrics().meanFrameMilliseconds, 1)} ms · khoảng cách khung lớn nhất {numberText(session.clock.getMetrics().maxFrameMilliseconds, 1)} ms. Không phải chứng nhận FPS.</p></details>
      <div className="speed-row"><span>Tốc độ mô phỏng</span><div>{[1, 2, 4].map(s => <Button key={s} size="sm" variant={clock.speedMultiplier === s ? 'secondary' : 'ghost'} disabled={!usable} aria-pressed={clock.speedMultiplier === s} onClick={() => session.clock.setSpeed(s)}>{s}x</Button>)}</div></div>
      </>}
      <Button size="sm" variant="outline" disabled={!usable} onClick={() => focus('overview', 'scenario')}>Xem toàn vùng kịch bản</Button>
    </InspectorSection>
    {metrics && <InspectorSection title="Chỉ số tại thời điểm hiện tại" defaultOpen><h2>Chỉ số tới thời điểm hiện tại</h2><div className="fleet-overview">{[["Đã yêu cầu", metrics.requested], ["Đã phân công xe", metrics.assigned], ["Hoàn tất", metrics.completed], ["Không được phục vụ", metrics.unserved]].map(([l, n]) => <div key={l}><span>{l}</span><strong>{n}</strong></div>)}</div>
      <dl className="booking-metrics" data-booking-metrics={JSON.stringify(metrics)}><dt>Đã đón / đã yêu cầu</dt><dd>{percent(metrics.serviceRate)}</dd><dt>Hoàn tất / đã yêu cầu</dt><dd>{percent(metrics.completionRate)}</dd><dt>Chờ TB · đã đón</dt><dd>{number(metrics.averageWaitingSeconds)}</dd><dt>Chuyến TB · hoàn tất</dt><dd>{number(metrics.averageTripSeconds)}</dd><dt>ETA đón TB · đã gán</dt><dd>{number(metrics.averageEstimatedPickupEtaSeconds)}</dd><dt>Quãng đường rỗng</dt><dd>{number(metrics.emptyMeters/1000, ' km')}</dd><dt>Quãng đường chở khách</dt><dd>{number(metrics.occupiedMeters/1000, ' km')}</dd><dt>Mức sử dụng đội xe · thời gian bận / tổng thời gian xe</dt><dd>{percent(metrics.utilization)}</dd></dl>
      <p className="small-note">Thời gian chờ và mức sử dụng đội xe là chỉ số mô phỏng; thời gian và quãng đường theo cấu hình OSRM, không phản ánh giao thông trực tiếp. Số đã phân công gồm mọi yêu cầu từng được gán xe.</p>
      <details className="scenario-summary"><summary>Kết quả cuối kịch bản</summary><p>{planned!.metrics.completed}/{plan!.demand.length} hoàn tất · {planned!.metrics.unserved} không được phục vụ</p><p>Rỗng {number(planned!.metrics.emptyMeters/1000, ' km')} · chở khách {number(planned!.metrics.occupiedMeters/1000, ' km')}</p></details>
    </InspectorSection>}
    {view && <InspectorSection title="Yêu cầu đặt xe" defaultOpen><h2>Yêu cầu đặt xe</h2><label className="booking-filter">Lọc trạng thái<select aria-label="Lọc trạng thái đặt xe" value={filter} onChange={e => setFilter(e.target.value)}>{[['active', 'Đang hoạt động'], ['all', 'Tất cả (gồm tương lai)'], ['unserved', "Không được phục vụ"], ['completed', 'Hoàn tất']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      {!shown.length && <p className="small-note">Không có yêu cầu đặt xe phù hợp với bộ lọc tại thời điểm này.</p>}
      <div className="vehicle-list">{shown.map(b => <button key={b.id} className={`booking-row ${session.selectedBookingId === b.id ? 'selected' : ''}`} aria-label={`Chọn yêu cầu đặt xe ${b.id}`} aria-pressed={session.selectedBookingId === b.id} data-booking-id={b.id} data-status={b.status} onClick={() => { session.setSelectedBookingId(b.id); session.setSelectedVehicleId(b.assignment?.vehicleId ?? null); focus('booking', b.id) }}><strong>{b.id}{b.serviceType ? ` · ${b.serviceType}` : ''}</strong><span>{labels[b.status]}</span><small>Yêu cầu +{number(b.requestTimeSeconds)} · {b.assignment?.vehicleId ?? "Chưa phân công xe"} · chờ {number(b.waitingSeconds)}</small>{b.failureReason && <small className="error-text">{errorText(b.failureReason)}</small>}</button>)}</div>
    </InspectorSection>}
    {selected && <InspectorSection title="Chi tiết yêu cầu đặt xe" selection={(session.selectedBookingId ?? "") + (session.selectedVehicleId ?? "")}><h2>{selected.id}{selected.serviceType ? ` · ${selected.serviceType}` : ''} · {labels[selected.status]}</h2><p>Điểm đón: {selected.pickup.map(v => v.toFixed(6)).join(', ')}<br />Điểm trả: {selected.dropoff.map(v => v.toFixed(6)).join(', ')}</p><p>Xe: {selected.assignment?.vehicleId ?? '—'} · ETA đón {number(selected.assignment?.estimatedPickupEtaSeconds ?? null)}<br />Chờ mô phỏng: {number(selected.waitingSeconds)} · chuyến OSRM: {number(selected.assignment?.tripRoute.duration ?? null)}</p>{selected.failureReason && <p>{errorText(selected.failureReason)}</p>}<Button variant="outline" size="sm" onClick={() => focus('booking', selected.id)}>Xem vùng đón và trả khách</Button></InspectorSection>}
    {view && <InspectorSection title="Đội xe điều phối" defaultOpen><h2>Đội xe điều phối</h2><div className="vehicle-list">{view.vehicles.map(v => <button className={`booking-row ${session.selectedVehicleId === v.id ? 'selected' : ''}`} key={v.id} aria-label={`Quan sát xe điều phối ${v.id}`} data-dispatch-row={v.id} data-status={v.status} onClick={() => { session.setSelectedVehicleId(v.id); session.setSelectedBookingId(v.activeBookingId); focus('vehicle', v.id) }}><strong>{v.id}{v.vehicleType ? ` · ${v.vehicleType}` : ''}</strong><span>{labels[v.status]}</span><small>{v.activeBookingId ?? "Không có yêu cầu đặt xe"} · {v.completedBookingIds.length} chuyến hoàn tất<br />Rỗng {number(v.emptyMeters/1000, ' km')} · chở khách {number(v.occupiedMeters/1000, ' km')}</small></button>)}</div></InspectorSection>}
    {view && <InspectorSection title="Dòng thời gian sự kiện"><h2>Dòng thời gian sự kiện · {view.events.length}</h2><ol className="booking-events">{view.events.slice(-16).reverse().map(e => <li key={e.id}><time>{number(e.timestampSeconds)}</time><span>{stateText(e.type)}<small>{e.bookingId}{e.vehicleId ? ' · '+e.vehicleId : ''}{e.payload.failureReason ? ' · '+errorText(String(e.payload.failureReason)) : ''}</small></span></li>)}</ol><p className="small-note">16 sự kiện gần nhất tới thời điểm mô phỏng; lùi thời gian sẽ loại bỏ các sự kiện tương lai.</p></InspectorSection>}
  </div>
}
