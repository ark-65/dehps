# Seven-Red Equal-Cost Portfolio Contract v1 — 2026-07-22

## Round contract

- Primary goal: normalize Raw seven-red Top10, Diversified seven-red Top10, and six-red Top70 into
  immutable, comparison-ready portfolios of exactly 70 paid six-red ticket slots.
- Engineering authorization: Agent Request `177`
  (`engineering-seven-red-equal-cost-portfolio-contract-v1`), Execution `98`.
- Dependency: completed Request `176`, seven-red score-pool compiler, merged commit
  `fe754d8c206a5b3bf907baf5a293c70c953ec293`.
- Role: Engineering Agent after a separate Reviewer decision.
- Status: `RESEARCH_ONLY`, accounting and settlement ABI, not a result.
- Production impact: none.

## Equal cost means 70 paid slots

`EqualCostSixRedPortfolio70` always contains exactly 70 ordered canonical `SixRedCombination`
slots. The contract keeps two quantities separate:

```text
paid_ticket_slot_count = 70
unique_ticket_count    = number of distinct six-red identities
duplicate_slot_count   = 70 - unique_ticket_count
```

Repeated six-red tickets remain repeated paid slots. The compiler never silently deduplicates or
refills them. This is essential for Raw Top10: two different seven-red candidates can share a
six-red expansion, so they spend two slots on one unique coverage identity.

Every slot binds its ordinal, source kind and rank, canonical six-red identity, and either:

- seven-red parent candidate plus expansion ordinal; or
- exact six-red source score tick for the Top70 control.

The portfolio digest binds target issue, source artifact, parent score-pool snapshot where
applicable, candidate-pool identity, pre-target latest history issue, the 70-slot sequence digest,
and unique/duplicate counts.

## Three deterministic source adapters

### Raw seven-red Top10

Slots are emitted by Raw rank, then canonical expansion ordinal. All ten candidates contribute all
seven tickets. Duplicates remain in place.

### Diversified seven-red Top10

Slots are emitted by diversified rank, then expansion ordinal. Construction reuses and rechecks the
existing Diversified invariant: all 70 expansions must be unique.

### Six-red Top70

The complete `SixRedFullScoreVector` is ranked by exact signed score tick descending and then lower
six-red `lex_id`. The first 70 distinct rows form the control. Negative scores and boundary ties use
the same integer ordering; float values do not decide inclusion.

## Mandatory parent-source binding

Reviewer analysis found that Raw and Diversified snapshots do not themselves carry a structured
target issue and history/window boundary. Their adapters therefore also require the parent
`SevenRedScoredCandidatePoolSnapshot`. The candidate-list digest must match exactly. This binds:

- the same target issue;
- the same complete six-red score vector;
- the same pre-target history/window and Runtime provenance;
- the same generated seven-red candidate pool.

The six-red Top70 path binds the same source vector directly and requires its latest history issue
to be strictly before the target.

No portfolio constructor accepts actual numbers, actual issue, hit count, outcome digest,
post-target history, timestamp, random seed, or settlement field.

## Separate post-outcome settlement

`EqualCostPortfolioSettlement.evaluate(...)` is a distinct post-outcome stage. Its explicit actual
issue must equal the sealed portfolio target issue. It records the actual canonical six-red
identity and recomputes:

- 70 slot-level matched-red counts;
- slot-weighted histogram for matched counts 0 through 6;
- deduplicated unique-ticket histogram for matched counts 0 through 6;
- slot-weighted exact-red6 count;
- unique-ticket exact-red6 count.

The two histogram totals must equal 70 and the portfolio unique-ticket count respectively. No blue
ball, prize, payout, shared-prize dilution, expected value, bankroll, or risk interpretation is
defined.

## Dual mathematical review

### Historical boundary

The Gauss and Riemann passes are historically inspired verification and structural lenses. They are
not literal reconstructions and provide no empirical evidence.

### Gauss pass: verification

- Strongest claim: 70-slot cost, canonical ticket legality, duplicate multiplicity conservation,
  Top70 order, chronology, issue equality, and both histogram identities are exact finite checks.
- Weakest assumption: red-ball matched-count coverage is a useful comparison coordinate without a
  blue-ball or economic contract.
- Required checks: boundary ties, negative scores, slot count/order, source digest equality,
  duplicate conservation, actual-issue equality, and histogram sums.
- Boundary: exact accounting establishes a fair denominator, not useful prediction.

### Riemann pass: structure

- Strongest claim: representing the same portfolio as both a 70-slot multiset and a unique-ticket
  set preserves the distinct overlap geometry of Raw and Diversified outputs.
- Weakest assumption: the two hit histograms capture enough structure for later multi-issue
  comparison; dependence among repeated tickets and among issues remains unmodeled.
- Required checks: never collapse duplicates before settlement, report unique coverage alongside
  paid cost, require deterministic replay of the parent score-pool snapshot, and avoid turning
  one-issue geometry into a time-series conclusion.
- Boundary: the ABI describes portfolio geometry; it does not select a preferred geometry.

### Smallest shared conclusion

The contract is acceptable only as a deterministic equal-cost accounting and settlement boundary.
It does not establish predictive superiority, statistical significance, or economic value.

## Deterministic evidence

The Raw fixture uses one six-red seed and the ten lowest-lexicographic seven-red supersets. It
produces:

```text
paid slots       = 70
unique tickets   = 61
duplicate slots  = 9
```

The common `(1,2,3,4,5,6)` ticket appears in all ten seven-red lines. When it is also the actual
six-red outcome, slot-weighted exact-red6 count is 10 while unique-ticket exact-red6 count is 1.
Both values are retained; neither replaces the other.

A separate ten-seed fixture produces 270 candidate-pool rows, lets the existing diversified greedy
selector choose ten expansion-compatible candidates, and compiles exactly 70 unique tickets.

The six-red fixture freezes the Top70 boundary with 69 higher-scored rows and a tied pair at lex IDs
70 and 80; lex ID 70 occupies the final slot. An all-negative tie fixture selects lex IDs 0 through
69 deterministically. A signed-boundary fixture mixes `int64` minimum, minimum plus one, and zero;
the ordering uses a sign-bit-transformed unsigned key and therefore does not overflow by negating
the minimum value.

Normative contract digest:
`d80acbf397b48357e4d740cee697631e27d766a8b63707120f2832ec3ae495f1`.

## Validation

- Focused equal-cost tests: `13 passed in 8.47s`.
- Complete seven-red predecessor and equal-cost chain: `106 passed in 14.51s`.
- Complete Worker regression: `1484 passed, 4 skipped, 4 warnings in 117.72s`. The warnings are the
  existing Python 3.14 multiprocessing warning about `fork()` from a multi-threaded process; this
  round introduced no new warning class.
- `py_compile`, `git diff --check`, line-length, placeholder, and source-scope audits passed.

## Explicit limitations

This round does not define random-from-pool or uniform-legal controls, choose random seeds, select
M/P or diversification weights, run multiple issues, perform walk-forward, estimate uncertainty,
run statistical tests, create Evidence, decide a hypothesis, recommend a bet, define economic
value, or integrate with database, CLI, API, web, scheduler, supervisor, or production TopK.
