import { numberText } from '@/lib/vi'
import { errorText } from '@/lib/vi'
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpRight, Check, ChevronRight, Database, FileBox, FolderOpen, Layers, MapPin, Navigation, RefreshCw, Route as RouteIcon, Server, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { modeFromUrl, modeUrl, type AppMode } from '@/lib/navigation'
import { PrimaryNavigation } from '@/components/primary-navigation'
import { InspectorSection } from '@/components/inspector-section'
import { PlaybackDock, ClockDock } from '@/components/playback-dock'
import { SandboxMap } from '@/components/sandbox-map'
import { api, regionApi, type Coordinate, type Route } from '@/lib/api'
import { usePlayback } from '@/lib/use-playback'
import './App.css'
import { useFleet } from '@/lib/use-fleet'
import { FleetPanel, type FleetFocus } from '@/components/fleet-panel'
import { RuntimeAudit } from '@/components/runtime-audit'
import { useBooking } from '@/lib/use-booking'
import { BookingPanel, type BookingFocus } from '@/components/booking-panel'

import { useModes, modeRoute, type FleetMix } from '@/lib/multimodal'
import { useRegion } from '@/lib/use-region'
import { useVoucher } from '@/lib/use-voucher'
import { VoucherPanel } from '@/components/voucher-panel'
import { savedMapStyle } from '@/lib/map-style'
const VoucherDashboard = lazy(() => import('@/components/voucher-dashboard'))
const SimulationWorkspace = lazy(() => import('@/components/simulation-workspace'))

const coordinateText = (point: Coordinate | null) => point ? point.map(v => v.toFixed(6)).join(', ') : 'Chưa chọn trên bản đồ'
const pbfLabels: Record<string, string> = { not_prepared: 'Chưa chuẩn bị dữ liệu khu vực', missing_pbf: 'Chưa có file PBF', present_unverified: 'Đã có file · chưa xác minh', invalid_extension: 'Sai phần mở rộng', unreadable_pbf: 'Không đọc được file', empty_pbf: 'File PBF rỗng' }

