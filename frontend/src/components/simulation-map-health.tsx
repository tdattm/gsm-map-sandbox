import { Component, useEffect, type ReactNode } from 'react'
import { useMap } from './ui/map'

export interface MapHealth { state: 'loading' | 'ready' | 'error' | 'blank'; message: string; loaded: number; milliseconds: number }
const assets = ['streets', 'water', 'green', 'buildings', 'places']

// Asset readiness is independent of the worker and of OSRM readiness.
export function SimulationMapHealth({ enabled, onChange }: { enabled: boolean; onChange: (value: MapHealth) => void }) {
  const { map } = useMap()
  useEffect(() => {
    if (!map) return
    const begun = performance.now()
    let failed = '', previous = ''
    const verified = new Set<string>()
    const publish = () => {
      for (const id of assets) if (map.getSource(id) && map.isSourceLoaded(id)) verified.add(id)
      const loaded = verified.size
      const state = failed ? 'error' : !enabled ? 'blank' : loaded === assets.length && !!map.getLayer('roads') ? 'ready' : 'loading'
      const message = failed || (state === 'ready' ? 'Bản đồ Hà Nội sẵn sàng · 5/5 lớp địa lý' : state === 'blank' ? 'Nền trống · chỉ dành cho benchmark' : `Đang tải bản đồ Hà Nội · ${loaded}/5 lớp`)
      const key = state + message
      if (key !== previous) { previous = key; onChange({ state, message, loaded, milliseconds: performance.now() - begun }) }
    }
    const error = (event: { error?: { message: string }; sourceId?: string }) => {
      failed = event.sourceId && !assets.includes(event.sourceId)
        ? `Lỗi lớp hiển thị ${event.sourceId}: ${event.error?.message ?? 'Không tải được dữ liệu'}`
        : `Không tải được bản đồ Hà Nội${event.sourceId ? ` (${event.sourceId})` : ''}. Kiểm tra API / GeoJSON / WebGL. ${event.error?.message ?? ''}`
      publish()
    }
    const lost = () => { failed = 'Mất ngữ cảnh WebGL. Hãy thử tải lại bản đồ; kiểm tra tài nguyên GPU/RAM.'; publish() }
    const observer = new ResizeObserver(() => map.resize())
    observer.observe(map.getContainer())
    map.on('sourcedata', publish); map.on('styledata', publish); map.on('error', error)
    map.getCanvas().addEventListener('webglcontextlost', lost)
    const timeout = window.setTimeout(() => { if (enabled && verified.size < assets.length) { failed = 'Bản đồ tải quá 20 giây. Kiểm tra GeoJSON và Vite proxy; lỗi này độc lập với worker/OSRM.'; publish() } }, 20000)
    publish()
    return () => { clearTimeout(timeout); observer.disconnect(); map.off('sourcedata', publish); map.off('styledata', publish); map.off('error', error); map.getCanvas().removeEventListener('webglcontextlost', lost) }
  }, [map, enabled, onChange])
  return null
}

export class SimulationMapBoundary extends Component<{ children: ReactNode }, { error: string }> {
  state = { error: '' }
  static getDerivedStateFromError(error: Error) { return { error: error.message } }
  render() { return this.state.error ? <div role="alert" className="simulation-map-notice">Không khởi tạo được WebGL: {this.state.error}<button onClick={() => this.setState({ error: '' })}>Thử dựng lại bản đồ</button></div> : this.props.children }
}
