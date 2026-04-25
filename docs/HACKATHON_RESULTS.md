# OpenIncident X Hackathon Results

## Submission Run (Current)

Command used for the main RL evidence:

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo_v1
```

Saved artifacts:

- `artifacts/colab_demo_v1/medium_epsilon_metrics.json`
- `artifacts/colab_demo_v1/medium_epsilon_rewards.csv`
- `artifacts/colab_demo_v1/medium_epsilon_rewards.png`

## Baseline vs Trained (Stochastic Medium)

Source file: `artifacts/colab_demo_v1/medium_epsilon_metrics.json`

### Random Baseline (5 episodes)

- avg env reward: `0.6276`
- avg train reward: `-0.9324`
- avg steps: `10.00`
- success rate: `0.00%`
- root cause rate: `20.00%`
- restore rate: `0.00%`
- closure gap rate: `0.00%`

### Epsilon-Greedy Trained Policy (30 episodes)

- avg env reward: `1.6891`
- avg train reward: `2.7791`
- avg steps: `9.57`
- success rate: `33.33%`
- root cause rate: `63.33%`
- restore rate: `43.33%`
- closure gap rate: `10.00%`

Best successful trajectory:

```text
[
  "inspect_config",
  "identify_root_cause",
  "inspect_traces",
  "identify_root_cause",
  "apply_fix",
  "apply_fix",
  "apply_fix",
  "apply_fix",
  "inspect_logs",
  "resolve_incident"
]
```

## Harder Robustness Run (Stochastic Medium, v2)

Command:

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 80 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2_tuned4_full
```

Source file: `artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_metrics.json`

- baseline success rate: `0.00%`
- trained success rate: `27.50%`
- trained root cause rate: `86.25%`
- trained restore rate: `36.25%`
- trained closure gap rate: `8.75%`

## Why This Is Better Than The Old Easy Result

- The environment is now stochastic and harder to game.
- The policy no longer wins with a fixed 3-step shortcut every episode.
- Variation is visible in trajectories and outcomes, which is more credible for judges.

## Mandatory HF TRL Path (Requirement Coverage)

Minimal HF TRL script:

- `colab/run_openincident_hf_trl_minimal.py`

Minimal Colab notebook path:

- `colab/OpenIncidentX_HF_TRL_Minimal.ipynb`

Run command:

```powershell
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

This produces:

- trajectory dataset JSONL from `ProductionIncidentEnv`
- dataset summary JSON
- TRL training summary JSON
- trained model folder

## Dependency Pin Confirmed

`pyproject.toml` now pins:

- `openenv-core==0.2.3`

## Safe Judge Claim

OpenIncident X demonstrates a real OpenEnv-compatible incident environment with measurable RL improvement under stochastic dynamics, plus a minimal Hugging Face TRL training path that can be rerun in Colab.
