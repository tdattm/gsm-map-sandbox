import { useCallback, useEffect, useRef, useState } from 'react'
import { api, regionApi, assertRegionProvenance } from './api'
import { FleetClock } from './fleet-clock'
import { validateBookingPlan, type BookingPlan, type BookingConfig } from './booking'
import { typesFor, validateMixed, type FleetMix, type MixedPlan, type MixedConfig } from './multimodal'

export function useBooking(active: boolean, ready: boolean, regionId?: string, mix: FleetMix = 'CAR') {
  const [clock] = useState(() => new FleetClock())
  const [plan, setPlan] = useState<BookingPlan | null>(null)
  const [multimodal,setMultimodal]=useState<MixedPlan | null>(null)
  const [loading, setLoading] = useState(false), [error, setError] = useState('')
  const [selectedBookingId, setSelectedBookingId] = useState<string | null>(null)
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null)
  const request = useRef<AbortController | null>(null)
  const clear = useCallback(() => { request.current?.abort(); clock.configure(0); setPlan(null); setMultimodal(null); setLoading(false); setError(''); setSelectedBookingId(null); setSelectedVehicleId(null) }, [clock])
  const scope = `${regionId}:${mix}`
  const previousScope = useRef(scope)
  useEffect(() => {
    const changed = previousScope.current !== scope; previousScope.current = scope
    if (!active || !ready || changed) clear()
  }, [active, ready, scope, clear])
  useEffect(() => () => { request.current?.abort(); clock.dispose() }, [clock])
  const generate = async (config: BookingConfig) => {
    if (!active || !ready) return
    clear(); const controller = new AbortController(); request.current = controller; setLoading(true)
    try {
      const explicit = mix !== 'CAR'
      const payload = explicit ? {...config,vehicleTypes:typesFor(mix,config.fleetSize),serviceTypes:typesFor(mix,config.bookingCount)} : config
      const response = await api<BookingPlan | MixedPlan>(explicit ? `/api/v2/regions/${regionId}/booking-simulation/prepare` : regionApi(regionId, '/booking-simulation/prepare'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: controller.signal })
      const result = explicit ? validateMixed(response as MixedPlan,regionId!,payload as MixedConfig) : response as BookingPlan
      controller.signal.throwIfAborted(); assertRegionProvenance(regionId, result.provenance); validateBookingPlan(result)
      if(explicit)setMultimodal(response as MixedPlan)
      setPlan(result); clock.configure(result.simulationDurationSeconds); setSelectedVehicleId(result.vehicles[0]?.id ?? null)
    } catch (error) { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : String(error)) }
    finally { if (!controller.signal.aborted) setLoading(false) }
  }
  return { clock, plan, multimodal, loading, error, generate, clear, selectedBookingId, setSelectedBookingId, selectedVehicleId, setSelectedVehicleId }
}
export type BookingSession = ReturnType<typeof useBooking>
