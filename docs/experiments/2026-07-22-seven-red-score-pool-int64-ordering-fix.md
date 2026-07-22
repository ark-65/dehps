# Seven-Red Score-Pool int64 Ordering Fix — 2026-07-22

## Round contract

- Primary goal: correct one signed `int64` boundary bug in score-pool Top-M seed ordering.
- Engineering authorization: Agent Request `178`
  (`engineering-seven-red-score-pool-int64-ordering-fix`), Execution `99`.
- Role: Engineering Agent after a separate Reviewer decision.
- Production impact: none; the score-pool module remains research-only.
- Non-goals: no score, candidate, parameter, Runtime, portfolio, selector, evaluation, or production
  contract change.

## Reproducer and cause

The frozen order is higher signed score tick, then lower six-red `lex_id`. The original NumPy key
used unary negation:

```text
lexsort((lex_id, -score_tick))
```

Two's-complement signed `int64` cannot represent positive `2^63`. Negating `-2^63` therefore
overflows back to `-2^63`, allowing the lowest legal tick to sort before higher ticks.

## Smallest fix

The implementation maps signed order to monotone unsigned order by flipping the sign bit, then
bitwise-inverts that key for descending order:

```text
signed_order = score_tick_as_uint64 XOR 2^63
descending_key = bitwise_not(signed_order)
lexsort((lex_id, descending_key))
```

This is defined for every signed `int64` value and preserves the lower-`lex_id` tie break. It does
not modify score ticks or cast them to float.

The transparent Python reference now contains `int64` minimum, minimum plus one, negative values,
zero, positive ties, and `int64` maximum. Existing frozen replay assertions continue to check that
the ordinary all-zero golden score-pool snapshot remains unchanged.

## Validation

- Score-pool focused tests: `16 passed in 3.18s`.
- Complete seven-red chain: `106 passed in 16.78s`.
- Complete Worker regression: `1484 passed, 4 skipped, 4 warnings in 131.70s`. The warnings are the
  existing Python 3.14 multiprocessing warning about `fork()` from a multi-threaded process; this
  fix introduced no new warning class.
- `py_compile`, `git diff --check`, line-length, placeholder, and source-scope audits passed.

## Interpretation boundary

This is an implementation correctness repair. It does not change the intended ranking contract,
provide new empirical evidence, select a strategy, or support any predictive or betting claim.
