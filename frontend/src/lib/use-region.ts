import { useCallback, useEffect, useRef, useState } from 'react'
import { api, regionApi, type DatasetStatus, type RegionMetadata } from './api'

const hcm: RegionMetadata = {
  id: 'hcm-center', label: 'Trung tâm TP.HCM · Quận 1 cũ',
  viewport: { center: [106.7, 10.7725], zoom: 14.2, bounds: [106.675, 10.750, 106.725, 10.795] },
  coverage: { operating: null, routing: null, render: null }, ready: false, mapReady: false,
  state: 'not_ready', reason: 'Đang kiểm tra dữ liệu khu vực.',
}

export function useRegion(saved: boolean, refreshKey: number) {
  const [regionId, setRegionId] = useState('hcm-center')
  const [regions, setRegions] = useState<RegionMetadata[]>([hcm])
  const [snapshot, setSnapshot] = useState<{ id: string; dataset: DatasetStatus } | null>(null)
  const [error, setError] = useState('')
  const currentRequest = useRef<AbortController | null>(null)
  const selectRegion = useCallback((id: string) => {
    currentRequest.current?.abort()
    setSnapshot(null); setError(''); setRegionId(id)
  }, [])

  useEffect(() => {
    if (saved) return
    const controller = new AbortController()
    api<{ regions: RegionMetadata[] }>('/api/regions', { signal: controller.signal })
      .then(data => {
        if (!Array.isArray(data.regions) || !data.regions.some(item => item.id === 'hcm-center')) throw new Error('INVALID_REGION_REGISTRY')
        if (!controller.signal.aborted) setRegions(data.regions)
      })
      .catch(() => { if (!controller.signal.aborted) setError('Không đọc được danh mục khu vực từ backend.') })
    return () => controller.abort()
  }, [saved, refreshKey])

  useEffect(() => {
    if (saved) return
    const controller = new AbortController(); currentRequest.current = controller
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const dataset = await api<DatasetStatus>(regionApi(regionId, '/dataset/status'), { signal: controller.signal })
        if ((dataset.regionId && dataset.regionId !== regionId) || (regionId !== 'hcm-center' && !dataset.regionId)) throw new Error('REGION_RESPONSE_MISMATCH')
        if (!controller.signal.aborted) { setSnapshot({ id: regionId, dataset }); setError('') }
      } catch {
        if (!controller.signal.aborted) { setSnapshot(null); setError('Backend chưa kết nối hoặc phản hồi không đúng khu vực. Kiểm tra FastAPI cục bộ.') }
      } finally { if (!controller.signal.aborted) timer = setTimeout(poll, 10000) }
    }
    void poll()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [regionId, saved, refreshKey])

  return { regionId, regions, selectRegion,
    metadata: regions.find(region => region.id === regionId),
    dataset: !saved && snapshot?.id === regionId ? snapshot.dataset : null,
    connectionError: saved ? '' : error }
}
