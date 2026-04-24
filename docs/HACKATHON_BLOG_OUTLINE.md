# OpenIncident X Hackathon Blog / Video Outline

## Title

OpenIncident X: Training LLMs For Long-Horizon Incident Response In A Multi-Agent Software Operations World

## Hook

Most LLM benchmarks are short, clean, and unrealistic.
Real software incidents are the opposite:

- partial information
- many possible tools
- delayed rewards
- long-horizon recovery workflows
- coordination across multiple specialist roles

OpenIncident X is our attempt to turn that operational reality into a trainable OpenEnv environment.

## Problem

When production systems fail, a good agent must do more than answer questions.
It must:

- gather the right evidence
- form a useful hypothesis
- choose recovery actions
- avoid premature closure
- finish the workflow properly

That is difficult for LLMs because the task unfolds over time.

## Our Environment

Our core environment is `ProductionIncidentEnv`.

The agent interacts through:

- `reset()`
- `step(action)`

Available actions include:

- inspect logs
- inspect metrics
- inspect traces
- inspect config
- inspect code
- rollback deploy
- restart service
- apply fix
- resolve incident

The world is partially observable, so the agent must learn when to inspect,
when to act, and when to close.

## Multi-Agent Framing

The environment is embedded inside a broader multi-agent system:

- Planner routes tasks
- Frontend and API agents generate validation signals
- Observability summarizes runtime evidence
- Triage explains likely root cause
- Guardian blocks unsafe release
- Oversight audits decisions

For the hackathon, we trained the `Reliability Agent` first because it has the
clearest RL structure.

## Training

We built a lightweight training loop in:

- [rl_training.py](C:/My%20Projects/AgenEnv/rl_training.py)

We compare:

- a random baseline
- an epsilon-greedy policy

And track:

- reward
- success rate
- restoration rate
- closure gap rate

## Results

On the `medium` task:

- random baseline success rate: `0%`
- trained policy success rate: `33.33%` (stochastic medium)
- closure gap held to `10%` in stochastic mode
- average steps reduced from `10.0` to `9.57`

This shows the trained agent is substantially better at finishing incident workflows.

## Why This Matters

This project sits at the intersection of:

- `Theme #3.1 Professional Tasks`
- `Theme #2 Long-Horizon Planning`
- `Theme #1 Multi-Agent Interactions`

It is not just another chatbot benchmark.
It is a realistic operational world where agents must act, recover, and coordinate.

## What’s Next

After the hackathon, we want to:

- tighten root-cause confirmation in the reward logic
- train additional agents beyond Reliability
- expand cross-project realism
- package the environment more directly for hosted OpenEnv demos

## Closing

OpenIncident X is our step toward training LLMs not just to answer, but to
operate inside realistic software systems with evidence, uncertainty, and real
recovery consequences.
