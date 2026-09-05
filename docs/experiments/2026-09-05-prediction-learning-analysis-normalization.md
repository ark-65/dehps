# First-round analysis completion after payout field mismatch

The frozen experiment at commit `8620a24` completed all 2,599 outer issues and
trained checkpoint `09f936e09e2a935fc7ff5c286904a3edc996dbca0590114677102f19577384a8`.
Its subsequent analysis failed because the Zhcw raw record exposes
`frontWinningNum/backWinningNum`, while the frozen payout consumer reads
`red/blue`. This is a field adapter error, not a model/data-label mismatch.

This Engineering acceptance round uses the existing, frozen Zhcw normalizer to
derive the missing aliases. It saves the original raw record, the normalized
record and both digests. Prize fields and frozen draw labels must match exactly.
The original contract, source files, issue results, checkpoint, attempt ledger,
failed analysis task/event and raw payout artifact are preserved.

The same Goal receives one additive analysis-completion Task, dispatched by the
existing ResearchEvidenceSupervisor in the same isolated experiment database.
Its Ready condition is the registered training completion. Its inputs are the
frozen contract and training index; its runner identity additionally binds the
normalization script SHA256. Outputs are the raw-to-normalized payout attestation,
the unchanged frozen analysis results and a RESEARCH_ONLY experimental Top-100.
Status is projected in `analysis-field-normalization-v1/learning-status.json`.
The downstream consumer is deterministic replay and the same frozen research
decision; no Formal P3 Evidence or deployment authority is created.

No fit, candidate generation, random repetition, metric, bootstrap, configuration,
selection rule or search budget changes. The runner imports the original source
from the preserved experiment worktree and checks its complete frozen identity.
The final report will distinguish this operational completion from the original
failed analysis. It does not erase or reset the first-round attempts.

An additional existing test failure was verified on both base main and the
experiment: the non-frozen audit partition count had grown beyond a hard-coded
433 (446 on base, 449 on the experiment). The acceptance test retains frozen
partition counts 65/4/11, all disjointness and coverage checks, and explicitly
checks that the new learning modules belong only to the audit partition.
