import { useEffect, useState } from 'react'
import { Button } from './ui/button'

export function simulationErrorText(message:string) {
  if(/RESOURCE_PRESSURE|RESOURCE_STOP/.test(message))return 'RAM khả dụng hoặc commit headroom dưới ngưỡng của workload. Giải phóng bộ nhớ trước khi thử lại; số xe và booking không bị giảm ngầm.'
  if(/MODE_NOT_READY|GRAPH|IDENTITY_CHANGED/.test(message))return 'Graph/profile chưa sẵn sàng. Kiểm tra manifest và mode readiness; không dùng graph khác.'
  if(/NO_ROUTE|NoRoute|NoSegment|NO_SEGMENT/.test(message))return 'OSRM không tìm được tuyến cho cặp điểm này. Kiểm tra điểm snap và coverage.'
  if(/ROUTER_UNAVAILABLE|ROUTER_TIMEOUT|ROUTER_BAD_RESPONSE/.test(message))return 'Router OSRM không sẵn sàng hoặc trả lời không hợp lệ. Kiểm tra đúng router theo loại xe.'
  if(/HTTP 502|HTTP 503|Failed to fetch|Network|fetch failed|Load failed/i.test(message))return 'Backend FastAPI chưa kết nối. Kiểm tra API health và Vite proxy target; đây chưa phải bằng chứng lỗi simulation/OSRM.'
  return 'Không đọc/gửi được dữ liệu mô phỏng. Xem mã lỗi và kiểm tra dịch vụ tương ứng.'
}

export function SimulationRuntime({intervalMs=15000}:{intervalMs?:number}) {
  const [message,setMessage]=useState('Đang kiểm tra FastAPI…'),[retry,setRetry]=useState(0)
  const [resources,setResources]=useState('')
  useEffect(()=>{
    const controller=new AbortController();let timeout:number|undefined
    const check=async()=>{
      if(document.hidden)return
      try {
        const health=await fetch('/api/health',{signal:controller.signal}).then(async r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()})
        if(health.backend_ready!==true)throw new Error('API identity unavailable')
        const runtime=await fetch('/api/v3/simulation/jobs/runtime',{signal:controller.signal}).then(async r=>{if(r.status===404)return null;if(!r.ok)throw new Error(`Runtime HTTP ${r.status}`);return r.json()})
        if(controller.signal.aborted)return
        const r=runtime?.resources
        const p=r?.admissionPolicy
        const policy=p?`Tác vụ thường: ≤${p.lightMaximumFleet} xe/≤${p.lightMaximumBookings} yêu cầu cần ${p.lightMinimumAvailableGiB} GiB RAM / ${p.lightMinimumCommitGiB} GiB commit; tới 5.000 xe/≤${p.routineMaximumBookings} yêu cầu cần ${p.routineMinimumAvailableGiB} / ${p.routineMinimumCommitGiB} GiB. Horizon ≤${p.maximumHorizonSeconds}s, schedule ≤${p.maximumSchedulePoints}, candidates ≤${p.maximumCandidates}; ngoài phạm vi cần ${p.extendedMinimumAvailableGiB} / ${p.extendedMinimumCommitGiB} GiB.`:`API cũ: small ${r?.smallMinimumAvailableGiB??2} GiB RAM; khởi động lại API để xác minh policy đầy đủ.`
        setResources(r&&Number.isFinite(r.availablePhysicalBytes)?`RAM khả dụng ${(r.availablePhysicalBytes/1024**3).toFixed(2)} GiB · commit headroom ${Number.isFinite(r.systemCommitAvailableBytes)?(r.systemCommitAvailableBytes/1024**3).toFixed(2)+' GiB':'không đo được'}. ${policy} Đây là ảnh chụp, không phải reservation.`:'')
        setMessage(runtime?.application==='gsm-map-sandbox'?`FastAPI đã kết nối · Worker ${runtime.worker==='locked'?'giữ lease đúng store (không phải heartbeat)':runtime.worker==='offline'?'chưa chạy trên store API':'chưa xác minh được lease'}`:'FastAPI đã kết nối · API cũ chưa có runtime/store check; khởi động lại API để dùng S0/S1 đầy đủ.')
      }catch(e){if(!controller.signal.aborted)setMessage(`Backend FastAPI chưa kết nối · ${e instanceof Error?e.message:String(e)}. Kiểm tra terminal API và Vite proxy.`)}
      if(!controller.signal.aborted)timeout=window.setTimeout(check,intervalMs)
    }
    const visible=()=>{clearTimeout(timeout);if(!document.hidden)void check()}
    document.addEventListener('visibilitychange',visible)
    void check();return ()=>{controller.abort();clearTimeout(timeout);document.removeEventListener('visibilitychange',visible)}
  },[retry,intervalMs])
  return <div className="simulation-runtime"><p role="status">{message}</p>{resources&&<p className="small-note" data-testid="simulation-resource-status">{resources}</p>}<Button variant="outline" onClick={()=>setRetry(n=>n+1)}>Kiểm tra lại kết nối</Button><p className="small-note">Chỉ kiểm tra GET, không gửi lại job. QUEUED cũng có thể do worker đang bận.</p></div>
}
