# Autonomous Evidence Evaluation

Round 25 completes the research loop after isolated experiment execution. It turns immutable experiment artifacts into formal Evidence records, aggregates evidence across experiment windows, drafts a deterministic hypothesis decision, and applies the decision only after Reviewer approval.

The lane is deliberately conservative:

- Evidence is derived only from formal JSON/JSONL artifacts and Registry records.
- Markdown, prompts, and LLM reasoning are not metric sources.
- Decision Drafts cite Evidence IDs, not prose.
- Reviewer approval is required before Hypothesis or Family status changes.
- All Registry changes use existing append-only Registry decisions and Evidence rows.

## Flow

```text
completed isolated experiment artifacts
-> artifact hash/fingerprint/window validation
-> metric loading
-> statistical review
-> Evidence append
-> sequential aggregation
-> Decision Draft Agent Request
-> Reviewer approval
-> Registry transition
```

## Worker Components

`apps/worker-python/dehps/research_evidence/` contains:

- `artifact_reader.py`: validates Round 24 artifact hashes, content hashes, fingerprints, hypothesis identity, plan identity, and issue windows.
- `metrics_loader.py`: loads Top-K hits, rank metrics, tails, baseline lift, effect size, bootstrap intervals, permutation p-values, and adjusted p-values from formal artifacts.
- `statistical_review.py`: maps metric observations into supporting, contradicting, neutral, or invalidating assessments.
- `evidence_builder.py`: builds formal `EvidenceRecord` objects.
- `evidence_repository.py`: appends Evidence through the existing Hypothesis Registry service.
- `decision_builder.py`: aggregates sequential Evidence and creates deterministic Decision Drafts.
- `hypothesis_updater.py`: applies approved Decision Requests to the Registry.
- `family_updater.py`: read-only helper for family status after decisions.
- `validation.py`: validates Evidence and Decision Draft contracts.
- `service.py`: high-level CLI orchestration.

## CLI

```text
dehps evidence build
dehps evidence show
dehps evidence aggregate
dehps decision draft
dehps decision review
dehps decision approve
dehps decision reject
```

`evidence build` appends formal Evidence by default. `decision draft` creates a `research_decision_submission` Agent Request and submits it by default. `decision approve` performs Reviewer approval, starts an audited Reviewer execution, applies the Registry transition, and completes the Agent Request.

## Decision Policy

The default policy is intentionally cautious:

- invalid artifact validation -> `invalidated`;
- no forward/future coverage -> `inconclusive`;
- strong positive evidence with forward coverage -> `accepted_for_followup`;
- consistent parameter-region failure -> `rejected` with `parameter_region`;
- consistent multi-experiment mechanism failure with forward non-support -> `rejected` with `mechanism_family`.

Round 24 has no forward validation, so Round 25 should not convert its frozen-only results into acceptance or mechanism rejection.

## API

Read-only API endpoints:

```text
GET /research-evidence
GET /research-evidence/:key
GET /research-decisions
GET /research-decisions/:key
GET /research-review/status
```

No write routes are exposed.
