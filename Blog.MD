# OpenIncident X Hackathon Writeup

## Title

OpenIncident X: Training Incident-Response Agents in a Long-Horizon, Partially Observable Operations Environment

## Problem We Targeted

Most LLM evaluations are short and clean. Real production incidents are not.
During an outage, an agent must inspect incomplete signals, form a diagnosis, apply a safe fix, verify recovery, and close with discipline.

We built OpenIncident X to model that workflow as a trainable environment.

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
- trained success: `33.33%`
- trained root-cause rate: `63.33%`
- trained restore rate: `43.33%`
- trained closure gap: `10.00%`

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
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

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

- Space: https://thanayr-openincident.hf.space
- GitHub: https://github.com/thanayr99/OpenIncident
- Colab: https://colab.research.google.com/drive/1R4IrMr5nIKm7lZfbI08EP9ijkUgF7fxH?usp=sharing

## Closing

OpenIncident X is built to train agents that do more than answer.
It trains agents to investigate, diagnose, recover, and close incidents under uncertainty in a realistic software-operations workflow.
