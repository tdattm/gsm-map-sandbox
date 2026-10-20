import { useEffect, useState } from 'react'
import { Dialog } from '@base-ui/react/dialog'
import { Button } from './ui/button'
import { api, ApiError } from '@/lib/api'
import { connectedBase } from '@/lib/connected-simulation'
import type { SimulationJob } from '@/lib/simulation'

export function ConnectedRunDialog({busy,onOpen,onClose}:{busy:boolean;onOpen:(id:string)=>void;onClose:()=>void}) {
  const [id,setId]=useState(''),[jobs,setJobs]=useState<SimulationJob[]|null>(null),[error,setError]=useState(''),[unavailable,setUnavailable]=useState(false),[retry,setRetry]=useState(0)
  useEffect(()=>{
    const controller=new AbortController()
    api<{jobs:SimulationJob[]}>(connectedBase,{signal:controller.signal}).then(data=>{
      if(controller.signal.aborted)return
      if(!Array.isArray(data.jobs))throw new Error('Danh sách run không hợp lệ.')
      setJobs(data.jobs.filter(job=>job.status==='COMPLETED'&&typeof job.id==='string'&&job.config?.schemaVersion==='gsm-nvmr-connected-scenario/v1'))
    }).catch(e=>{if(!controller.signal.aborted){setUnavailable(e instanceof ApiError&&[404,503].includes(e.status));setError(e instanceof Error?e.message:String(e))}})
    return ()=>controller.abort()
  },[retry])
  const open=(value:string)=>{onOpen(value.trim());onClose()}
  return <Dialog.Popup className="connected-run-dialog"><div className="connected-section-heading"><Dialog.Title>Mở run v5 đã lưu</Dialog.Title><Dialog.Close render={<Button variant="ghost" size="sm"/>}>Đóng</Dialog.Close></div>
    {error?<div role={unavailable?'status':'alert'} className="connected-run-error">{unavailable?'Danh sách run chưa khả dụng.':`Không tải được danh sách: ${error}`} <Button size="sm" variant="ghost" onClick={()=>{setJobs(null);setError('');setUnavailable(false);setRetry(n=>n+1)}}>Thử lại</Button></div>:jobs===null?<p role="status">Đang tải danh sách…</p>:!jobs.length?<p role="status">Chưa có run hoàn tất.</p>:<ul className="connected-run-list" aria-label="Runs Connected đã hoàn tất">{jobs.map(job=><li key={job.id}><button disabled={busy} onClick={()=>open(job.id)}><span><strong>{String(job.config?.fleetSize??'—')} xe</strong><span>{String(job.config?.bookingCount??'—')} yêu cầu · Hoàn tất</span></span><small title={job.id}>{String(job.config?.seed??job.id).slice(0,40)} · {job.id.slice(0,8)}</small></button></li>)}</ul>}
    <form className="connected-run-manual" onSubmit={e=>{e.preventDefault();open(id)}}><label>Mã run<input aria-label="Mã run Connected NVMR" required value={id} onChange={e=>setId(e.target.value)} placeholder="Nhập ID nếu cần"/></label><Button type="submit" disabled={busy||!id.trim()}>Mở run liên thông</Button></form>
  </Dialog.Popup>
}
