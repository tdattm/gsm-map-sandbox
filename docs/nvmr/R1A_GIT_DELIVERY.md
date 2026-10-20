# R1a review-only Git delivery

Generated from the actual primary checkout inventory on18/10/2026. Branch `feature/nvmr-m0-architecture`, unchanged HEAD `43a6d09be2252c44743f9e78a429a3ed700502c1`. The index was verified empty. **No staging, commit, push, merge or rebase was performed.**

## Before any user-run staging

These commands are suggestions for the Owner. Run each group in order and inspect every staged diff before its commit. If anything is already staged or the checkout has changed since this inventory, reconcile that first. Raw PBF/OSRM graphs, whole render datasets, job stores/build caches, node_modules/dist, .env/secrets and unrelated sibling worktree files are excluded.

```powershell
Set-Location 'D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox'
git status --short
git diff --check
git diff --cached --name-only
```

The four commits are a suggested review structure; closely related groups can be combined after review. Do not omit the backend/source dependencies when reviewing the frontend. All modules already live and were tested together in this one checkout. The historical M3/M4 worktrees are not a source of additional R1a changes.

## 1. Bac Ninh GIS/pipeline

13 actual files:

```powershell
git add -- `
  'backend/app/dataset.py' `
  'backend/app/modes.py' `
  'backend/app/regions.py' `
  'config/regions/nvmr-bac-ninh-core-motorbike.json' `
  'config/regions/nvmr-bac-ninh-core.json' `
  'scripts/capture_regional_gis.py' `
  'scripts/motorbike_pipeline.py' `
  'scripts/pipeline.py' `
  'scripts/region_pipeline.py' `
  'scripts/regional_resources.py' `
  'scripts/validate_regional_routing.py' `
  'tests/test_r1a_gis.py' `
  'tests/test_regions.py'
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached

# Execute only after reviewing the full staged content:
git commit -m "feat(gis): add Bac Ninh Core local routing foundation"
```

## 2. Regional simulation/contracts

9 actual files:

```powershell
git add -- `
  'backend/app/booking.py' `
  'backend/app/main.py' `
  'backend/app/regional_jobs.py' `
  'backend/app/regional_simulation.py' `
  'backend/app/simulation_jobs.py' `
  'backend/app/simulation_worker.py' `
  'scripts/validate_regional_api.py' `
  'scripts/validate_regional_domain.py' `
  'tests/test_regional_simulation.py'
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached

# Execute only after reviewing the full staged content:
git commit -m "feat(simulation): add durable two-region NVMR scenarios"
```

## 3. NVMR frontend/runtime integration

12 actual files:

```powershell
git add -- `
  'frontend/src/App.css' `
  'frontend/src/App.tsx' `
  'frontend/src/components/regional-overview.tsx' `
  'frontend/src/components/regional-workspace.tsx' `
  'frontend/src/components/simulation-map-health.tsx' `
  'frontend/src/components/simulation-workspace.tsx' `
  'frontend/src/lib/regional-simulation.ts' `
  'frontend/src/lib/use-regional-simulation.ts' `
  'frontend/tests/regional-overview.test.tsx' `
  'frontend/tests/regional-simulation.test.ts' `
  'scripts/Start-GsmDev.ps1' `
  'scripts/Stop-GsmDev.ps1'
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached

# Execute only after reviewing the full staged content:
git commit -m "feat(ui): integrate NVMR overview and regional replay"
```

## 4. Documentation and executed evidence

75 actual files:

