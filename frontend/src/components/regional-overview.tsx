import { useEffect, useMemo } from 'react'
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import { useMap } from './ui/map'
import type { RegionMetadata } from '@/lib/api'
import type { RegionalSnapshot } from '@/lib/regional-simulation'
import { regionLabel } from '@/lib/regional-simulation'

/** Only verified registry rectangles and summary counts; no detailed road downloads. */
export function RegionalOverview({regions, snapshot, onSelect}: {regions: RegionMetadata[]; snapshot: RegionalSnapshot | null; onSelect: (id: string) => void}) {
  const {map, isLoaded} = useMap()
  const data = useMemo((): GeoJSON.FeatureCollection => ({type: 'FeatureCollection', features: regions.flatMap(region => {
    const bbox = region.coverage.operating
    if (!bbox) return []
    const [w, s, e, n] = bbox, live = snapshot?.regions.find(r => r.regionId === region.id)
    const car = live?.vehicles.filter(v => v.vehicleType === 'CAR').length ?? 0
    const bike = live?.vehicles.filter(v => v.vehicleType === 'MOTORBIKE').length ?? 0
    const properties = {id: region.id, label: `${regionLabel(region.id)}\n${live?`${car} CAR · ${bike} MOTORBIKE`:'Chưa mở run'}`, kind: 'extent'}
    return [
      {type: 'Feature' as const, properties, geometry: {type: 'Polygon' as const, coordinates: [[[w,s],[e,s],[e,n],[w,n],[w,s]]]}},
      {type: 'Feature' as const, properties: {...properties, kind: 'label'}, geometry: {type: 'Point' as const, coordinates: [(w+e)/2,(s+n)/2]}},
    ]
  })}), [regions, snapshot])
  useEffect(() => {
    if (!map || !isLoaded) return
    map.addSource('regional-extents', {type: 'geojson', data: {type:'FeatureCollection',features:[]}})
    map.addLayer({id: 'regional-fill', type: 'fill', source: 'regional-extents', filter: ['==', ['get','kind'], 'extent'], paint: {'fill-color': '#278b75', 'fill-opacity': .15}})
    map.addLayer({id: 'regional-outline', type: 'line', source: 'regional-extents', filter: ['==', ['get','kind'], 'extent'], paint: {'line-color': '#176b64', 'line-width': 2, 'line-dasharray': [3,2]}})
    map.addLayer({id: 'regional-label', type: 'symbol', source: 'regional-extents', filter: ['==', ['get','kind'], 'label'], layout: {'text-field': ['get','label'], 'text-font': ['Geist'], 'text-size': 14, 'text-allow-overlap': true}, paint: {'text-color': '#153f38', 'text-halo-color': '#fff', 'text-halo-width': 2}})
    return () => {
      if (!map.getStyle()) return
      for (const id of ['regional-label','regional-outline','regional-fill']) if (map.getLayer(id)) map.removeLayer(id)
      if (map.getSource('regional-extents')) map.removeSource('regional-extents')
    }
    // Recreate on style load, update data separately on playback.
  }, [map, isLoaded])
  useEffect(() => {if (map && isLoaded) (map.getSource('regional-extents') as GeoJSONSource | undefined)?.setData(data)}, [map, isLoaded, data])
  useEffect(() => {
    if (!map || !isLoaded) return
    const clicked = (event: MapMouseEvent) => {
      const id = map.queryRenderedFeatures(event.point, {layers: ['regional-fill','regional-label']})[0]?.properties.id
      if (typeof id === 'string') onSelect(id)
    }
    map.on('click', clicked)
    return () => {map.off('click', clicked)}
  }, [map, isLoaded, onSelect])
  useEffect(() => {
    if (!map || !isLoaded || !regions.length) return
    const boxes = regions.map(r => r.viewport.bounds)
    const fit = () => {
      map.resize()
      map.stop()
      map.fitBounds([[Math.min(...boxes.map(b => b[0])), Math.min(...boxes.map(b => b[1]))], [Math.max(...boxes.map(b => b[2])), Math.max(...boxes.map(b => b[3]))]], {padding: 40, duration: 0})
      const bounds = map.getBounds()
      map.getCanvas().dataset.regionalOverviewContainsBoth = String(boxes.every(b => bounds.contains([b[0],b[1]]) && bounds.contains([b[2],b[3]])))
    }
    // Fit after the style/layout transition; overview has no detailed map-health
    // observer. Resize only refits the geographic overview, never playback ticks.
    const frame = requestAnimationFrame(fit)
    const observer = new ResizeObserver(fit)
    observer.observe(map.getContainer())
    return () => {cancelAnimationFrame(frame); observer.disconnect(); delete map.getCanvas().dataset.regionalOverviewContainsBoth}
  }, [map, isLoaded, regions])
  return null
}

export function RegionalCamera({region}: {region: RegionMetadata}) {
  const {map, isLoaded} = useMap()
  useEffect(() => {if (map && isLoaded) {map.resize(); map.fitBounds([[region.viewport.bounds[0],region.viewport.bounds[1]], [region.viewport.bounds[2],region.viewport.bounds[3]]], {padding: 35, duration: 0})}}, [map, isLoaded, region])
  return null
}
