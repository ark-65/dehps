# Signal bootstrap series-identity fix v1

## Primary goal

Make circular block-bootstrap output a deterministic function of the ordered
paired-difference series and bootstrap protocol, independent of display arm
labels.

## Reproducer

Corrected random-control execution 122 produced byte-identical random rows and
identical paired means for the equivalent `full_model` and
`fixed_minimal_linear` arms. Their confidence intervals still differed slightly
because the arm label participated in bootstrap RNG derivation.

Affected snapshot:

```text
fe5f4f62221e33da5964f434019c0a7cf1ffd83ca3f4745b434879cf0cea0381
```

That snapshot remains immutable and is not admissible as formal Evidence.

## Change

The resampling seed now binds:

- the configured seed digest;
- a canonical digest of the ordered paired-difference series;
- block length;
- resample count;
- the circular block-bootstrap protocol.

The display label remains accepted by the public function for compatibility but
does not affect the resampling sequence. The summary records
`series_identity_digest` for audit.

## Non-goals

- No scoring, feature, ranking, portfolio, baseline, or random-control change.
- No mutation of existing artifacts.
- No research conclusion or Promotion Gate change.

## Acceptance

- Repeated runs over one series are byte-identical.
- Two different labels over one ordered series are byte-identical.
- The focused diagnostic tests and full worker suite pass.
- A fresh Operator artifact is required before Evidence submission.
