# Near Dynamic Rolling V3

## Primary Goal

将 `dynamic_kdj_near` 临期线从 expanding 历史训练切换为 rolling 历史训练。

## Behavior

- 临期回归目标窗口仍固定为最近 9 个已知目标。
- 每个临期目标的打分训练历史改为 rolling：只使用目标期之前最近 `train_window` 条历史。
- 当前 supervisor 参数下，`train_window=900`，所以临期线使用最近 900 期历史，而不是近 10 年全部 expanding 历史。
- 普通主线 `static_100` 与普通动态线 `dynamic_kdj` 不变。
- KDJ 信号仍读取现有 canonical signal run；当前信号表只有 `expanding/900` 信号，因此本轮不强制切换信号来源，避免临期线退化成静态 fallback。

## Non-Goals

- 不新增新特征。
- 不改变临期目标 `3/10 exact red6 Top100`。
- 不改变主线或普通动态线训练模式。

## Guardrails

- 每个 target 仍只能使用目标期之前的数据。
- 报表和候选快照必须显示临期线 `train_mode=rolling`。
- 临期候选生成也必须只喂最近 `train_window` 条历史。

## Validation

Planned validation:

```bash
bash -n scripts/ensure_training_supervisor.sh
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_next_candidates.py apps/worker-python/tests/test_prediction_evaluation.py apps/worker-python/tests/test_training_supervisor.py apps/worker-python/tests/test_training_watch.py apps/worker-python/tests/test_line_overlap_audit.py
```

After deployment, restart the supervisor and confirm a fresh `dynamic_kdj_near` line round reports:

- `train_mode = rolling`
- `eval_window = 9`
- `target_count = 9`
- `leakage_passed = true`