```powershell
git add -- `
  'README.md' `
  'docs/nvmr/M0_IMPLEMENTATION_PLAN.md' `
  'docs/nvmr/M0_TARGET_ARCHITECTURE.md' `
  'docs/nvmr/R1A_BACKEND.md' `
  'docs/nvmr/R1A_GIS.md' `
  'docs/nvmr/R1A_GIT_DELIVERY.md' `
  'docs/nvmr/R1A_IMPLEMENTATION.md' `
  'docs/nvmr/R1A_PROGRESS.md' `
  'docs/nvmr/R1A_RUNBOOK.md' `
  'docs/nvmr/r1a-evidence/bac-ninh-motorbike-reuse.txt' `
  'docs/nvmr/r1a-evidence/backend-artifact-free-final.txt' `
  'docs/nvmr/r1a-evidence/backend-artifact-free.txt' `
  'docs/nvmr/r1a-evidence/backend-live-final.txt' `
  'docs/nvmr/r1a-evidence/backend/domain-5000.json' `
  'docs/nvmr/r1a-evidence/backend/table-live-100-diagnostic.json' `
  'docs/nvmr/r1a-evidence/backend/table-live-100-probes.json' `
  'docs/nvmr/r1a-evidence/browser/console-final-page.json' `
  'docs/nvmr/r1a-evidence/browser/console.json' `
  'docs/nvmr/r1a-evidence/browser/final-regional-overview.png' `
  'docs/nvmr/r1a-evidence/browser/final-regional.ax.txt' `
  'docs/nvmr/r1a-evidence/browser/functional-summary.json' `
  'docs/nvmr/r1a-evidence/browser/hanoi-motorbike.png' `
  'docs/nvmr/r1a-evidence/browser/hcm-booking.ax.txt' `
  'docs/nvmr/r1a-evidence/browser/hcm-fleet.ax.txt' `
  'docs/nvmr/r1a-evidence/browser/hcm-saved-replay.ax.txt' `
  'docs/nvmr/r1a-evidence/browser/hcm-single.ax.txt' `
  'docs/nvmr/r1a-evidence/browser/hcm-voucher-live.ax.txt' `
  'docs/nvmr/r1a-evidence/browser/matrix-summary.json' `
  'docs/nvmr/r1a-evidence/browser/overview-20.png' `
  'docs/nvmr/r1a-evidence/browser/overview-5000-final.png' `
  'docs/nvmr/r1a-evidence/browser/overview-5000.png' `
  'docs/nvmr/r1a-evidence/browser/webgl-100-total-bac-ninh-50.json' `
  'docs/nvmr/r1a-evidence/browser/webgl-500-total-bac-ninh-250.json' `
  'docs/nvmr/r1a-evidence/browser/webgl-5000-total-bac-ninh-2500.json' `
  'docs/nvmr/r1a-evidence/build-final.txt' `
  'docs/nvmr/r1a-evidence/build.txt' `
  'docs/nvmr/r1a-evidence/frontend-tests-final.txt' `
  'docs/nvmr/r1a-evidence/frontend-tests.txt' `
  'docs/nvmr/r1a-evidence/gis-reuse-tests.txt' `
  'docs/nvmr/r1a-evidence/gis/artifact-audit.json' `
  'docs/nvmr/r1a-evidence/gis/nvmr-bac-ninh-core/car-only/regional-routing.json' `
  'docs/nvmr/r1a-evidence/gis/nvmr-bac-ninh-core/car-only/source-oneway-ways.xml' `
  'docs/nvmr/r1a-evidence/gis/nvmr-bac-ninh-core/car-table-route-comparison.json' `
  'docs/nvmr/r1a-evidence/gis/nvmr-bac-ninh-core/regional-routing.json' `
  'docs/nvmr/r1a-evidence/gis/nvmr-bac-ninh-core/source-oneway-ways.xml' `
  'docs/nvmr/r1a-evidence/gis/nvmr-bac-ninh-core/synthetic-validation.json' `
  'docs/nvmr/r1a-evidence/git-allowlists.json' `
  'docs/nvmr/r1a-evidence/hanoi-motorbike-reuse.txt' `
  'docs/nvmr/r1a-evidence/hanoi-v3-live.json' `
  'docs/nvmr/r1a-evidence/hcm-router-serve.txt' `
  'docs/nvmr/r1a-evidence/launcher-final-recovery.txt' `
  'docs/nvmr/r1a-evidence/launcher-regional-reuse.txt' `
  'docs/nvmr/r1a-evidence/launcher-restarted.txt' `
  'docs/nvmr/r1a-evidence/launcher.txt' `
  'docs/nvmr/r1a-evidence/lint-final.txt' `
  'docs/nvmr/r1a-evidence/live-100-retry.json' `
  'docs/nvmr/r1a-evidence/live-100.json' `
  'docs/nvmr/r1a-evidence/live-20.json' `
  'docs/nvmr/r1a-evidence/live-500.json' `
  'docs/nvmr/r1a-evidence/live-5000.json' `
  'docs/nvmr/r1a-evidence/live-lifecycle.json' `
  'docs/nvmr/r1a-evidence/live-matrix-summary.json' `
  'docs/nvmr/r1a-evidence/restart-stop-fixed.txt' `
  'docs/nvmr/r1a-evidence/restart-stop.txt' `
  'docs/nvmr/r1a-evidence/router-proof-preservation.json' `
  'docs/nvmr/r1a-evidence/saved-verifier.txt' `
  'docs/nvmr/r1a-evidence/stop-identity-setup-failure.json' `
  'docs/nvmr/r1a-evidence/stop-identity-summary.json' `
  'docs/nvmr/r1a-evidence/stop-invalid-receipt-pwsh.txt' `
  'docs/nvmr/r1a-evidence/stop-invalid-receipt.txt' `
  'docs/nvmr/r1a-evidence/typecheck-final.txt' `
  'docs/nvmr/r1a-evidence/typecheck.txt' `
  'docs/nvmr/r1a-evidence/ui-created-20-audit-recovery.json' `
  'docs/nvmr/r1a-evidence/ui-created-20-audit.json' `
  'docs/nvmr/r1a-evidence/validation-summary.json'
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached

# Execute only after reviewing the full staged content:
git commit -m "docs(nvmr): record R1a verification and recovery runbook"
```

## Existing dirty historical worktrees

`D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox-m3` and `...\gsm-map-sandbox-m4` remain detached at455abeb and contain old uncommitted source. They were inspected read-only, not changed, staged, reset, archived or removed. Their exact status inventory is in `r1a-evidence/validation-summary.json`. R1a implementation is already integrated in the primary checkout.

## Review boundaries

- `backend/app/booking.py` changes only explicit-radius query plumbing; legacy defaults stay unchanged. V4 applies1m vehicle source radiuses in its own adapter, preserving response assertions and null ETAs.
- Public `SimulationConfig`, scientific simulation engine, Voucher ledger/model, Hanoi configs/motorcycle profile and Saved artifact contract are unchanged.
- MOTORBIKE serve now preserves identical router proof bytes/mtime and refuses overwrite mismatches; no graph rebuild is implied.
- Stop-GsmDev handles UTC/PS7 DateTime receipt parsing and command whitespace while retaining PID/executable/command/child guards. Failed test setup and recovery evidence are retained.
- Browser low-RAF measurements are recorded limitations, not a smooth5,000 UI or production certificate.
- Failure/raw evidence files are intentionally kept alongside successful retries. They are not passed checks and contain no credentials.

Machine-readable exact lists: `r1a-evidence/git-allowlists.json`. Final executed verification/limitations: `R1A_IMPLEMENTATION.md`.
