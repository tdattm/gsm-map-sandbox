# Connected NVMR v1 contract (API v5)

This contract represents one connected simulation world. Historical v3 Hanoi and
v4 isolated-region scenarios retain their existing semantics and readers.

## Scenario

`schemaVersion: gsm-nvmr-connected-scenario/v1`, `regionId: nvmr-connected`.
The strict generated request schema is [connected-scenario-v1.schema.json](connected-scenario-v1.schema.json).

`fleetSize` is 1–5,000 **global** vehicles; `carCount` plus derived MOTORBIKE count
must conserve it. `fleetAllocations` contains exactly five unique technical zone
IDs and exact per-mode integer counts. If omitted, largest remainder allocation
uses 80/5/5/5/5 weights independently for the two mode totals. This preset is
configuration, not a dispatch restriction. `onlineFraction` and schedule are global.

`demandWeights`, `demandCarFraction`, `crossZoneDemandFraction`, `bookingCount`,
`horizonSeconds` and seed define independent synthetic passenger inputs. Equal
zone demand weights are the default even with 80% fleet in Hanoi. Technical zone
geometry is versioned server configuration, not official administrative geography.

`distribution` controls occupied cell size, maximum vehicles at an exact snapped
coordinate and nearest-neighbor diagnostic sample size. Missing anchors fail;
there is no generated-coordinate or public-router fallback. Geographic distance
is used for sampling/indexing and diagnostic summaries; service duration and
distance come from mode-specific OSRM routes.

## Job API

Base: `/api/v5/simulation/jobs`.

| Method | Suffix | Behavior |
|---|---|---|
| POST | collection | Strict configuration, resource/readiness checks, immutable queue input; 202 |
| GET | collection | Only connected v5 jobs |
| GET | `/{id}` | Durable status |
| POST | `/{id}/cancel` | Terminal cancellation, no late resurrection |
| GET | `/{id}/result?summary=true` | Final summary, no route/timeline bulk payload |
| GET | `/{id}/result` | Complete persisted immutable world |
| GET | `/{id}/snapshot?timeSeconds=t` | Global immutable projection with all vehicles and zone accounting |
| GET | `/{id}/vehicles/{vehicleId}?timeSeconds=t` | Selected vehicle and optional booking |
| GET | `/{id}/bookings/{bookingId}` | Immutable selected pickup/trip detail |
| GET | `/{id}/routes/{ref}` | One selected persisted geometry |

Job IDs from v5 are rejected by v3/v4 endpoints. The existing single bounded
queue, worker OS lease, atomic completion and cancellation/restart behavior are
shared across versions. An interrupted run is retained as INTERRUPTED; retry is
a new explicit job, not a promise of instruction-level resume.

## Result and snapshot

Result schema: `gsm-nvmr-connected-result/v1`; model `heap-grid-connected/v1`.
There is one global `vehicles`, `bookings`, `assignments`, `events`, `timelines`
and `routes` collection. `vehicles` contains initial positions plus immutable
`homeZoneId`; snapshots derive `currentZoneId` from the projected position.
Bookings retain `pickupZoneId`, `dropoffZoneId`, `potentialPassengerId`.

Snapshot schema: `gsm-nvmr-connected-snapshot/v1`. Global counts satisfy
`total = online + offline`, `online = idle + assigned + onTrip`; moving is a
subset of assigned/onTrip. `zoneCounts` partitions **current** positions,
including `outside-operating-zones`, and reconciles to every global count.

`kpis.global`, `kpis.byZone` and `kpis.byMode` retain raw counts, wait sums/counts,
busy/online/fleet vehicle-seconds before ratios. Demand/wait are attributed to
pickup zone; fleet/utilization to immutable home zone. This explicitly supports
cross-zone service without incorrectly merging those attribution axes.

`distributionQuality` records exact zone/mode counts, coordinate duplicates,
occupied cells, crowded cells and sampled nearest-neighbor distances.
`routingIdentities` pins separate CAR/MOTORBIKE profile, graph manifest,
source/extract hashes and MLD algorithm. Inputs, configuration, seeds, model and
dataset provenance are retained. Completed playback requires the persisted run
and local map assets; it makes no new OSRM calls.

## M5 extension boundary

Identity-keyed passenger draws and independent fleet/demand streams permit
controlled exogenous inputs in separate immutable worlds. Stable passenger IDs,
`NO_BOOK / CAR / MOTORBIKE` choice-set metadata, outcome histories and additive
KPIs provide extension points. R1b does not implement/calibrate behavioral
choice, voucher policy/budget/ledger, treatment effects or incremental bookings.
Those models must remain explicit versioned M5 inputs with independently owned
world state, not hard-coded R1b assumptions or observed GSM claims.
