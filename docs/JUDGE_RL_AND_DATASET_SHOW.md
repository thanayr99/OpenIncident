# How To Show RL + Dataset To Judges

## 1) Run One Command Before Demo

From repo root:

```powershell
python scripts/judge_rl_packet.py --metrics artifacts/colab_demo/medium_epsilon_metrics.json --testcases artifacts/rl_test_cases_65.json --output artifacts/judge_rl_packet.md
```

This prints and writes a clean judge packet with:
- exact task/policy/seed
- baseline vs trained metrics
- testcase coverage split
- artifact paths

Use this as your source of truth during Q&A.

## 1.1) Run Mandatory HF TRL Path

From repo root:

```powershell
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

Show:

- `artifacts/trl_minimal/medium_stochastic_dataset_summary.json`
- `artifacts/trl_minimal/medium_stochastic_trl_summary.json`

## 2) What To Say About "Dataset Used"

Say this clearly:

1. RL optimization uses **online rollouts**, not a fixed supervised dataset.
2. Each training sample is `state -> action -> reward -> next_state -> done`.
3. Scenario/task distributions come from `tasks/easy.py`, `tasks/medium.py`, `tasks/hard.py`.
4. We also maintain an explicit **evaluation coverage pack**:
   `artifacts/rl_test_cases_65.json` (65 structured RL test cases).

## 3) 90-Second RL Evidence Sequence

1. Show `artifacts/colab_demo/medium_epsilon_metrics.json`.
2. Show `artifacts/colab_demo/medium_epsilon_rewards.png`.
3. Show `artifacts/rl_test_cases_65.json`.
4. Show generated `artifacts/judge_rl_packet.md`.

Then say:

- "This is the exact run and seed used in our demo."
- "These are the before/after metrics."
- "This is the testcase coverage used to evaluate RL behavior."

## 4) If Judges Ask "How Do You Check The Agent?"

Use both:

1. CLI evidence:
   - `python rl_training.py --task-id medium --episodes 30 --policy epsilon --baseline-random 5`
2. Product evidence:
   - Dashboard `Execution` -> `Evidence` -> `Training`
   - Show incident chain and dataset-backed agent records.

## 5) Important Honesty Line

If asked about diagnosis quality, say:

"We currently optimize closure behavior strongly, and we are tightening diagnosis strictness in the environment so resolution requires confirmed root cause plus restoration."
