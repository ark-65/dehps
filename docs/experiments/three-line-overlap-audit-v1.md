# Three-Line Overlap Audit V1

## Primary Goal

建立三条训练线的逐期差异审计：

- `static_100` 主线
- `dynamic_kdj` 动态线
- `dynamic_kdj_near` 临期动态线

审计目标是回答：命中到底是主线独有、动态线独有、临期线独有，还是三线共同命中。这个 round 不继续迷信“多跑几轮”，而是验证三条线是否真的换了搜索空间。

## Non-Goals

- 不新增预测算法。
- 不调整权重排序目标。
- 不宣称训练已经达到预测能力。
- 不把红5辅助命中计入主指标。

## Behavior

动态线与临期动态线的训练 summary 现在保存 `target_results`，与主线一致，包含每个目标期的：

- issue 与 draw date
- 红6真实号码
- exact red6 rank 与 Top100/Top1000/Top10000 标记
- red5 rank 与 Top100/Top1000/Top10000 辅助标记

新增审计脚本：

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/analyze_training_line_overlap.py
```

脚本从 `training_line_round_results` 读取同一个 run/round 的三条线，输出 JSON 和 Markdown 到：

```text
data/output/optimization/line-overlap-audits/
```

## Metrics

主指标：

- exact red6 Top100

辅助观察：

- exact red6 Top1000/Top10000
- red5 Top100/Top1000/Top10000
- static -> dynamic 的 rescued/lost issue
- near window 中 9 个临期目标的逐期排名差异

## Guardrails

- 法定红球样本空间固定为 `1,107,568`。
- 每个 target 的训练边界必须只使用目标期之前的数据。
- 旧动态线数据如果没有 `target_results`，审计报告必须标记为 `partial`。
- 红5只作为结构辅助观察，不计入临期 3/10 主目标。
- 历史命中只作为预测假设证据，不作为预测能力证明。

## Gauss/Riemann Review

Gauss pass:

- 先看逐期集合和 rank，不先相信 aggregate。
- 对 Top100、Top1000、Top10000 分别做 rescued/lost 计数。
- 报告保留缺失 target 明细的 warning，避免把不可比数据当作可比数据。

Riemann pass:

- 三条线应被看成同一候选空间中的三种局部坐标变换。
- 如果动态线命中只是主线命中的重叠，它没有提供新空间。
- 如果临期线只在近 9 期产生独有命中，下一步应研究临期结构而不是扩大长期训练轮数。

Smallest shared conclusion:

```text
瓶颈本身不是坏事；下一步先审计命中集合差异，再决定是否需要新特征或新目标。
```

## Validation

Planned validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_next_candidates.py apps/worker-python/tests/test_line_overlap_audit.py apps/worker-python/tests/test_prediction_evaluation.py apps/worker-python/tests/test_training_supervisor.py apps/worker-python/tests/test_training_watch.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/analyze_training_line_overlap.py --run-id 20260709-163014 --round-index 1 --output-dir /tmp/dehps-line-overlap-smoke
```
