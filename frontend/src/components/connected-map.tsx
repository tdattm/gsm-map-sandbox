import { useEffect } from 'react'
import { useMap } from './ui/map'
import type { MapHealth } from './simulation-map-health'
import { connectedBounds } from '@/lib/map-style'
import { api } from '@/lib/api'

export function ConnectedCamera() {
  const {map,isLoaded}=useMap()
  useEffect(()=> {
    if (!map || !isLoaded) return
    const [w,s,e,n]=connectedBounds
    // Fit once per map/style lifetime, never on playback or vehicle filter updates.
    const frame=requestAnimationFrame(()=>{map.resize();map.fitBounds([[w,s],[e,n]],{padding:35,duration:0})})
    return ()=>cancelAnimationFrame(frame)
  },[map,isLoaded])
  return null
}
export function ConnectedMapHealth({onChange}:{onChange:(health:MapHealth)=>void}) {
  const {map,isLoaded}=useMap()
  useEffect(()=> {
    // Failed initial tiles can prevent MapLibre's load event. Subscribe and
    // query the artifact as soon as the instance exists, including that case.
    if (!map) return
    const started=performance.now();let failure='',previous='',artifactReady=false
    const controller=new AbortController()
    const publish=()=> {
      const ready=isLoaded&&artifactReady&&!!map.getSource('connected-basemap')&&map.isSourceLoaded('connected-basemap')&&!!map.getLayer('roads')
      const state=failure?'error':ready?'ready':'loading'
      const message=failure||(ready?'Bản đồ OSM miền Bắc · vector tiles cục bộ đã tải cho viewport':'Đang tải vector tiles miền Bắc cho viewport…')
      if (state+message!==previous) {previous=state+message;onChange({state,message,loaded:ready?1:0,milliseconds:performance.now()-started})}
    }
    const error=(event:{error?:{message:string};sourceId?:string})=> {failure=`Không tải được dữ liệu bản đồ${event.sourceId?` (${event.sourceId})`:''}: ${event.error?.message??'Kiểm tra artifact tiles, API và WebGL.'}`;publish()}
    const lost=()=>{failure='Mất ngữ cảnh WebGL. Kiểm tra GPU/RAM rồi tải lại bản đồ.';publish()}
    void api<{ready:boolean;reason?:string}>('/api/v5/connected/map/status',{signal:controller.signal}).then(status=>{if (!controller.signal.aborted) {artifactReady=status.ready;if (!status.ready) failure=`Bản đồ Connected NVMR chưa sẵn sàng: ${status.reason??'Thiếu artifact/manifest hợp lệ.'}`;publish()}}).catch(e=>{if (!controller.signal.aborted) {failure=`Không đọc được trạng thái basemap: ${String(e)}`;publish()}})
    const observer=new ResizeObserver(()=>map.resize());observer.observe(map.getContainer())
    const timeout=window.setTimeout(()=>{if (!failure&&(!map.getSource('connected-basemap')||!map.isSourceLoaded('connected-basemap'))) {failure='Vector tiles tải quá 20 giây. Kiểm tra basemap manifest và API tiles cục bộ.';publish()}},20000)
    map.on('sourcedata',publish);map.on('styledata',publish);map.on('error',error);map.getCanvas().addEventListener('webglcontextlost',lost);publish()
    return ()=>{controller.abort();clearTimeout(timeout);observer.disconnect();map.off('sourcedata',publish);map.off('styledata',publish);map.off('error',error);map.getCanvas().removeEventListener('webglcontextlost',lost)}
  },[map,isLoaded,onChange])
  return null
}
