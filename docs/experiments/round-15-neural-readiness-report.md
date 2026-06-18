# Round 15 Report: Neural Readiness Probe

## Summary

- Added a pure NumPy CPU MLP feasibility probe for DEHPS.
- The current machine can run small neural baselines comfortably on CPU.
- CUDA-class GPU training is not available on this host; the detected accelerator path is Intel Arc iGPU/NPU, not the first target for this repo.
- The first neural-network milestone should be a frozen, time-split CPU baseline, not a large model.

## Hardware Snapshot

```text
CPU: Intel Core Ultra 7 155H, 22 logical CPUs
RAM: 30 GiB total, about 25 GiB available at check time
GPU: Intel Arc integrated graphics
NPU: Intel Meteor Lake NPU detected
CUDA/NVIDIA: unavailable
Python ML deps: numpy available; torch/tensorflow/sklearn/jax/numba unavailable
```

## Probe

Command:

```bash
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_neural_feasibility_probe.py --as-of-issue 2026067 --max-sample-rows 20000 --negative-ratio 10 --epochs 2 --hidden-units 32 --batch-size 4096 --learning-rate 0.03
```

Result:

```text
report: data/output/optimization/neural-feasibility-20260618-102235.md
elapsed: 0:10.04
maxrss: 1055796 KB
universe_rows: 1105506
sampled_rows: 16434
feature_count: 61
estimated_dense_full_universe_features: 0.251 GiB
last_epoch_rows_per_second: 1011307.7
validation_auc_epoch_2: 0.486419
```

## Interpretation

The machine can handle a small CPU neural baseline now. A dense full-universe static feature frame is only about 0.25 GiB as float32, and the smoke run stayed near 1.1 GiB RSS.

The probe does not show useful signal yet. Validation AUC near 0.5 means the tiny static MLP is basically at null behavior on this sampled historical-vs-negative task. That is acceptable for this phase: the goal was hardware and pipeline feasibility, not promotion.

## Neural Network Gate

Neural work is allowed to enter the training loop after these gates:

- Freeze a time-split protocol so no draw after the train cutoff affects feature scaling or labels.
- Add same-budget structural/frequency/null baselines beside the neural score.
- Store neural experiment summaries in DB, not in large JSON files.
- Promote only if frozen validation beats the baselines on objective score and does not increase tail risk.

## Next Step

Add an experimental `neural_cpu_mlp_v0` scorer that can produce a score vector for the existing universe matrix, but keep it behind an explicit flag and outside the default supervisor candidate generation until it beats the controls.

## Guardrail

This is a feasibility result for historical hypothesis testing. It is not evidence that a neural network can predict random draws.
