# OpenIncident X Hackathon Writeup

## Title

OpenIncident X: Training Incident-Response Agents in a Long-Horizon, Partially Observable Operations Environment

## Problem We Targeted

Most LLM evaluations are short and clean. Real production incidents are not.
During an outage, an agent must inspect incomplete signals, form a diagnosis, apply a safe fix, verify recovery, and close with discipline.

We built OpenIncident X to model that workflow as a trainable environment.

## Why I Chose This Project

I chose this because reliability incidents are high-pressure and high-impact.
At 2 AM, during real outages, engineers do not need another explanation tool; they need disciplined action under uncertainty.

Many current AI systems can describe incidents, but they do not reliably handle end-to-end incident response:

- what to inspect first
- how to avoid misleading signals
- when to fix versus when to roll back
- when it is actually safe to close

OpenIncident X is my attempt to train agents for this exact capability gap.

## Environment Design

Primary environment:

- `ProductionIncidentEnv`

Interaction pattern:

- `reset()`
- `step(action)`

Action space includes:

- inspect logs, metrics, traces, config, code, deploy context
- identify root cause
- apply fix, rollback deploy, restart or scale service
- add monitor
- resolve incident

The world is partially observable, so the agent cannot just execute a static script; it must gather evidence and adapt.

## Multi-Agent Product Framing

OpenIncident X also includes a multi-agent application layer:

- Planner routes stories and execution order
- Frontend/API agents run validation checks
- Observability aggregates logs and signals
- Reliability handles incident response workflows
- Triage summarizes likely root cause and next action
- Guardian and Oversight gate safety and quality

For this submission, the primary trained role is the `Reliability Agent`.

## Training Setup

We compare:

- random baseline policy
- epsilon-greedy Q-learning policy

And track:

- success rate
- root-cause confirmation rate
- restore rate
- closure gap rate
- reward trajectory

We also provide a minimal Hugging Face TRL pipeline to satisfy the training-script requirement.

## Results

### Official judged packet (stochastic medium, profile=v1)

Source:

- `artifacts/colab_demo_v1/medium_epsilon_metrics.json`

Key outcomes:

- baseline success: `0.00%`
- trained success: `26.67%`
- trained root-cause rate: `63.33%`
- trained restore rate: `30.00%`
- trained closure gap: `3.33%`

### Harder robustness packet (stochastic medium, profile=v2)

Source:

- `artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_metrics.json`

Key outcomes:

- baseline success: `0.00%`
- trained success: `27.50%`
- trained root-cause rate: `86.25%`
- trained restore rate: `36.25%`
- trained closure gap: `8.75%`

Interpretation:

- v1 is our stable benchmark packet.
- v2 is a stricter environment profile that improves anti-shortcut behavior and diagnosis discipline.

## HF TRL Requirement Coverage

Minimal TRL script:

- `colab/run_openincident_hf_trl_minimal.py`

Minimal notebook:

- `colab/OpenIncidentX_HF_TRL_Minimal.ipynb`

Example command:

```bash
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --env-profile v2 --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_loss_proof
```

## Training Evidence Artifacts

- reward plot v1: `artifacts/colab_demo_v1/medium_epsilon_rewards.png`
- reward plot v2: `artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_rewards.png`
- TRL loss plot: `artifacts/trl_loss_proof/medium_stochastic_v2_trl_loss.png`
- TRL loss CSV: `artifacts/trl_loss_proof/medium_stochastic_v2_trl_loss.csv`
- TRL summary JSON: `artifacts/trl_loss_proof/medium_stochastic_v2_trl_summary.json`

## Video Narrative Flow (Used in Final Demo)

This is the polished story arc used in the final 7 to 8 minute walkthrough:

1. 2 AM outage hook and why incident response is hard.
2. Why explanation-only AI is not enough.
3. Product walkthrough: login, project setup, runtime context.
4. Check execution and incident creation from failed validations.
5. Multi-agent collaboration: Planner, Frontend/API, Observability, Reliability, Triage, Guardian, Oversight.
6. RL environment: partially observable `ProductionIncidentEnv`.
7. Reward logic and safe-action behavior.
8. v1 benchmark result vs baseline.
9. v2 harder-profile robustness result.
10. HF TRL reproducibility path and final conclusion.

Full script file:

- `VIDEO_SCRIPT_FINAL.md`
- HF direct link: `https://huggingface.co/spaces/thanayr/OpenIncident/blob/main/VIDEO_SCRIPT_FINAL.md`

## Is This Real Data or Simulation?

Training data is generated from environment trajectories, not from a static scraped dataset.
This is a controlled incident simulation designed for measurable policy improvement.

The product layer can ingest real runtime signals (health checks, API checks, browser checks, logs), but the RL benchmark is evaluated in the environment for reproducibility and fairness.

## Reproduce in 2 Commands

```bash
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo_v1
python colab/run_openincident_hackathon.py --task-id medium --episodes 80 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2_tuned4_full
```

## Links

- Space (Hub): https://huggingface.co/spaces/thanayr/OpenIncident
- Space (App): https://thanayr-openincident.hf.space
- Live application: https://open-incident.vercel.app/
- GitHub: https://github.com/thanayr99/OpenIncident
- Colab: https://colab.research.google.com/drive/1R4IrMr5nIKm7lZfbI08EP9ijkUgF7fxH?usp=sharing
- YouTube demo: https://youtu.be/8L-1TsajsTA?si=2ZaoWftUeKxj0jqS

## Submission Checklist (Final)

- OpenEnv latest pinned: `openenv-core==0.2.3`
- OpenEnv-compatible environment implemented: `ProductionIncidentEnv`
- Minimal HF TRL training script provided: `colab/run_openincident_hf_trl_minimal.py`
- Colab notebook linked for rerun: `colab/OpenIncidentX_HF_TRL_Minimal.ipynb`
- Real training evidence included: reward plots + TRL loss plot and CSV
- Hugging Face Space published and runnable
- Separate blog MD included (`Blog.MD`)
- Video link included and cross-linked from README/Space
- Reproducibility commands included

## Closing

OpenIncident X is built to train agents that do more than answer.
It trains agents to investigate, diagnose, recover, and close incidents under uncertainty in a realistic software-operations workflow.
