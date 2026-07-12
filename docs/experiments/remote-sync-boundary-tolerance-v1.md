# Remote Sync Boundary Tolerance V1

Date: 2026-07-12

## Primary Goal

Keep the cold-window remote SSQ polling interval at no more than approximately
60 minutes when ten-minute watchdog ticks and sync completion timestamps differ
by a few seconds.

## Non-Goals

- No parser, draw-data, advisor, candidate, objective, search-base, training, or
  promotion change.
- No change to the 30-minute protection for a still-running sync.
- No change to failed-sync retries or official draw/recovery hot windows.
- No predictive, betting, frozen-validation, or performance claim.

## Evidence Before Change

The watchdog recorded a successful attempt at `2026-07-12T07:00:02.718792+08:00`.
At the next hourly wall-clock tick, `2026-07-12T08:00:01.914323+08:00`, the
planner measured `59.987` minutes and returned
`cold_poll_interval_not_elapsed`. With ten-minute watchdog ticks, the next
remote request would occur around 70 minutes after the prior request.

## Change

The cold-success boundary now accepts up to 60 seconds of scheduler drift. The
tolerance is explicit in the plan as `cold_poll_boundary_tolerance_seconds=60`.
It applies only to the cold polling interval; other arbitration branches keep
their previous ordering and thresholds.

## Gauss-Riemann Cross-Review

- **Task Frame:** preserve the stated hourly upper cadence without increasing
  the ten-minute local-health cadence or changing synchronization semantics.
- **Historical Boundary:** Gauss and Riemann are historically inspired
  verification lenses, not literal minds or authority.
- **Gauss Pass:** the observed residual is 0.013 minutes below the exact
  threshold, followed by a ten-minute scheduling jump. The regression test
  checks the observed boundary shape and a 58:59 counterexample.
- **Riemann Pass:** wall-clock watchdog ticks and completion timestamps are two
  time grids. A small overlap at their boundary prevents a subsecond gap from
  becoming a ten-minute discontinuity.
- **Cross-Review:** the tolerance is bounded to one minute and does not apply to
  the running-sync lockout. This verifies cadence arbitration only, not remote
  availability or data correctness.
- **Synthesis:** accept the smallest explicit boundary overlap that removes the
  observed 60-to-70-minute jump while preserving all scientific gates.
- **Next Verification:** observe a cold-window tick near the hourly boundary and
  confirm a successful sync still reports zero unresolved conflicts before any
  forward evaluation, advisor refresh, or supervisor release.

## Scientific Boundary

The legal red-ball universe remains `1,107,568` combinations; the active ranked
universe remains `1,105,506`. The current 80-period search and 20-period frozen
split, historical-holdout quarantine, incomplete sequential-null ledger, and
0/20 forward-evidence count are unchanged. Selection and automatic promotion
remain disabled.