export default function App() {
  const [mapError, setMapError] = useState('')
  const [routeError, setRouteError] = useState('')
  const [start, setStart] = useState<Coordinate | null>(null)
  const [end, setEnd] = useState<Coordinate | null>(null)
  const [route, setRoute] = useState<Route | null>(null)
  const [routing, setRouting] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [mode, setMode] = useState<AppMode>(()=>modeFromUrl(window.location.search))
  const [voucherRuntime,setVoucherRuntime]=useState<'live'|'saved'>(()=>new URLSearchParams(window.location.search).get('runtime')==='saved'?'saved':'live')
  const saved=mode==='voucher' && voucherRuntime==='saved'
  const region = useRegion(saved, refreshKey)
  const { dataset, connectionError, regionId } = region
  const [navigationSize, setNavigationSize] = useState<'expanded' | 'collapsed' | 'hidden'>('expanded')
  const [mobileMenu, setMobileMenu] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [mobileView, setMobileView] = useState<'map' | 'analytics'>('map')
  const [bookingFocus, setBookingFocus] = useState<BookingFocus | null>(null)
  const [fleetFocus, setFleetFocus] = useState<FleetFocus | null>(null)
  const request = useRef<AbortController | null>(null)
  const playback = usePlayback(route)
  const [service,setService]=useState<FleetMix>('CAR')
  const modeMetadata=useModes(regionId,saved || service==='CAR' || mode==='voucher',refreshKey)
  const modeReady=service==='CAR' || (regionId==='nvmr-hanoi-core' && modeMetadata.some(m=>m.vehicleType==='MOTORBIKE' && m.ready))
  const ready = (mode==='voucher' || service==='CAR' ? !!dataset?.ready : modeReady && !!dataset?.artifacts.map_ready && (service!=='MIXED' || !!dataset?.ready)) && !connectionError && !mapError
  const fleet = useFleet(mode === 'fleet', ready, regionId,service)
  const booking = useBooking(mode === 'booking', ready, regionId,service)
  const voucher = useVoucher(mode === 'voucher', ready, voucherRuntime, regionId)
  const replayStyle=useMemo(()=>{if(!saved || !voucher.replayAssets) return undefined; const style=savedMapStyle(voucher.replayAssets); return {light:style,dark:style}},[saved,voucher.replayAssets])
  const voucherReady=saved ? !!voucher.artifact && !!voucher.replayAssets && !mapError : ready
  const focusVehicle = (id: string, kind: FleetFocus['kind']) => { fleet.setSelectedVehicleId(id); setFleetFocus({ id, kind, sequence: performance.now() }) }
  const changeMode = (next: AppMode, fromHistory = false) => { if (next === mode) return; playback.pause(); clear(); fleet.clear(); booking.clear(); voucher.clear(); setFleetFocus(null); setBookingFocus(null); if(next==='single' && service==='MIXED')setService('CAR'); setMapError(''); setMode(next); if(!fromHistory)window.history.pushState(null,'',modeUrl(window.location.href,next,voucherRuntime)) }
  useEffect(()=>{const pop=()=>{const runtime=new URLSearchParams(window.location.search).get('runtime');setVoucherRuntime(runtime==='saved'?'saved':'live');changeMode(modeFromUrl(window.location.search),true)};window.addEventListener('popstate',pop);return ()=>window.removeEventListener('popstate',pop)},[mode,voucherRuntime,service])
  const mapReady = saved ? !!replayStyle : !!dataset?.artifacts.map_ready
  const pbfPresent = ['present_unverified', 'present_verified'].includes(dataset?.pbf.state ?? '')

  const clear = useCallback(() => {
    request.current?.abort(); setRouting(false); setStart(null); setEnd(null); setRoute(null); setRouteError('')
  }, [])
  useEffect(() => { if (!ready) clear() }, [ready, clear])
  useEffect(() => () => request.current?.abort(), [])

  const changeRegion = (id: string) => {
    if (saved || id === regionId) return
    playback.pause(); clear(); fleet.clear(); booking.clear(); voucher.clear()
    setMapError(''); setFleetFocus(null); setBookingFocus(null); setService('CAR'); region.selectRegion(id)
  }

  const select = useCallback((point: Coordinate) => {
    if (!ready || !dataset?.region.routing_bbox) return
    request.current?.abort(); setRoute(null); setRouteError(''); setRouting(false)
    const [w, s, e, n] = dataset.region.routing_bbox
    if (point[0] < w || point[0] > e || point[1] < s || point[1] > n) { setStart(null); setEnd(null); setRouteError('Chọn điểm trong vùng tính tuyến đã cấu hình.'); return }
    if (!start || end) { setStart(point); setEnd(null) } else { setEnd(point) }
  }, [ready, dataset, start, end])

  useEffect(() => {
    if (!start || !end || !ready) return
    const controller = new AbortController(); request.current = controller; setRouting(true)
    const result = service==='MOTORBIKE' ? modeRoute(regionId,'MOTORBIKE',start,end,controller.signal,modeMetadata.find(m=>m.vehicleType==='MOTORBIKE')?.routingIdentity ?? undefined) : api<Route>(regionApi(regionId, '/route'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ start, end }), signal: controller.signal })
    result.then(data => { if (!controller.signal.aborted) setRoute(data) })
      .catch(error => { if (!controller.signal.aborted) setRouteError(error.message) })
      .finally(() => { if (!controller.signal.aborted) setRouting(false) })
    return () => controller.abort()
  }, [start, end, ready, regionId,service,modeMetadata])

  const refresh = () => { setMapError(''); setRefreshKey(value => value + 1) }
  const waitTitle = dataset?.readinessReason ? 'Khu vực chưa sẵn sàng' : connectionError ? 'Kết nối backend để bắt đầu' : !dataset ? 'Đang kiểm tra dữ liệu cục bộ' : !pbfPresent ? 'Thêm dữ liệu để mở bản đồ' : 'PBF đã có. Chờ chuẩn bị bản đồ.'
  const waitDescription = connectionError || dataset?.readinessReason || (!dataset ? 'Đang đọc cấu hình và tình trạng artifact.' : !pbfPresent ? 'Sao chép file Geofabrik đã tải vào đường dẫn bên dưới. Ứng dụng sẽ tự kiểm tra lại.' : 'Chưa có artifact GeoJSON hợp lệ. Chạy pipeline cục bộ theo README rồi kiểm tra lại.')

  return <div className={`app-shell nav-${navigationSize} ${inspectorOpen ? "inspector-open" : "inspector-closed"} mode-${mode} view-${mobileView}`}>
    {(import.meta.env.DEV || new URLSearchParams(window.location.search).get('audit')==='1') && <RuntimeAudit />}
    <header className="app-header">
      <Button variant="outline" aria-label="Mở menu chính" onClick={() => { if (window.matchMedia('(max-width: 900px)').matches) setMobileMenu(true); else setNavigationSize(navigationSize === 'hidden' ? 'expanded' : 'hidden') }}><Navigation size={18}/></Button>
      <div className="brand"><span className="brand-icon"><Navigation size={24} /></span><div><h1>GSM Map Sandbox</h1><span className="brand-subtitle">{mode === 'simulation' ? 'Mô phỏng quy mô lớn' : mode === 'voucher' ? "Phòng thí nghiệm voucher" : mode === 'booking' ? "Đặt xe và điều phối" : mode === 'fleet' ? "Mô phỏng đội xe" : "Một hành trình"}</span></div></div>
      {mode !== 'simulation' && <Button variant="outline" aria-label="Mở hoặc ẩn bảng chi tiết" aria-expanded={inspectorOpen} onClick={() => setInspectorOpen(!inspectorOpen)}>Chi tiết</Button>}
      {mode === 'voucher' && <div className="workspace-view" role="group" aria-label="Chế độ hiển thị"><Button size="sm" variant={mobileView === 'map' ? 'secondary' : 'outline'} onClick={() => setMobileView('map')}>Bản đồ</Button><Button size="sm" variant={mobileView === 'analytics' ? 'secondary' : 'outline'} onClick={() => setMobileView('analytics')}>Phân tích</Button></div>}
      <Badge variant="outline" className="local-badge"><span className="status-dot green" />Mô phỏng cục bộ</Badge>

      {mode === 'simulation' ? <div className="header-status">Hanoi Core · CAR + MOTORBIKE · phát lại mô hình</div> : <div className="header-status"><span><span className={mapReady && (saved || !connectionError) ? 'status-dot green' : 'status-dot amber'} />{mapReady ? 'Bản đồ cục bộ' : 'Chờ dữ liệu bản đồ'}</span><span><span className={dataset?.osrm.state === 'connected' && !connectionError ? 'status-dot green' : 'status-dot'} />{saved ? "Phát lại đã lưu · không cần tính tuyến trực tiếp" : 'OSRM'} {!saved && (dataset?.osrm.state === 'connected' && !connectionError ? 'kết nối' : 'chưa kết nối')}</span></div>}
    </header>
    <main className="workspace">
      <PrimaryNavigation mode={mode} size={navigationSize} onMode={next=>changeMode(next)} onSize={setNavigationSize} mobileOpen={mobileMenu} onMobileOpen={setMobileMenu}/>
      {mode === 'simulation' ? <Suspense fallback={<p role="status">Đang tải mô phỏng quy mô lớn…</p>}><SimulationWorkspace previousRegion={region.metadata?.label ?? regionId}/></Suspense> : <>
      <aside className="sidebar inspector" hidden={!inspectorOpen} aria-label="Cấu hình mô phỏng"><div className="inspector-toolbar"><strong>Cấu hình và chi tiết</strong><Button variant="ghost" size="sm" aria-label="Đóng bảng chi tiết" onClick={() => setInspectorOpen(false)}>×</Button></div>
        <InspectorSection title="Khu vực mô phỏng" defaultOpen>
          <label className="region-selector">Khu vực mô phỏng<select aria-label="Khu vực mô phỏng" value={saved ? 'hcm-center' : regionId} disabled={saved} onChange={event => changeRegion(event.target.value)}>{region.regions.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <p className="small-note" aria-live="polite">{saved ? 'Khu vực và bản đồ do gói phát lại HCM v1 quyết định; không cần backend.' : dataset?.ready ? 'Khu vực đã sẵn sàng cho mô phỏng trực tiếp.' : dataset?.readinessReason || connectionError || (dataset ? 'Khu vực chưa sẵn sàng. Kiểm tra dữ liệu và kết nối OSRM cục bộ.' : 'Đang kiểm tra dữ liệu khu vực.')}</p>
        </InspectorSection>
        {!saved && mode!=='voucher' && <InspectorSection title="Loại phương tiện" defaultOpen><label>Loại dịch vụ<select aria-label="Loại dịch vụ" value={service} onChange={e=>{playback.pause();clear();fleet.clear();booking.clear();setFleetFocus(null);setBookingFocus(null);setService(e.target.value as FleetMix)}}><option value="CAR">CAR · Ô tô điện</option><option value="MOTORBIKE" disabled={regionId!=='nvmr-hanoi-core'}>MOTORBIKE · Mô tô điện</option>{mode!=='single' && <option value="MIXED" disabled={regionId!=='nvmr-hanoi-core'}>Hỗn hợp CAR + MOTORBIKE</option>}</select></label><p aria-live="polite" className="small-note">{service==='CAR' ? 'CAR · định tuyến ô tô hiện có.' : modeReady ? 'MOTORBIKE pilot · mô tô điện 70 km/h thiết kế, giả định 6 kW. ETA mô hình, chưa hiệu chuẩn.' : 'MOTORBIKE NOT READY · kiểm tra profile, graph, validation và router riêng; CAR vẫn khả dụng.'}</p>{service==='MIXED' && <p className="small-note">Xe và yêu cầu xen kẽ CAR/MOTORBIKE, tổng số theo cấu hình bên dưới.</p>}</InspectorSection>}
        {!saved && mode==='voucher' && <p className="small-note">Voucher CAR v1 · thí nghiệm ô tô ghép cặp. Chưa hỗ trợ lựa chọn MOTORBIKE hoặc hành vi đổi loại xe.</p>}
        <InspectorSection title="Dữ liệu bản đồ">{saved ? <div><h2>Gói phát lại cục bộ</h2><p>© OpenStreetMap contributors · ODbL 1.0</p><p className="small-note">{voucher.replayAssets ? `Danh mục đã kiểm chứng ${voucher.replayAssets.manifest.id}` : "Nhập thí nghiệm hoặc tải kịch bản mẫu để kiểm chứng gói phát lại."}</p></div> : <><div className="section-heading"><Database size={17} /><h2>Dữ liệu bản đồ</h2></div>
          <div className="source-card"><div className="source-icon"><FileBox size={22} /></div><div><strong>Geofabrik Vietnam</strong><p>OpenStreetMap · nguồn PBF cục bộ</p></div><a href="https://download.geofabrik.de/asia/vietnam.html" target="_blank" rel="noreferrer" aria-label="Thông tin nguồn Geofabrik"><ArrowUpRight size={17} /></a></div>
          <div className="data-state"><span className={pbfPresent ? 'status-dot green' : 'status-dot amber'} /><span>{dataset?.pbf.format_verified ? 'PBF đã xác minh bằng Osmium' : dataset ? pbfLabels[dataset.pbf.state] ?? dataset.pbf.state : 'Đang kiểm tra file PBF…'}</span></div>
          <div className="data-detail">{dataset?.pbf.size_bytes ? numberText((dataset.pbf.size_bytes / 1024 / 1024), 1) + (dataset.pbf.format_verified ? ' MiB · nguồn Geofabrik cục bộ đã kiểm tra' : ' MiB · định dạng chưa xác minh bằng Osmium') : 'Đọc từ ổ đĩa · không tải lên qua trình duyệt'}</div>
          <div className="region-row"><MapPin size={17} /><div><strong>{dataset?.region.name ?? region.metadata?.label}</strong><p>{dataset?.region.boundary_note ?? region.metadata?.reason}</p></div></div>
          <div className="bbox-row">{(dataset?.region.display_bbox ?? region.metadata?.viewport.bounds ?? []).map(v => v.toFixed(3)).join(' / ')}</div>
          <p className="small-note">Vùng kỹ thuật thử nghiệm, không phải ranh giới hành chính.</p></>}
        </InspectorSection>
        {mode === 'voucher' ? <VoucherPanel docked session={voucher} ready={voucherReady} onRuntime={next=>{setMapError('');setVoucherRuntime(next);window.history.pushState(null,'',modeUrl(window.location.href,'voucher',next))}} onFocus={setBookingFocus} /> : mode === 'booking' ? <BookingPanel docked session={booking} ready={ready} onFocus={setBookingFocus} /> : mode === 'fleet' ? <FleetPanel docked fleet={fleet} ready={ready} onFocus={focusVehicle} /> : <><InspectorSection title="Thiết lập hành trình" defaultOpen><div className="section-heading"><RouteIcon size={17} /><h2>Thiết lập hành trình</h2><span className="section-number">01</span></div>
          <p className="section-description">Nhấp trên bản đồ để chọn A, sau đó chọn B.</p>
          <div className="endpoint"><span className="endpoint-label">A</span><div><label>Điểm xuất phát</label><p>{coordinateText(start)}</p></div></div>
          <div className="endpoint"><span className="endpoint-label end">B</span><div><label>Điểm đến</label><p>{coordinateText(end)}</p></div></div>
          <div className="route-metrics"><div><label>Quãng đường</label><strong>{route ? numberText((route.distance / 1000), 2) + ' km' : '—'}</strong></div><div><label>Thời gian di chuyển dự kiến</label><strong>{route ? numberText((route.duration / 60), 1) + ' phút' : '—'}</strong></div></div>
          <p className="small-note">Ước tính từ profile {service}, không phải giao thông thời gian thực.</p>
          {routing && <p role="status" className="small-note">Đang tính tuyến đường bằng OSRM cục bộ…</p>}
          {routeError && <p role="alert" className="error-text">{errorText(routeError)}</p>}
          {route && <p className="small-note">Độ lệch điểm A/B trên đường: {route.snap_points.map(point => numberText(point.distance, 1) + ' m').join(' / ')}</p>}
          {route && <details className="snap-details"><summary>Điểm đã khớp với đường</summary>{route.snap_points.map((point, i) => <p key={i}>{i ? 'B' : 'A'} · {point.name || 'Đường không tên'}<br />{coordinateText(point.location ?? null)}</p>)}</details>}
          <Button variant="outline" className="clear-button" disabled={!start && !end} onClick={clear}><Trash2 />Xóa điểm A/B và chọn lại</Button>
        </InspectorSection>
        </>}
        <div className="sidebar-footer"><Server size={14} />Chỉ chạy cục bộ<span>WGS84 · [lon, lat]</span></div>
      </aside>
      <div className="workspace-content">
      <section className="map-workspace" aria-label={saved ? "Bản đồ HCM phát lại" : `Bản đồ ${region.metadata?.label ?? regionId}`}>
        <div className="map-topbar"><div><span className="eyebrow">KHU VỰC NGHIÊN CỨU</span><h2>{saved ? "TP.HCM · phát lại đã lưu" : region.metadata?.label ?? regionId}</h2></div><Button variant="outline" onClick={refresh}><RefreshCw size={15} />Kiểm tra lại</Button></div>
        <div className="map-canvas">
          <SandboxMap vehicleType={service==='MOTORBIKE' ? 'MOTORBIKE':'CAR'} regionId={saved ? "hcm-center" : regionId} viewport={saved ? undefined : dataset?.viewport ?? region.metadata?.viewport} replayBounds={saved ? voucher.replayAssets?.manifest.displayBbox : undefined} replayStyle={replayStyle} dataset={saved ? null : dataset} start={mode === 'single' ? start : null} end={mode === 'single' ? end : null} route={mode === 'single' ? route : null} progress={playback.progress} enabled={ready && mode === 'single'} onSelect={select} onError={setMapError} fleet={mode === 'fleet' ? fleet : undefined} fleetFocus={fleetFocus} booking={mode === 'voucher' ? voucher.mapSession : mode === 'booking' ? booking : undefined} bookingFocus={bookingFocus} />
          <div className="map-chip"><Layers size={15} />{mapReady ? 'GeoJSON cục bộ · OSM' : "Bản đồ trống cục bộ"}<span className="chip-divider" />{mapReady ? 'Dữ liệu đường phố' : 'Chưa có lớp đường phố'}</div>
          {(!mapReady || mapError || (!saved && connectionError)) && <div className="waiting-overlay"><div className="waiting-card"><div className="waiting-icon"><FolderOpen size={32} /><span>{pbfPresent ? <Check size={13} /> : <Database size={13} />}</span></div><Badge variant="outline">{pbfPresent ? 'CHỜ TÀI NGUYÊN A1' : 'CHỜ DỮ LIỆU CỤC BỘ'}</Badge><h2>{saved ? "Nhập thí nghiệm đã lưu để phát lại" : waitTitle}</h2><p>{mapError || (saved ? "Phát lại đã lưu dùng tài nguyên cục bộ đã kiểm chứng, không cần FastAPI/OSRM. Mở bảng Chi tiết để nhập thí nghiệm hoặc tải kịch bản mẫu." : waitDescription)}</p><div className="file-path"><FolderOpen size={16} /><code>{saved ? "Gói phát lại cục bộ" : dataset?.pbf.path ?? 'Dữ liệu cục bộ của khu vực'}</code></div>{!saved && <div className="readiness-list"><div className={pbfPresent ? 'done' : ''}><span>{pbfPresent ? <Check size={12} /> : '1'}</span>File PBF cục bộ</div><ChevronRight size={13} /><div><span>2</span>GeoJSON bản đồ</div><ChevronRight size={13} /><div><span>3</span>OSRM MLD</div></div>}<Button variant="outline" onClick={refresh}><RefreshCw size={15} />Kiểm tra dữ liệu</Button><p className="waiting-footnote">Chỉ hiển thị đường phố sau khi xử lý dữ liệu OSM thật.</p></div></div>}
          <div className="map-bottom-note"><span className={ready ? 'status-dot green' : 'status-dot amber'} />{mode === 'voucher' ? `Thí nghiệm voucher · ${voucher.arm === "baseline" ? "Baseline" : "Treatment"} · giả định PoC` : mode === 'booking' ? 'Đặt xe mô phỏng · màu vàng: đến đón · xanh: chở khách · xám: rảnh' : mode === 'fleet' ? "Đội xe mô phỏng · không phải GPS thực tế · chọn xe để quan sát" : ready ? start ? end ? 'Nhấp để bắt đầu hành trình mới' : 'Chọn điểm B trên bản đồ' : 'Chọn điểm A trên bản đồ' : 'Chọn A/B đang khóa · dữ liệu hoặc bộ tính tuyến chưa sẵn sàng'}</div>
        </div>
        <footer className="map-footer"><span>© OpenStreetMap contributors · Geofabrik</span><span>Sandbox nghiên cứu · {mode === 'single' ? 'một xe mô phỏng' : 'đội xe mô phỏng'}</span></footer>
      </section>
      {mode === 'voucher' && <aside className="analytics-panel" aria-label="Phân tích chỉ số kinh doanh"><Suspense fallback={<p>Đang tải phòng thí nghiệm cục bộ…</p>}><VoucherDashboard session={voucher}/></Suspense></aside>}
      </div></> }
    </main>
    {mode !== 'simulation' && (mode === 'single' ? <PlaybackDock label="Một hành trình" enabled={!!route && ready} time={playback.progress * (route?.duration ?? 0)} duration={route?.duration ?? 0} status={playback.progress >= 1 ? 'completed' : playback.playing ? 'playing' : 'paused'} speed={playback.speed} play={playback.play} pause={playback.pause} reset={playback.reset} seek={time => playback.seek(route ? time/route.duration : 0)} setSpeed={playback.setSpeed}/> : <ClockDock key={mode} label={mode === 'fleet' ? "Mô phỏng đội xe" : mode === 'booking' ? "Đặt xe và điều phối" : "Thí nghiệm voucher"} clock={mode === 'fleet' ? fleet.clock : mode === 'booking' ? booking.clock : voucher.clock} duration={mode === 'fleet' ? fleet.scenario?.simulationDurationSeconds ?? 0 : mode === 'booking' ? booking.plan?.simulationDurationSeconds ?? 0 : voucher.experiment?.simulationDurationSeconds ?? 0} enabled={(mode === 'voucher' ? voucherReady : ready) && (mode === 'fleet' ? !!fleet.scenario && !fleet.loading : mode === 'booking' ? !!booking.plan && !booking.loading : !!voucher.experiment && !voucher.loading)}/>)}
  </div>
}

