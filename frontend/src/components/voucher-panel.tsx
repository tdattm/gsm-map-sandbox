import { numberText } from '@/lib/vi'
import { moneyText as vnd, stateText, errorText, presetText, dateText } from '@/lib/vi'
import { InspectorSection } from './inspector-section'
import { useMemo, useRef, useState } from 'react'
import { FlaskConical, Play, Pause, RotateCcw } from 'lucide-react'
import { Button } from './ui/button'
import { Slider } from './ui/slider'
import { defaultExperimentConfig, experimentMetrics, type ExperimentConfig } from '@/lib/voucher'
import { bookingProjection } from '@/lib/booking'
import { useFleetClock } from '@/lib/use-fleet'
import type { VoucherSession } from '@/lib/use-voucher'
import type { BookingFocus } from './booking-panel'

export function VoucherPanel({ session, ready, onFocus, onRuntime, docked = false }: { session: VoucherSession; ready: boolean; docked?: boolean; onRuntime?: (runtime:'live'|'saved')=>void; onFocus: (focus: BookingFocus) => void }) {
  const [config, setConfig] = useState<ExperimentConfig>(structuredClone(defaultExperimentConfig)), [seek, setSeek] = useState('0')
  const importInput = useRef<HTMLInputElement>(null)
  const [importName, setImportName] = useState('Chưa chọn file')
  const clock = useFleetClock(session.clock), experiment = session.experiment
  const time = clock.simulationTimeSeconds, usable = !!experiment && ready && !session.loading, playing = clock.playbackStatus === 'playing'
  const metricTime = playing ? Math.floor(time) : time
  const projection = useMemo(() => experiment ? bookingProjection(experiment[session.arm].plan, time) : null, [experiment, session.arm, time])
  const metrics = useMemo(() => experiment ? experimentMetrics(experiment, session.arm, metricTime) : null, [experiment, session.arm, metricTime])
  const focus = (kind: BookingFocus['kind'], id: string) => onFocus({ kind, id, sequence: performance.now() })
  const input = (label: string, value: number, update: (value: number) => void, min: number, max: number, step=1) => <label>{label}<input aria-label={label} type="number" value={value} min={min} max={max} step={step} onChange={e => update(+e.target.value)} /></label>
  const selected = projection?.bookings.find(b => b.id === session.selectedBookingId)
  const saved=session.runtime==='saved'
  return <div className="voucher-panel" data-experiment-time={time} data-experiment-clock={clock.playbackStatus} data-experiment-arm={session.arm === "baseline" ? "Baseline" : "Treatment"} data-clock-metrics={JSON.stringify(session.clock.getMetrics())}>
    <InspectorSection title="Chế độ thí nghiệm" defaultOpen><div className="arm-switch" role="group" aria-label="Chế độ thí nghiệm"><Button variant={!saved?'secondary':'outline'} aria-pressed={!saved} onClick={()=>onRuntime?.('live')}>Thí nghiệm trực tiếp (Live)</Button><Button variant={saved?'secondary':'outline'} aria-pressed={saved} onClick={()=>onRuntime?.('saved')}>Phát lại đã lưu (Saved Replay)</Button></div>
      {saved && <><p className="simulation-disclaimer">Phát lại đã lưu · không cần tính tuyến trực tiếp</p><label>Nhập thí nghiệm đã lưu<input ref={importInput} className="sr-only" tabIndex={-1} aria-label="Nhập thí nghiệm đã lưu" type="file" accept=".json,application/json" onChange={event=>{const file=event.target.files?.[0]; if(file) { setImportName(file.name); void session.loadSaved(file) }; event.target.value=''}}/></label><Button variant="outline" aria-describedby="saved-import-name" onClick={()=>importInput.current?.click()}>Chọn file JSON</Button><p id="saved-import-name" className="small-note">{importName}</p><Button variant="outline" onClick={()=>void session.loadSaved('demo')} disabled={session.loading}>Tải kịch bản mẫu</Button>{session.loading && <p role="status">Đang kiểm chứng thí nghiệm và gói bản đồ cục bộ…</p>}{session.error && <p role="alert" className="error-text">{errorText(session.error)}</p>}
      {experiment && <p className="small-note">Seed: {experiment.seed}<br/>Thời điểm chuẩn bị: {dateText(experiment.createdAt)} (giờ Việt Nam)<br/>Bộ dữ liệu: {experiment.datasetFingerprint}<br/>Phiên bản mô hình: {JSON.stringify(experiment.assumptions.versions)}<br/>SHA-256 đã kiểm chứng · dữ liệu mô phỏng, không GPS thực tế</p>}</>}
    </InspectorSection>
    {!saved && <InspectorSection title="Cấu hình thí nghiệm" defaultOpen prepared={docked && !!experiment}><div className="section-heading"><FlaskConical size={18}/><h2>Thí nghiệm voucher</h2></div><p className="simulation-disclaimer">Giá và hành vi giả định · chưa hiệu chỉnh từ khách hàng GSM</p>
      <div className="booking-inputs"><label className="wide">Seed (khởi tạo ngẫu nhiên)<input aria-label="Seed thí nghiệm" value={config.seed} maxLength={80} onChange={e => setConfig({ ...config, seed: e.target.value })}/></label>
        <label>Đội xe<select aria-label="Số xe thí nghiệm" value={config.fleetSize} onChange={e => setConfig({ ...config, fleetSize: +e.target.value })}>{Array.from({ length: 10 }, (_, i) => <option key={i+1}>{i+1}</option>)}</select></label>
        <label>Hành trình tiềm năng<select aria-label="Số hành trình tiềm năng" value={config.potentialCount} onChange={e => setConfig({ ...config, potentialCount: +e.target.value })}>{Array.from({ length: 21 }, (_, i) => <option key={i+10}>{i+10}</option>)}</select></label>
        <label>Nhu cầu đặt xe<select aria-label="Phân bố nhu cầu thí nghiệm" value={config.preset} onChange={e => setConfig({ ...config, preset: e.target.value as ExperimentConfig['preset'] })}>{['Low','Medium','High'].map(p => <option key={p} value={p}>{presetText(p)}</option>)}</select></label>
        {input("Khoảng phát sinh yêu cầu (giây)", config.horizonSeconds, horizonSeconds => setConfig({ ...config, horizonSeconds }),60,3600)}
      </div>
      <InspectorSection title="Chính sách voucher" defaultOpen={!docked}><div className="booking-inputs voucher-policy"><label>Voucher<select aria-label="Loại voucher" value={config.voucher.type} onChange={e => setConfig({ ...config, voucher: { ...config.voucher, type: e.target.value as 'fixed' | 'percentage' } })}><option value="fixed">Số tiền cố định (VND)</option><option value="percentage">Theo tỷ lệ</option></select></label>
        {config.voucher.type === 'fixed' ? input("Mức giảm cố định (VND)", config.voucher.fixedAmount, fixedAmount => setConfig({ ...config, voucher: { ...config.voucher, fixedAmount } }),0,1000000) : input("Tỷ lệ giảm (0–1)",config.voucher.rate,rate => setConfig({ ...config, voucher: { ...config.voucher, rate } }),0,1,.01)}
        {input("Ngân sách voucher (VND)",config.campaignBudget,campaignBudget => setConfig({ ...config, campaignBudget }),0,10000000)}
      </div></InspectorSection>
      <details className="scenario-summary"><summary>Giả định về hành vi hành khách và giá cước</summary><div className="booking-inputs">
        {input("Cước cơ bản (VND)",config.fare.baseFare,baseFare => setConfig({ ...config, fare: { ...config.fare, baseFare } }),0,100000)}
        {input("Cước theo quãng đường (VND/km)",config.fare.perKm,perKm => setConfig({ ...config, fare: { ...config.fare, perKm } }),0,100000)}
        {input('Alpha (log-odds)',config.behavior.alpha,alpha => setConfig({ ...config, behavior: { ...config.behavior, alpha } }),-20,20,.1)}
        {input("Beta (độ nhạy giá)",config.behavior.beta,beta => setConfig({ ...config, behavior: { ...config.behavior, beta } }),0,20,.1)}
        {input("Cước tham chiếu (VND)",config.behavior.referenceFare,referenceFare => setConfig({ ...config, behavior: { ...config.behavior, referenceFare } }),1,1000000)}
        {input("Cước tối thiểu để áp dụng (VND)",config.voucher.minimumFare,minimumFare => setConfig({ ...config, voucher: { ...config.voucher, minimumFare } }),0,1000000)}
        {input("Giới hạn giảm theo tỷ lệ (VND)",config.voucher.cap,cap => setConfig({ ...config, voucher: { ...config.voucher, cap } }),0,1000000)}
        {input("Giới hạn chờ đến lúc đón (giây)",config.maxWaitSeconds,maxWaitSeconds => setConfig({ ...config, maxWaitSeconds }),10,900)}
      </div><p className="small-note">Cước = cước cơ bản + đơn giá × quãng đường OSRM (km). Sigmoid(alpha − beta × cước sau ưu đãi / cước tham chiếu). Hai kịch bản dùng cùng mẫu ngẫu nhiên. Khi thiếu ngân sách: dùng giá gốc, không áp dụng một phần voucher.</p></details>
      <Button disabled={!ready || !config.seed.trim()} onClick={() => { setSeek('0'); void session.generate({ ...config, seed: config.seed.trim() }) }}>Chuẩn bị thí nghiệm</Button>
      {session.loading && <p role="status">Đang tính cước và chuẩn bị hai kịch bản bằng OSRM cục bộ…</p>}{session.error && <p role="alert" className="error-text">{errorText(session.error)}</p>}
      {experiment && <details className="scenario-summary"><summary>Thí nghiệm sẵn sàng · {numberText((experiment.preparationMilliseconds/1000), 2)} giây</summary><p>Seed: {experiment.seed}<br/>Dấu nhận dạng thí nghiệm: {experiment.id}<br/>{experiment.routingRequests.table} bảng ETA · {experiment.routingRequests.route} tuyến · {experiment.routingRequests.routeCacheHits} lần dùng bộ nhớ đệm</p><p>{experiment.potential.filter(p => !p.valid).length} báo giá không hợp lệ, loại khỏi mẫu số tỷ lệ đặt xe.</p></details>}
    </InspectorSection>}
    <InspectorSection title="Kịch bản và ngân sách" defaultOpen><h2>Kịch bản thí nghiệm</h2><p className="small-note">Baseline: kịch bản không voucher. Treatment: kịch bản áp dụng voucher.</p><div className="arm-switch" role="group" aria-label="Kịch bản thí nghiệm">{(['baseline','treatment'] as const).map(arm => <Button key={arm} variant={session.arm === arm ? 'secondary' : 'outline'} aria-pressed={session.arm === arm} onClick={() => session.selectArm(arm)}>{arm === 'baseline' ? 'Baseline' : 'Treatment'}</Button>)}</div>
      {!docked && <>
      <div className="playback-buttons"><Button disabled={!usable || playing} onClick={session.clock.play}><Play size={15}/>{clock.playbackStatus === 'paused' && time > 0 ? "Tiếp tục" : "Phát"}</Button><Button variant="outline" disabled={!usable || !playing} onClick={session.clock.pause}><Pause size={15}/>Tạm dừng</Button><Button variant="outline" aria-label="Đưa thí nghiệm về đầu" disabled={!usable} onClick={() => { session.clock.reset(); setSeek('0') }}><RotateCcw size={15}/></Button></div>
      <label id="experiment-timeline">Dòng thời gian thí nghiệm</label><Slider aria-labelledby="experiment-timeline" disabled={!usable} min={0} max={experiment?.simulationDurationSeconds ?? 1} step={.1} value={[time]} onValueChange={value => session.clock.seek(typeof value === 'number' ? value : value[0])}/>
      <div className="booking-seek"><input aria-label="Thời điểm thí nghiệm (giây)" type="number" min={0} max={experiment?.simulationDurationSeconds ?? 0} disabled={!usable} value={seek} onChange={e => setSeek(e.target.value)}/><Button disabled={!usable || !seek.trim() || !Number.isFinite(+seek)} variant="outline" onClick={() => session.clock.seek(+seek)}>Đến thời điểm</Button></div>
      <p className="playback-time">{numberText(time, 1)} / {numberText((experiment?.simulationDurationSeconds ?? 0), 1)} giây · {stateText(clock.playbackStatus)}</p><div className="speed-row">{[1,2,4].map(s => <Button key={s} disabled={!usable} size="sm" variant={clock.speedMultiplier === s ? 'secondary' : 'ghost'} aria-pressed={clock.speedMultiplier === s} onClick={() => session.clock.setSpeed(s)}>{s}x</Button>)}</div>
      </>}
      <Button variant="outline" size="sm" disabled={!usable} onClick={() => focus('overview','scenario')}>Xem toàn vùng thí nghiệm</Button>
      {metrics && <div className="budget-summary"><strong>Ngân sách · {session.arm === "baseline" ? "Baseline" : "Treatment"} · tới thời điểm hiện tại</strong><p>Ngân sách đang giữ trước {vnd(metrics.budget.reserved)}<br/>Chi phí voucher đã sử dụng {vnd(metrics.budget.spent)}<br/>Ngân sách còn khả dụng {vnd(metrics.budget.available)}</p><small>Đã đề xuất {metrics.voucherCounts.OFFERED} · đang giữ trước {metrics.voucherCounts.RESERVED} · đã sử dụng {metrics.voucherCounts.SETTLED} · đã giải phóng {metrics.voucherCounts.RELEASED}</small></div>}
    </InspectorSection>
    {projection && <InspectorSection title="Chi tiết xe và yêu cầu đặt xe" selection={(session.selectedBookingId ?? "") + (session.selectedVehicleId ?? "")}><h2>Xe / yêu cầu đặt xe · {session.arm === "baseline" ? "Baseline" : "Treatment"}</h2><p className="small-note">Vàng: đang đến đón khách · xanh: đang chở khách · xám: đang rảnh</p><div className="vehicle-list">{projection.vehicles.map(v => <button key={v.id} className={`booking-row ${session.selectedVehicleId === v.id ? 'selected' : ''}`} aria-label={`Quan sát xe thí nghiệm ${v.id}`} onClick={() => { session.setSelectedVehicleId(v.id); session.setSelectedBookingId(v.activeBookingId); focus('vehicle',v.id) }}><strong>{v.id}</strong><span>{stateText(v.status)}</span><small>{v.activeBookingId ?? "Đang rảnh"} · {v.completedBookingIds.length} chuyến hoàn tất</small></button>)}</div>
      <div className="vehicle-list">{projection.bookings.filter(b => b.status !== 'scheduled').map(b => <button className="booking-row" key={b.id} aria-label={`Chọn yêu cầu thí nghiệm ${b.id}`} onClick={() => { session.setSelectedBookingId(b.id); session.setSelectedVehicleId(b.assignment?.vehicleId ?? null); focus('booking',b.id) }}><strong>{b.id}</strong><span>{stateText(b.status)}</span><small>{b.assignment?.vehicleId ?? (b.failureReason ? errorText(b.failureReason) : "Đang chờ xe")}</small></button>)}</div>
      {selected && <div className="selected-detail"><h3>{selected.id} · {stateText(selected.status)}</h3><p>Điểm đón {selected.pickup.map(p => p.toFixed(6)).join(', ')}<br/>Điểm trả {selected.dropoff.map(p => p.toFixed(6)).join(', ')}<br/>Chờ {numberText(selected.waitingSeconds, 1) ?? '—'} giây · ETA {numberText(selected.assignment?.estimatedPickupEtaSeconds, 1) ?? '—'} giây</p></div>}
    </InspectorSection>}
  </div>
}
