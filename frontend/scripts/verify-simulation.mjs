// Cross-language contract proof against a completed real worker job.
// Uses the product TypeScript validator, without a second schema implementation.
import { build } from 'vite'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const root = resolve(frontend, '..')
const [origin, id, output = 'build/m3-m4/contract-verification.json'] = process.argv.slice(2)
if (!origin || !id || !/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(origin) || !/^[a-f0-9]{32}$/.test(id)) {
  throw new Error('Usage: node scripts/verify-simulation.mjs http://127.0.0.1:8013 JOB_ID [root-relative-output]')
}
const destination = resolve(root, output)
if (!destination.startsWith(root + '/') && !destination.startsWith(root + '\\')) throw new Error('Output must stay inside project')
await build({configFile:false,logLevel:'warn',build:{lib:{entry:resolve(frontend,'src/lib/simulation.ts'),formats:['es'],fileName:()=> 'simulation.mjs'},outDir:resolve(frontend,'.replay-tools'),emptyOutDir:false}})
const validators = await import(pathToFileURL(resolve(frontend,'.replay-tools/simulation.mjs')).href)
const base = `${origin}/api/v3/simulation/jobs/${id}`
const get = async path => {
  const response = await fetch(base + path)
  assert.equal(response.status, 200, `${path}: ${await response.clone().text()}`)
  return response.json()
}
const job = await get('')
assert.equal(job.status, 'COMPLETED')
const result = await get('/result')
const summary = await get('/result?summary=true')
assert.equal(summary.runId, id)
assert.ok(!('routes' in summary) && !('events' in summary))
assert.equal(result.counts.completed, result.events.filter(e => e.type === 'TRIP_COMPLETED').length)
assert.equal(result.counts.unserved, result.events.filter(e => e.type === 'BOOKING_UNSERVED').length)
assert.equal(result.counts.requested, result.counts.completed + result.counts.unserved)
const times = new Set([0, result.simulationDurationSeconds / 4, result.simulationDurationSeconds / 2, result.simulationDurationSeconds])
const samples = []
for (const mode of ['CAR', 'MOTORBIKE']) {
  const assignment = result.assignments.find(a => a.vehicleType === mode)
  if (assignment) times.add((assignment.pickupAtSeconds + assignment.dropoffAtSeconds) / 2)
}
const routeSamples = [],bookingSamples=[]
for (const time of [...times].sort((a,b) => a-b)) {
  const snapshot = validators.validateSnapshot(await get(`/snapshot?timeSeconds=${time}`), id, result.regionId)
  const gate = new validators.SnapshotGate(id, result.regionId)
  assert.equal(gate.accept(snapshot), true)
  assert.equal(gate.accept(snapshot), false)
  samples.push({time:snapshot.simulationTimeSeconds,sequence:snapshot.sequenceNumber,counts:snapshot.counts})
  for (const mode of ['CAR', 'MOTORBIKE']) {
    if (routeSamples.some(r => r.vehicleType === mode)) continue
    const vehicle = snapshot.vehicles.find(v => v.vehicleType === mode && v.routeRef)
    if (!vehicle) continue
    const route = validators.validateSimulationRoute(await get(`/routes/${vehicle.routeRef}`), snapshot, vehicle)
    assert.equal(route.routingIdentity.profile, mode === 'CAR' ? 'car' : 'motorbike')
    routeSamples.push({vehicleType:mode,vehicleId:vehicle.id,routeRef:route.routeRef,graph:route.routingIdentity.graphManifestSha256,points:route.coordinates.length})
    const detail=validators.validateBookingDetail(await get(`/bookings/${vehicle.activeBookingId}`),snapshot,vehicle)
    const legs=[]
    for(const leg of [detail.pickupLeg,detail.tripLeg]) {
      if(leg.routeRef) {
        const stored=validators.validateSimulationRoute(await get(`/routes/${leg.routeRef}`),snapshot,{...vehicle,routeRef:leg.routeRef})
        assert.equal(stored.distance,leg.distance);assert.equal(stored.duration,leg.duration)
        legs.push({phase:leg.phase,routeRef:stored.routeRef,points:stored.coordinates.length})
      }else assert.equal(leg.duration,0)
    }
    bookingSamples.push({vehicleType:mode,vehicleId:vehicle.id,bookingId:detail.bookingId,pickup:detail.pickup,dropoff:detail.dropoff,legs})
  }
}
assert.deepEqual(routeSamples.map(r=>r.vehicleType).sort(), ['CAR','MOTORBIKE'])
const report = {status:'PASS',kind:'real-worker-HTTP-to-product-TypeScript-validator',jobId:id,config:result.config,counts:result.counts,snapshotSamples:samples,selectedRoutes:routeSamples,selectedBookings:bookingSamples,summaryWithoutHistory:true,duplicateSnapshotsRejected:true,savedV1:'separate contract; untouched'}
await mkdir(dirname(destination), {recursive:true})
await writeFile(destination, JSON.stringify(report,null,2)+'\n')
console.log(JSON.stringify(report,null,2))
