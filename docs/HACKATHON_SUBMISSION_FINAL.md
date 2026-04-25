# OpenIncident X Hackathon Final Submission Guide

Last updated: April 25, 2026

## 1) Non-Negotiable Requirement Check

- `OpenEnv usage`: `ProductionIncidentEnv` with `reset()` + `step(action)` is implemented and used in training.
- `Minimal training script`: RL loop is in `rl_training.py` and Colab wrapper in `colab/run_openincident_hackathon.py`.
- `HF TRL / Unsloth requirement`: minimal HF TRL path is now added:
  - script: `colab/run_openincident_hf_trl_minimal.py`
  - notebook: `colab/OpenIncidentX_HF_TRL_Minimal.ipynb`
- `Reward evidence`: CSV + PNG + JSON metrics are generated under `artifacts/colab_demo_v1/` (official) and `artifacts/colab_demo_v2_tuned4_full/` (harder robustness).
- `README-level explanation`: updated in `hf_space/README.md` and `docs/HACKATHON_RESULTS.md`.
- `OpenEnv version pin`: `openenv-core==0.2.3` in `pyproject.toml`.

## 2) Exact Commands To Reproduce

Main RL evidence run:

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo_v1
```

Harder robustness RL run:

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 80 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2_tuned4_full
```

Minimal HF TRL run:

```powershell
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

Windows PowerShell (safe UTF-8 mode for TRL template loading):

```powershell
$env:PYTHONUTF8='1'
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

## 3) Files To Show Judges

- `artifacts/colab_demo_v1/medium_epsilon_metrics.json`
- `artifacts/colab_demo_v1/medium_epsilon_rewards.png`
- `artifacts/colab_demo_v1/medium_epsilon_rewards.csv`
- `artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_metrics.json`
- `artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_rewards.png`
- `artifacts/trl_minimal/medium_stochastic_dataset_summary.json`
- `artifacts/trl_minimal/medium_stochastic_trl_summary.json`
- `artifacts/rl_test_cases_65.json`

## 4) Current Main Result (Stochastic Medium)

From `artifacts/colab_demo_v1/medium_epsilon_metrics.json`:

- baseline success rate: `0.00%`
- trained success rate: `33.33%`
- trained root cause rate: `63.33%`
- trained restore rate: `43.33%`
- trained closure gap rate: `10.00%`

Harder profile cross-check (`artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_metrics.json`):

- baseline success rate: `0.00%`
- trained success rate: `27.50%`
- trained root cause rate: `86.25%`
- trained restore rate: `36.25%`
- trained closure gap rate: `8.75%`

## 5) What To Say In Demo

- We model incident response as a partially observable OpenEnv world, not a static benchmark.
- The trained Reliability Agent improves measurable outcomes versus random baseline in stochastic mode.
- We provide both a native RL loop and a minimal HF TRL path that trains on environment-generated trajectories.
- The system is multi-agent at product level, with Reliability as the primary trainable policy in this submission.

## 6) Final Packaging Checklist Before Submit

- Push latest repo with updated docs and Colab notebook.
- Ensure HF Space points to `hf_space/app.py` and updated `hf_space/README.md`.
- Add final links in root README: Space URL, Colab notebook URL, short video/blog URL.
- Freeze one final metrics run and do not change artifacts after submission lock.
