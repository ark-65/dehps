# Seven-red isolated walk-forward runner v1

## Round contract

- Request: `engineering-seven-red-isolated-walk-forward-runner-v1` (Request 183)
- Execution: 104
- Role: Engineering Agent
- Primary goal: connect the already verified seven-red scoring, selection, equal-cost, random-control, inner-selection, outer-walk-forward, and statistical contracts into one deterministic research-only runner for the preregistered experiment.
- Production impact: none

Non-goals:

- no historical experiment execution in this Engineering round;
- no parameter, target, seed, endpoint, comparator, threshold, or decision change;
- no Evidence or Hypothesis mutation;
- no prediction, betting, promotion, API, web, scheduler, or supervisor integration;
- no committed `data/output` artifact.

## Implemented boundary

`python -m dehps.seven_red.run_walk_forward` accepts only the approved experiment key and an output directory below `data/output`. Before computing anything it requires:

- a clean committed repository;
- the registered preregistered/running hypothesis and planned/running experiment;
- the exact `2026083` as-of boundary;
- the exact last-80 issue slice `2026004..2026083` with the 20/60 split at `2026023/2026024`;
- the full `C(33,6)=1,107,568` universe;
- the frozen score configuration, four-row Raw/Diversified grid, eight seed digests, and statistical parameters.

The preregistered generic diversification coordinates map explicitly and only once into the existing selector contract: `score → source_quality`, `redundancy → pair_coverage`, `edge → triple_coverage`, and `coverage → exposure_balance`. Both registered rows use `1/1/1` on the latter three coordinates, while `div-b` alone changes source quality from `1` to `2`.

For each issue the runner first compiles the prior-only score vector and all parameter-specific pools and portfolios. For outer targets it then chooses parameters from the preceding 20 completed issue evaluations and seals the selected portfolios, Top70, and random cohorts. Only after those pre-outcome objects exist does it materialize the target red numbers for settlement.

Each completed issue atomically replaces one cumulative checkpoint. Resume requires the same runner version, preregistered plan digest, exact source commit, canonical completed-issue prefix, complete issue-by-parameter rectangle, and complete outer-trial prefix. A changed commit, missing cell, reordered issue, unknown parameter, or digest mismatch fails closed.

Final generated outputs are:

- `protocol.json`;
- `checkpoint.json`;
- `walk_forward_snapshot.json`;
- `statistical_snapshot.json`;
- `run_manifest.json`;
- `run_report.md`.

They stay under ignored `data/output`. The numerical report explicitly leaves the research decision unset.

## Gauss pass

- Exact sample space is asserted at `1,107,568` legal six-red combinations.
- Every retained strategy and control continues through the existing exact 70-paid-slot contract.
- The parameter grid is exactly two Raw plus two Diversified rows; no row can be added, removed, or modified at runtime.
- The inner evidence is a complete `20 issues × 4 parameters` rectangle for every outer target.
- All eight registered seed digests are retained; the seed policy only applies canonical ordering and never selects a seed.
- Checkpoint recovery proves the exact source commit and full canonical cell matrix instead of trusting counts alone.
- Statistical arithmetic and multiplicity remain delegated to the verified Fraction/sign-test/Holm/block-bootstrap contract.

## Riemann pass

- The process is separated into three spaces: prior-only candidate construction, post-outcome per-issue settlement, and cross-issue statistical compilation.
- The outer target never participates in its own rolling inner window.
- Raw and Diversified select independently, while all strategy arms for one target share the same source score vector and actual outcome.
- Random controls remain attached to the selected family pool rather than becoming free-floating global baselines.
- Resume state preserves the topology of the experiment: one ordered issue prefix, four parameter cells per completed issue, and one trial per completed outer target.

## Disagreement and resolution

Gauss favors the smallest state necessary for exact replay; Riemann favors retaining enough structure to reconstruct the full experiment without collapsing family or temporal relationships. Storing full score artifacts per issue would satisfy replay but create unnecessarily large runtime state. Storing only row counts would be compact but structurally ambiguous.

The shared resolution is a compact cumulative checkpoint containing all parameter evaluation rows and compact outer trials, with every digest replayed into immutable contract objects. Full per-issue score arrays are recomputed only for unfinished targets.

## Smallest shared conclusion

The approved fixed experiment can now be executed without adding scientific degrees of freedom. This Engineering artifact does not establish whether Raw or Diversified Top10 outperforms any comparator; that question remains blocked on a separately approved Operator run and Research/Reviewer evidence decision.

## Validation

- Registered-plan smoke check against local PostgreSQL: plan digest `26e0b337386fadaf5b2f83579c743ab4ad5d605a0c7f7bc35f12fa2079c4ad46`; issue split `2026004..2026023 / 2026024..2026083`.
- Focused seven-red suite: `154 passed`.
- Full Worker regression: `1532 passed, 4 skipped` (`4` existing Python 3.14 fork deprecation warnings).
