# Knowledge Roadmap

## Mission

Maintain the definitions and decisions shared by Runtime and Research so neither lane silently
redefines a feature, window, candidate, metric, or evidence claim. Knowledge records explain and
index authority; they do not themselves authorize implementation, operation, or promotion.

## Knowledge map

| Knowledge family | Authoritative location | Contents |
| --- | --- | --- |
| Domain contracts | `docs/architecture/scoring-input-contract-v1.md`, source/data docs | Legal universe, draw identity, history and source boundaries |
| Contract Runtime | `docs/architecture/contract-runtime-architecture.md` and contract-specific specs | Contract DAG, compiler, ABI, verifier, planner, envelope, artifacts |
| Feature definitions | `docs/architecture/feature-contract-v1.md` and normative code manifest | Feature names, formulas, ordering, Golden identity, version |
| Candidate definitions | `docs/architecture/candidate-abi-v1.md` and Candidate Contract docs | Candidate identity, universe, ordering, layouts, rank/unrank |
| Window definitions | `docs/architecture/scoring-input-contract-v1.md` and history/window specs | Rolling/expanding semantics, target boundary, history binding |
| Evaluation semantics | `docs/architecture/evaluation-contract-v1.md`, `objective-policy.md` | Metric formulas, rank namespaces, cutoffs, status and promotion meaning |
| Active research protocols | [Frozen-Future-30 rolling-history preregistration](../experiments/2026-07-20-m2-frozen-future-30-rolling-history.md), Agent Request ledger | Frozen versus rolling identities, pre-outcome boundaries, null model, decision rule, invalidation conditions |
| Research theory and sources | `docs/theory/`, `docs/sources/`, future reviewed paper notes | Assumptions, references, applicability, limitations |
| Architecture decisions | `docs/architecture/` | Current design, invariants, compatibility, non-goals |
| Research OS orchestration | [Goal-Driven Research Orchestrator](../architecture/goal-driven-research-orchestrator.md) | Goal Graph, Task DAG, Evidence Bundle, Review, Resource Manager, Capability ABI, scheduler boundaries |
| Decision records | `DECISIONS.md` and future focused ADRs | Project-level choices, reasons, consequences, supersession |
| Experiment evidence | `docs/experiments/` | Frozen round contract, commands, results, failures, next test |
| Milestones and roadmaps | `docs/milestones/`, `docs/roadmaps/` | Capability acceptance, active objective, ownership, planned gates |

## Required metadata

Every new normative knowledge item must state:

- status: draft, accepted, deprecated, or superseded;
- owner lane: Runtime, Research, Knowledge, or cross-lane;
- semantic/version identity where applicable;
- source facts and evidence links;
- assumptions, invariants, and explicit non-goals;
- compatibility or supersession relationship;
- last verified date or commit when it reports mutable state.

## Vocabulary rules

- `Contract` means normative semantics and compatibility identity.
- `ABI` means packed machine layout; it is not a model or feature hypothesis.
- `Artifact` means durable result plus provenance and payload identity.
- `Recent-N` names exact issues and whether the window selected or validated the configuration.
- `Walk-forward` names the as-of rule, training mode, target identities, and leakage boundary.
- `Prediction Quality` refers to model/research evidence, never Runtime test or throughput evidence.
- `Runtime Health` refers to current verified platform evidence, never a historical milestone badge.
- `Expected Value` remains undefined until its economic contract exists.
- `Goal` means a versioned objective completed by reviewed success Evidence, never merely by Task completion.
- `Task` means a schedulable unit with typed dependencies; waiting is local to the Task.
- `Evidence Bundle` means an immutable reviewed collection of Evidence and is the only admissible Promotion input.

## Maintenance rules

- Prefer links to one normative definition over copying formulas into multiple reports.
- A semantic change requires a version or a superseding decision, not an in-place reinterpretation.
- Reports may cite a contract but may not silently amend it.
- Dashboard labels and API fields must link or map to the governing definition.
- Deprecated knowledge remains discoverable with its replacement; historical artifacts are not
  rewritten to match newer semantics.
- Quarterly or milestone review should identify stale state claims, broken links, duplicate
  definitions, and decisions lacking a supersession path.

## Near-term backlog

1. Implement the Goal Graph and Task DAG compatibility layer described by the accepted Research OS
   architecture without changing scientific or production behavior.
2. Add a generated read-only Knowledge index to the dashboard after the dual-dashboard foundation.
3. Give every Research KPI an Evaluation Semantics entry with unit, window, null, and freshness.
4. Convert large cross-cutting decisions into focused ADRs when `DECISIONS.md` no longer provides
   enough context.
5. Add reviewed research-paper notes only when they state domain transfer limits and a falsifiable
   DEHPS implication.
