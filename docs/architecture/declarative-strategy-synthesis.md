# Declarative Strategy Synthesis

Round 28 introduces strategy synthesis as a contract generator, not as a code generator.

Synthesized features and strategies are declarative JSON contracts. They are intended to become inputs to later reviewed research proposals and isolated experiments. They cannot execute Python, SQL, shell commands, arbitrary expressions, or production mutations.

## Feature contract

A `SynthesizedFeature` includes:

- source pattern keys and hashes
- `execution_mode`: `declarative`, `composable`, or `runtime_interpreted`
- explicit formula and parameters
- an allowed operation list
- input boundary
- output contract
- null dependency
- failure condition

Allowed operations are intentionally small: count, ratio, sum, span, difference, modulo, contains, rolling/window counts, z-score, residual, rank, quantile, and linear combination.

Forbidden tokens include arbitrary execution surfaces such as `eval`, `exec`, imports, shell, SQL, subprocess, and Python module escape hatches.

## Strategy contract

A `SynthesizedStrategy` must use one allow-listed strategy type:

- `single_feature_rank`
- `weighted_linear_rank`
- `quantile_filter_then_rank`
- `residual_rerank`
- `stratified_candidate_allocation`
- `rank_ensemble`

Every strategy declares:

- source features and source patterns
- scoring expression
- bounded parameters
- candidate boundary
- matched baseline strategy
- validation protocol
- failure condition
- `production_impact: none`

## Safety boundary

Round 28 synthesis does not:

- modify source code
- modify the production ranker
- modify objective policy
- modify candidate source
- run training
- replace frozen strategies
- create or merge a PR
- claim profit, hits, or one-draw confirmation

The only permitted handoff is a submitted Research Proposal Request. Reviewer approval and later isolated engineering/execution rounds remain required.
