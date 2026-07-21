# Mainline Mail Copy Format v1

Date: 2026-07-21

Engineering authorization: Agent Request `engineering-mainline-mail-copy-format-20260721-v1` (request `168`, execution `89`).

## Primary Goal

Make the scheduled `static_100` email directly copyable into a chat input by removing presentation and diagnostic noise from the message body.

## Body Contract

The plain-text body contains exactly 100 lines. Every line contains only one six-red-ball combination:

```text
01 05 09 18 26 33
02 07 11 19 25 31
```

The separator between combinations is one newline character. The body contains no:

- rank;
- score;
- headings;
- blank lines;
- runtime or model metadata;
- explanatory or risk paragraphs.

The HTML alternative is one `<pre>` block containing the identical escaped text, so HTML-preferring email clients preserve the same copy/paste line boundaries.

## Preserved Integrity

Rank and score remain internal validation inputs. Before rendering, the compiler still requires contiguous ranks `1..100`, finite scores, legal sorted red balls, no duplicate numbers within a combination, and no duplicate Top-100 combinations.

Issue identity and evidence maturity remain visible in the subject:

```text
[DEHPS][实验性·未达预测目标] 双色球 {issue} 主线 Top 100
```

The prediction source, order, delivery key, ledger, recipient, QQ SMTP transport, and 17:00 schedule are unchanged.

## Production Correction

Issue `2026083` was successfully delivered at 17:00 using the prior verbose format. After this format revision is merged, a separate Operator Request may send one explicitly labeled format-correction email without altering the original `sent` ledger entry.

## Validation

Commands and results:

```text
python -m pytest -q tests/test_mainline_prediction_mail.py tests/test_mail_service.py tests/test_latest_prediction.py
30 passed

python -m pytest -q
1347 passed, 4 skipped, 4 existing Python 3.14 fork warnings

live read-only compile of issue 2026083
lines=100
all_number_only=true
rank_present=false
score_present=false
blank_lines=0
html_pre=true

git diff --check
passed
```

External correction delivery remains a separate Operator action.
