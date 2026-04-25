# OpenIncident X V2 Execution And Backup Plan

## Goal

Ship environment V2 improvements without breaking the working V1 demo.

## Safety Model

1. `v1` stays the default profile for all existing runs.
2. `v2` is opt-in via `--env-profile v2`.
3. V1 and V2 artifacts are stored in separate output folders.

## Environment Profiles

- `v1`: current baseline behavior (stable backup path)
- `v2`: stricter sequencing and closure discipline

V2 adds:

- stronger evidence requirements before diagnosis
- stronger inspection requirements before mitigation
- multi-signal recovery verification
- closure gate requiring monitoring for medium/hard incidents

## Command Matrix

### 1) Baseline Backup (V1)

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo_v1
```

### 2) V2 Evaluation

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 40 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2
```

### 3) V2 TRL Dataset + Training

```powershell
$env:PYTHONUTF8='1'
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --env-profile v2 --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal_v2
```

## What To Present

1. `v1` (stable benchmark): proves reproducibility.
2. `v2` (harder world): proves improved environment quality and anti-shortcut design.
3. Baseline vs trained metrics for both profiles.
4. One best successful trajectory and one failed trajectory (with done reason).
