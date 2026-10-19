# M5 Engineering Handoff — Connected NVMR

Prepared 19/10/2026 (Asia/Saigon). Read the final decision in
[R1B_CONNECTED_IMPLEMENTATION.md](R1B_CONNECTED_IMPLEMENTATION.md) and the latest
[checkpoint](R1B_PROGRESS.md) before treating infrastructure as accepted. This
document describes available interfaces and remaining M5 work; it does not claim
that a behavioral or voucher model has already been implemented.

## Reusable R1b infrastructure

Connected v5 has one world, event queue, clock, global mode-specific dispatch pool,
immutable result and playback. Zone membership is a versioned technical research
definition; it is neither a dispatch partition nor an official province polygon.
The strict scenario contract and result/API semantics are documented in
[CONNECTED_V1.md](../../contracts/nvmr/CONNECTED_V1.md).

- Global fleet maximum5,000; exact integer zone/mode allocation. Default4,000
  Hanoi plus250 per satellite zone,2,000CAR plus3,000MOTORBIKE. These are research
  inputs, not GSM operational counts.
- Independent demand weights/mode fraction/cross-zone fraction. Equal zone
  demand weights are independent of the80/20 fleet preset.
- Identity-keyed SHA-256 fleet/passenger streams. Demand tests demonstrate
  changing fleet size/allocation does not alter the same-seed exogenous passenger
  draws. Stable `potentialPassengerId` connects a request to its research identity.
- Road-derived spatial anchors, separate snapped catalogs by mode and bounded
  spatial shortlists. Final distance/ETA and geometry come from local OSRM.
- Raw vehicle/booking inputs, events, timelines, assignments, explicit unserved
  reasons, selected pickup/trip geometry and routing/model/dataset provenance.
- Additive global/zone/mode wait and utilization numerators/denominators.
  Requested pickup zone attributes demand/wait; immutable home zone attributes
  fleet/utilization. Current-zone snapshot accounting includes outside-zone travel.
- Persisted results replay without OSRM; the local API and MBTiles are required
  for a fresh browser. Queue/worker lease and cancellation/restart rules remain
  shared with historical v3/v4.

## Extension points for the M5 implementation

`backend/app/connected_simulation.py` separates `connected_inputs()` from
`simulate_connected()`. The latter accepts explicit vehicles, bookings,
mode-specific travel adapters/identities, world ID, technical zones and metadata.
It creates fresh world state inside the existing event engine on every call.

`backend/app/connected_jobs.py` prepares/pins live artifacts, persists immutable
inputs and publishes final results. `simulation_worker.py` chooses the executor
by scenario schema, without changing old API semantics. A paired experiment
should use a new explicit envelope/schema and executor rather than adding silent
treatment meaning to existing v5 requests.

The frontend's `use-connected-simulation.ts` and connected workspace consume
versioned summaries/snapshots and existing immutable booking/route details.
Presentation filters, playback cadence and Meeting mode never affect demand,
dispatch, routing or treatment outcomes.

## Work M5 must add

1. Define and freeze a **potential passenger population** before any treatment
   decision. R1b currently turns its independent synthetic demand stream into
   CAR/MOTORBIKE bookings; it does not yet store a full NO_BOOK decision cohort.
2. Add explicit `NO_BOOK / CAR / MOTORBIKE` choice model, availability,
   preference/utility parameters and stable identity-keyed latent draws. State
   assumptions and calibration limits; do not label assumed behavior as observed.
3. Run Baseline and Treatment as independent mutable worlds over the same frozen
   cohort, initial fleet, exogenous seed/draws and graph identities. Mode choices,
   bookings and later world states may diverge as model outcomes.
4. Add versioned voucher policy and auditable integer-VND budget/ledger rules.
   Define offer/reserve/settle/release semantics and terminal failure handling.
   Existing HCM `voucher.py` accounting is a reference, not proof that its CAR-only
   behavior/model can be copied unchanged into multimodal v5.
5. Define incremental bookings, pickup-wait comparisons, utilization and regional
   impacts with explicit populations and denominators. Compare raw sums/counts;
   never average zone averages. Distinguish intended treatment, realized booking
   choice, fulfilled trip and settled subsidy.
6. Define a common paired observation horizon. R1b's `horizonSeconds` is the
   request-generation window and its engine drains accepted work; final simulation
   duration can exceed it. Comparing utilization over unequal world durations
   without a common research horizon would confound treatment interpretation.
7. Add paired deterministic fixtures, arm-order invariance, exogenous-input
   conservation, independent world state, mode isolation, budget conservation,
   no double settlement, cancellation and replay tests before live experiments.

No voucher effects, customer preference, actual fleet/demand, commercial ROI or
causal benefit is hard-coded or certified by R1b.

## Boundaries to preserve

HCM Single Trip/Fleet/Booking/Voucher v1/Saved Replay, Hanoi v3 and R1a v4 stay
versioned and readable. Their historical benchmarks remain historical. Existing
M4 FPS investigation is closed; M5 may report a demonstrated new UI regression
without reopening the historical optimization milestone by default.

Use the pinned national source, isolated connected CAR/MOTORBIKE manifests,
current validation evidence and snapped catalog. Reuse valid artifacts; a missing
graph/profile/anchor must fail explicitly. There is no public OSRM, straight-line
route or invented-anchor runtime fallback. Keep heavy GIS stages serial and
retain resource guards and incomplete markers.

The exact runnable demo, tests, local run IDs, graph/tiles hashes, limitations and
GO/M5 decision belong to the final R1b report/runbook. Until those live acceptance
sections are finalized, **M5 acceptance remains pending** despite the available
source interfaces and fixture tests.
