# Autonomous Pattern Discovery

Round 28 adds a bounded pattern-discovery layer for DEHPS.

The layer reads historical red-ball draws and formal artifacts, searches a fixed catalog of interpretable pattern families, compares candidates against declared nulls, and converts only valid candidates into declarative feature and strategy contracts. It does not modify source code, production training, production rankers, objectives, candidate sources, or the Promotion Gate.

## Data flow

```text
History / artifacts
  -> Pattern catalog
  -> Extractors
  -> PatternCandidate
  -> Significance + novelty review
  -> SynthesizedFeature
  -> SynthesizedStrategy
  -> Research Proposal Request
```

## PatternCandidate contract

Every candidate is machine-readable and includes:

- `pattern_key`, `pattern_family`, `pattern_type`
- explicit `formula` and bounded `parameters`
- `input_boundary`, `search_issue_range`, `history_fingerprint`
- `legal_universe_fingerprint`
- observed and expected support
- effect, stability, novelty, and complexity scores
- declared null and failure condition
- leakage risks and source artifacts
- generator version and multiplicity family

The current legal universe fingerprint is `ssq-red-1-33-choose-6-v1`.

## Catalog

The catalog is fixed and machine-readable. It currently covers more than 30 pattern types across:

- arithmetic and spacing
- consecutive runs
- odd/even structure
- sum/span
- tail and modular residues
- prime/square/Fibonacci counts
- zones
- co-occurrence graph patterns
- temporal omission patterns
- residual/model patterns

## Null comparison

Arithmetic progression candidates compare against:

- legal universe
- same-sum null
- same-span null
- same odd/even ratio null
- random-history permutation null

The AP implementation distinguishes full six-term progressions and 5/4/3-term subsequences, including start `a` and difference `d`.

## Search protocol

Pattern search keeps the search/frozen/forward boundary explicit:

- search discovers candidates
- frozen validates preregistered candidates
- forward is future-only evidence
- frozen and forward windows are not parameter-selection windows
- multiplicity is counted by family
- incomplete multiplicity makes significance non-interpretable

## Pattern memory

Round 28 adds:

- `discovered_patterns`
- `pattern_observations`
- `pattern_validations`
- `synthesized_features`
- `synthesized_strategies`
- `pattern_search_cycles`

Formula hashes are unique. Observations and validations are append-only. Frozen validation thresholds are immutable. Rejected patterns remain retained so novelty checks can detect near retries.

## Scheduler integration

When pattern memory is enabled and no active research item is available, the scheduler can select one pattern action:

```text
discover_patterns
screen_patterns
synthesize_features
synthesize_strategies
submit_pattern_hypothesis
wait_forward_pattern
```

If no valid pattern action exists, the scheduler waits instead of manufacturing speculative proposals.
