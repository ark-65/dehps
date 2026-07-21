# Post-draw Three-line Evaluation Report Mail v1

Date: 2026-07-21

Engineering authorization: Agent Request `engineering-post-draw-three-line-report-mail-20260721-v1` (request `170`, execution `91`).

## Primary Goal

After an official draw update completes accepted forward Evaluation, compile and send one detailed report showing how the actual draw ranked in each of the three prediction lines.

## Evidence Boundary

The report consumes only persisted pre-draw `forward_prediction_runs`, their immutable candidate snapshots, completed `forward_evaluation_runs`, and accepted `training_prediction_evaluations`. It fails closed unless:

- exactly one evaluation exists for each of `static_100`, `dynamic_kdj`, and `dynamic_kdj_near`;
- all rows bind to the same issue and actual draw;
- `as_of_issue < predicted_issue` and `leakage_passed=true`;
- evaluation, prediction, and evaluation-run statuses are completed;
- evaluation, prediction, and persisted candidate counts all equal the frozen `top_n`;
- Ranking Audit covers the same 1,107,568-combination legal red-ball universe;
- full-universe model rank is legal and final export rank agrees with the frozen snapshot;
- Top100/1000/10000 flags agree with their underlying exact-six or red-five rank;
- Evaluation Artifact state is verified or explicitly recorded as unavailable for legacy-compatible evidence.

## Report Contract

For every line the report includes:

- actual combination's full-universe `model_score_rank`;
- frozen TopN `final_export_rank` or an explicit not-exported result;
- exact-six Top100/1000/10000;
- best red-five rank and Top100/1000/10000;
- counts of exact-six and red-five combinations at each cutoff;
- initial/model/export ranking path and elimination reason;
- prediction snapshot, prediction run, evaluation run, configuration and fingerprint;
- candidate completeness, Ranking Contract, leakage result, Evaluation Artifact, Runtime Envelope, and Candidate ABI identities.

Exact-six and red-five results are never merged. Scores are intentionally omitted because the operational question is ordinal rank and cutoff membership. The blue ball is recorded but not scored.

## Delivery Contract

The report payload is canonicalized and SHA-256 addressed. JSON and text artifacts are written before SMTP. The delivery key binds issue, report digest, and recipient. A sent report is idempotently skipped; an ambiguous SMTP failure becomes `uncertain` and blocks automatic retry.

The daily pipeline invokes report delivery only when synchronization inserted or updated draw data, after the forward Evaluation batch succeeds and before next-issue signal/candidate generation. Notification failure is recorded without blocking the next prediction snapshot.

Production activation and external delivery remain a separate Operator action.

## Non-goals

- feature, weight, window, candidate, scoring, ranking, Evaluation, or Promotion changes;
- predictive-lift or statistical-significance claims;
- blue-ball scoring;
- incomplete report delivery;
- any change to the independent 17:00 pre-draw Top-100 mail.

## Validation

Commands and results:

```text
python -m pytest -q tests/test_post_draw_evaluation_mail.py tests/test_daily_pipeline.py tests/test_mail_service.py tests/test_mainline_prediction_mail.py tests/test_prediction_evaluation.py tests/test_forward_evaluation_service.py tests/test_ranking_audit.py
64 passed

python -m pytest -q
1360 passed, 4 skipped, 4 existing Python 3.14 fork warnings

dehps mail post-draw-evaluation --issue 2026082 --preview
status=preview
line_count=3
report_digest=dd20fc9cfa6f2fd8fec5025523b390307bbd9b2757a52648e863d51f3dcf5a58

git diff --check
passed
```

The read-only production preview compiled issue `2026082` from exactly three accepted rows. It reported full-universe model ranks of `738672` (`static_100`), `736511` (`dynamic_kdj`), and `714931` (`dynamic_kdj_near`). All three were outside the frozen Top10,000 for exact-six and red-five. No SMTP connection was opened by preview.
