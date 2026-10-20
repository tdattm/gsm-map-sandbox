import { memo, useEffect, useId, useState } from 'react'
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent, type ChartConfig } from './ui/chart'
import { Button } from './ui/button'
import { api } from '@/lib/api'
import { connectedBase } from '@/lib/connected-simulation'
import { fleetStates, simulationTimestamp, validateFleetStateSeries, type FleetStateSeries } from '@/lib/connected-analytics'

const config={
  OFFLINE:{label:'Offline',color:'#aab5af'}, IDLE:{label:'Rảnh',color:'#70ad99'},
  ASSIGNED:{label:'Đến đón',color:'#d8a14c'}, ON_TRIP:{label:'Chở khách',color:'#387f96'},
} satisfies ChartConfig
// Small immutable aggregate cache, never a vehicle/geometry cache.
const cache=new Map<string,FleetStateSeries>()
export const ConnectedFleetChart=memo(function ConnectedFleetChart({runId,fleetSize,duration}:{runId:string;fleetSize:number;duration:number}) {
  const [series,setSeries]=useState<FleetStateSeries|null>(()=>cache.get(runId)??null)
  const [error,setError]=useState(''),[retry,setRetry]=useState(0)
  const gradient=useId().replace(/[^a-zA-Z0-9]/g,'')
  useEffect(()=>{
    const existing=cache.get(runId)
    if(existing)return
    const controller=new AbortController()
    api<FleetStateSeries>(`${connectedBase}/${encodeURIComponent(runId)}/analytics/fleet-states`,{signal:controller.signal})
      .then(raw=>{if(controller.signal.aborted)return;const data=validateFleetStateSeries(raw,runId,fleetSize,duration);cache.set(runId,data);if(cache.size>4)cache.delete(cache.keys().next().value!);setSeries(data)})
      .catch(e=>{if(!controller.signal.aborted)setError(e instanceof Error?e.message:String(e))})
    return ()=>controller.abort()
  },[runId,fleetSize,duration,retry])
  return <section className="simulation-card connected-chart-section" aria-label="Trạng thái đội xe theo thời gian"><div className="connected-section-heading"><h2>Trạng thái đội xe</h2>{series&&<span title={series.sampled?'Chọn các mốc sự kiện có thật; các chuyển trạng thái ở giữa không được biểu diễn.':'Từ timeline đã lưu'}>{series.points.length} mốc{series.sampled?' chọn lọc':''}</span>}</div>
    {error?<div role="alert">Chưa có chuỗi thời gian hợp lệ. <Button variant="ghost" size="sm" title={error} onClick={()=>{setError('');setRetry(n=>n+1)}}>Thử lại</Button></div>:!series?<p role="status">Đang đọc timeline…</p>:<ChartContainer config={config} className="connected-fleet-chart">
      <AreaChart accessibilityLayer data={series.points} margin={{left:0,right:12,top:12,bottom:0}}>
        <defs>{fleetStates.map(state=><linearGradient key={state} id={`${gradient}-${state}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={`var(--color-${state})`} stopOpacity={.8}/><stop offset="100%" stopColor={`var(--color-${state})`} stopOpacity={.35}/></linearGradient>)}</defs>
        <CartesianGrid vertical={false}/>
        <XAxis dataKey="timeSeconds" type="number" domain={[0,duration]} tickFormatter={simulationTimestamp} minTickGap={35} tickLine={false} axisLine={false} tickMargin={8}/>
        <YAxis width={36} domain={[0,fleetSize]} allowDecimals={false} tickLine={false} axisLine={false}/>
        <ChartTooltip cursor={false} content={<ChartTooltipContent labelFormatter={(_,payload)=>`${simulationTimestamp(Number(payload[0]?.payload.timeSeconds??0))} · ${Number(payload[0]?.payload.timeSeconds??0).toLocaleString('vi-VN',{maximumFractionDigits:3})} s`} indicator="dot"/>}/>
        <ChartLegend content={<ChartLegendContent/>}/>
        {fleetStates.map(state=><Area key={state} dataKey={state} type="stepAfter" stackId="fleet" fill={`url(#${gradient}-${state})`} stroke={`var(--color-${state})`} strokeWidth={1.5} isAnimationActive={false}/>)}
      </AreaChart>
    </ChartContainer>}
  </section>
})
