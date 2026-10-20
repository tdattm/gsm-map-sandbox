import { useEffect, useRef, useState } from 'react'
import { api, type RegionMetadata } from './api'
import { FleetClock } from './fleet-clock'
import { presentationPolicy, type PresentationProfile } from './simulation-profile'
import { validateBookingDetail, validateSimulationRoute, type BookingDetail, type SelectedJourney, type SimulationJob, type SimulationRoute } from './simulation'
import { regionalBase as base, validateRegionalResult, validateRegionalSnapshot, type RegionalConfig, type RegionalResult, type RegionalSnapshot } from './regional-simulation'

const terminal = (status: string) => ['COMPLETED', 'CANCELLED', 'FAILED', 'INTERRUPTED'].includes(status)
const message = (error: unknown) => error instanceof Error ? error.message : String(error)

export function useRegionalSimulation(profile: PresentationProfile) {
  const [clock] = useState(() => new FleetClock())
  const [job, setJob] = useState<SimulationJob | null>(null)
  const [result, setResult] = useState<RegionalResult | null>(null)
  const [snapshot, setSnapshot] = useState<RegionalSnapshot | null>(null)
  const [regions, setRegions] = useState<RegionMetadata[]>([])
  const [regionId, setRegionId] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [journey, setJourney] = useState<SelectedJourney | null>(null)
  const [error, setError] = useState(''), [routeError, setRouteError] = useState('')
  const [loading, setLoading] = useState(false), [detailLoading, setDetailLoading] = useState(false)
  const [retryEpoch, setRetryEpoch] = useState(0)
  const [snapshotEpoch, setSnapshotEpoch] = useState(0)
  const epoch = useRef(0), submitting = useRef(false), requests = useRef(new Set<AbortController>())
  const configuredRun = useRef<string | null>(null)
  const policy = presentationPolicy[profile]
  useEffect(() => { clock.setPresentationHz(policy.clockHz) }, [clock, policy])
  useEffect(() => () => {requests.current.forEach(c => c.abort()); clock.dispose()}, [clock])
  useEffect(() => {
    const controller = new AbortController()
    api<{regions: RegionMetadata[]}>('/api/regions', {signal: controller.signal}).then(v => {
      if (!controller.signal.aborted) setRegions(v.regions.filter(r => r.id === 'nvmr-hanoi-core' || r.id === 'nvmr-bac-ninh-core'))
    }).catch(e => {if (!controller.signal.aborted) setError(message(e))})
    return () => controller.abort()
  }, [retryEpoch])
  const reset = () => {
    epoch.current++; requests.current.forEach(c => c.abort()); requests.current.clear()
    configuredRun.current = null
    clock.configure(0); setJob(null); setResult(null); setSnapshot(null); setJourney(null); setSelectedId(null); setError(''); setRouteError(''); setLoading(false)
  }
  const create = async (config: RegionalConfig) => {
    if (submitting.current || job && !terminal(job.status)) return
    submitting.current = true; reset(); setLoading(true)
    const version = epoch.current, controller = new AbortController(); requests.current.add(controller)
    try {
      const next = await api<SimulationJob>(base, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config), signal: controller.signal})
      if (!controller.signal.aborted && epoch.current === version) setJob(next)
    } catch (e) {if (!controller.signal.aborted && epoch.current === version) setError(message(e))}
    finally {submitting.current = false; requests.current.delete(controller); if (epoch.current === version) setLoading(false)}
  }
  const open = async (id: string) => {
    reset(); setLoading(true); const version = epoch.current, controller = new AbortController(); requests.current.add(controller)
    try {
      const next = await api<SimulationJob>(`${base}/${encodeURIComponent(id.trim())}`, {signal: controller.signal})
      if (!controller.signal.aborted && version === epoch.current) setJob(next)
    } catch (e) {if (!controller.signal.aborted && version === epoch.current) setError(message(e))}
    finally {requests.current.delete(controller); if (version === epoch.current) setLoading(false)}
  }
  useEffect(() => {
    if (!job || terminal(job.status)) return
    const controller = new AbortController(), version = epoch.current; requests.current.add(controller)
    let timer: number | undefined
    const poll = async () => {
      try {
        const next = await api<SimulationJob>(`${base}/${job.id}`, {signal: controller.signal})
        if (!controller.signal.aborted && version === epoch.current) {setJob(next); setError(''); if (!terminal(next.status)) timer = window.setTimeout(poll, 700)}
      } catch (e) {if (!controller.signal.aborted && version === epoch.current) {setError(message(e)); timer = window.setTimeout(poll, 2000)}}
    }
    void poll(); return () => {controller.abort(); requests.current.delete(controller); clearTimeout(timer)}
  }, [job?.id, job?.status, retryEpoch])
  useEffect(() => {
    if (job?.status !== 'COMPLETED') return
    const controller = new AbortController(); requests.current.add(controller)
    api<RegionalResult>(`${base}/${job.id}/result?summary=true`, {signal: controller.signal}).then(raw => {
      if (!controller.signal.aborted) {const value = validateRegionalResult(raw, job.id); setResult(value); if (configuredRun.current !== job.id) {clock.configure(value.simulationDurationSeconds); configuredRun.current = job.id} setError('')}
    }).catch(e => {if (!controller.signal.aborted) setError(message(e))})
    return () => {controller.abort(); requests.current.delete(controller)}
  }, [job?.id, job?.status, clock, retryEpoch])
  useEffect(() => {
    if (!result) return
    const controller = new AbortController(); requests.current.add(controller)
    let timer: number | undefined, inFlight = false, previous = '', lastStart = 0
    const wake = () => {if (timer === undefined && !controller.signal.aborted && !document.hidden) timer = window.setTimeout(poll, Math.max(0, policy.snapshotMs - (performance.now() - lastStart)))}
    const poll = async () => {
      timer = undefined
      if (inFlight || controller.signal.aborted || document.hidden) return
      const version = epoch.current, time = clock.getSnapshot().simulationTimeSeconds, key = `${version}:${time.toFixed(3)}`
      if (key === previous) return
      inFlight = true; lastStart = performance.now()
      try {
        const next = await api<RegionalSnapshot>(`${base}/${result.runId}/snapshot?timeSeconds=${time.toFixed(3)}`, {signal: controller.signal})
        if (!controller.signal.aborted && version === epoch.current) {validateRegionalSnapshot(next, result.runId); if (Math.abs(next.simulationTimeSeconds - time) > .001) throw new Error('REGIONAL_SNAPSHOT_TIME_MISMATCH'); previous = key; setSnapshot(next); setError('')}
      } catch (e) {if (!controller.signal.aborted && version === epoch.current) setError(message(e))}
      inFlight = false
      if (!controller.signal.aborted && previous === key) wake()
      else if (!controller.signal.aborted && clock.getSnapshot().playbackStatus === 'playing') timer = window.setTimeout(wake, 2000)
    }
    const unsubscribe = clock.subscribe(wake); document.addEventListener('visibilitychange', wake); void poll()
    return () => {controller.abort(); requests.current.delete(controller); clearTimeout(timer); unsubscribe(); document.removeEventListener('visibilitychange', wake)}
  }, [result, clock, policy, retryEpoch, snapshotEpoch])
  const selectRegion = (id: string | null) => {setRegionId(id); setSelectedId(null); setJourney(null); setRouteError('')}
  const selectVehicle = (id: string) => {
    const owner = snapshot?.regions.find(r => r.vehicles.some(v => v.id === id))
    if (owner) {setRegionId(owner.regionId); setSelectedId(id); setRouteError('')}
  }
  const regionalSnapshot = snapshot?.regions.find(r => r.regionId === regionId) ?? null
  const vehicle = regionalSnapshot?.vehicles.find(v => v.id === selectedId)
  const bookingId = vehicle?.activeBookingId
  useEffect(() => {
    setJourney(null); setRouteError(''); setDetailLoading(false)
    if (!regionalSnapshot || !vehicle || !bookingId) return
    const controller = new AbortController(); requests.current.add(controller); setDetailLoading(true)
    const root = `${base}/${regionalSnapshot.runId}`
    const route = async (ref: string) => validateSimulationRoute(await api<SimulationRoute>(`${root}/routes/${encodeURIComponent(ref)}`, {signal: controller.signal}), regionalSnapshot, {...vehicle, routeRef: ref})
    void (async () => {
      try {
        const detail = validateBookingDetail(await api<BookingDetail>(`${root}/bookings/${encodeURIComponent(bookingId)}`, {signal: controller.signal}), regionalSnapshot, vehicle)
        const [pickupRoute, tripRoute] = await Promise.all([detail.pickupLeg.routeRef ? route(detail.pickupLeg.routeRef) : null, route(detail.tripLeg.routeRef!)])
        if (!controller.signal.aborted) setJourney({detail, pickupRoute, tripRoute})
      } catch (e) {if (!controller.signal.aborted) setRouteError(message(e))}
      finally {if (!controller.signal.aborted) setDetailLoading(false)}
    })()
    return () => {controller.abort(); requests.current.delete(controller)}
  }, [regionalSnapshot?.runId, regionId, selectedId, bookingId, retryEpoch])
  const currentJourney = journey?.detail.vehicleId === vehicle?.id && journey?.detail.bookingId === bookingId && journey?.detail.runId === snapshot?.runId ? journey : null
  const seek = (time: number) => {epoch.current++; setSnapshot(null); setJourney(null); clock.seek(time); setSnapshotEpoch(n => n + 1)}
  const cancel = async () => {
    if (!job) return
    epoch.current++
    const controller = new AbortController(), version = epoch.current; requests.current.add(controller)
    try {const next = await api<SimulationJob>(`${base}/${job.id}/cancel`, {method: 'POST', signal: controller.signal}); if (!controller.signal.aborted && version === epoch.current) setJob(next)}
    catch (e) {if (!controller.signal.aborted && version === epoch.current) {setError(message(e)); setRetryEpoch(n => n + 1)}} finally {requests.current.delete(controller)}
  }
  return {clock, job, result, snapshot, regions, regionId, selectRegion, selectVehicle, selectedId, regionalSnapshot, vehicle,
    journey: currentJourney, route: currentJourney ? vehicle?.serviceState === 'ASSIGNED' ? currentJourney.pickupRoute : currentJourney.tripRoute : null,
    error, routeError, loading, detailLoading, create, open, cancel, seek, reset, retry: () => setRetryEpoch(n => n + 1)}
}
