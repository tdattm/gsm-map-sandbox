import { useState } from 'react'
import { Button } from './ui/button'
import type { MapTelemetry } from './simulation-map'
import type { useConnectedSimulation } from '@/lib/use-connected-simulation'
import { download } from '@/lib/voucher'

/** Opt-in QA controls reuse the map's existing bounded instrumentation.
 * No fixture, new clock, route bulk download or additional presentation mode.
 */
export function ConnectedReplayDiagnostics({session,telemetry,closeAnalytics}:{session:ReturnType<typeof useConnectedSimulation>;telemetry:React.RefObject<MapTelemetry>;closeAnalytics:()=>void}) {
  const [at,setAt]=useState(900),[busy,setBusy]=useState(false),[rows,setRows]=useState<Record<string,unknown>[]>([])
  const measure=async(mapFirst:boolean)=>{
    setBusy(true)
    if(mapFirst)closeAnalytics()
    // Let the existing resize observer settle; keep the same map and clock.
    await new Promise(resolve=>setTimeout(resolve,600))
    session.clock.play()
    try {
      const row=await telemetry.current.measure(8,()=>{session.clock.pause();return session.clock.getSnapshot().simulationTimeSeconds},{pan:true})
      const requests=performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/v5/')).map(e=>{
        const r=e as PerformanceResourceTiming
        return {path:new URL(r.name).pathname+new URL(r.name).search,startMs:r.startTime,durationMs:r.duration,transferBytes:r.transferSize,decodedBytes:r.decodedBodySize}
      })
      setRows(previous=>[...previous,{...row,presentation:mapFirst?'A':'B',speed:session.clock.getSnapshot().speedMultiplier,requests}])
    }finally{setBusy(false)}
  }
  return <details className="simulation-card"><summary>Đo replay (QA)</summary>
    <label>Thời điểm kiểm tra (s)<input aria-label="QA thời điểm" type="number" min={0} max={session.result?.simulationDurationSeconds??0} value={at} onChange={e=>setAt(+e.target.value)}/></label>
    <Button disabled={busy||!session.result} onClick={()=>session.seek(at)}>QA seek</Button>
    {[6,11,16].map(zoom=><Button key={zoom} disabled={busy} onClick={()=>telemetry.current.zoomTo(zoom,zoom===16)}>QA zoom {zoom}</Button>)}
    <Button disabled={busy||!session.snapshot} onClick={()=>void measure(false)}>Đo State B 8s</Button>
    <Button disabled={busy||!session.snapshot} onClick={()=>void measure(true)}>Đo State A 8s</Button>
    <Button disabled={!rows.length||busy} onClick={()=>download('connected-replay-browser.json',JSON.stringify(rows,null,2),'application/json')}>Tải số đo replay</Button>
    <output aria-label="QA trạng thái">{busy?'Đang đo':'Sẵn sàng'} · {rows.length} số đo · {session.snapshot?.simulationTimeSeconds??0} s · {session.snapshot?.counts.total??0} xe · selected {session.selectedId??'—'}</output>
    {!!rows.length&&<pre data-testid="connected-replay-measurement">{JSON.stringify(rows,null,2)}</pre>}
  </details>
}
