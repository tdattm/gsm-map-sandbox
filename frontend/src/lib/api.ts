export type Coordinate = [number, number]
export interface DatasetStatus {
  state: string
  ready: boolean
  pbf: { state: string; path?: string; size_bytes: number | null; format_verified: boolean; osmium_available: boolean }
  artifacts: { map_ready: boolean; graph_ready: boolean; extracted_ready: boolean }
  osrm: { state: string; url?: string }
  region: { name: string; display_bbox: Bbox; routing_bbox: Bbox | null; source: string; attribution: string; boundary_note: string }
  regionId?: string
  viewport?: RegionViewport
  readinessReason?: string
}
export type Bbox = [number, number, number, number]
export interface RegionViewport { center: Coordinate; zoom: number; bounds: Bbox }
export interface RegionMetadata {
  id: string; label: string; viewport: RegionViewport
  coverage: { operating: Bbox | null; routing: Bbox | null; render: Bbox | null }
  ready: boolean; mapReady: boolean; state: string; reason: string
}
// Hooks retain their legacy default when no scope is supplied (including Saved).
export const regionApi = (regionId: string | undefined, path: string) => regionId && regionId !== 'hcm-center' ? `/api/regions/${encodeURIComponent(regionId)}${path}` : `/api${path}`
export function assertRegionProvenance(regionId: string | undefined, provenance: Record<string, unknown>) {
  if (regionId && (provenance.region_id ?? 'hcm-center') !== regionId) throw new Error('REGION_RESPONSE_MISMATCH: Phản hồi không đúng khu vực đang chọn.')
}
export interface Route {
  coordinates: Coordinate[]
  distance: number
  duration: number
  snap_points: { location: Coordinate; distance: number; name: string }[]
  duration_source: string
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, options)
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(data?.error ? `${data.error.code}: ${data.error.message}` : `API trả về HTTP ${response.status}`)
  }
  return response.json()
}
