# OpenIncident X Final Video Script + Results

Use this as the primary recording script.
All metrics below are taken from the current repo artifacts.

## Personal Intro (Optional: 20-30 sec before 0:00)

Say:

"I am Thanay Reddy, and I built OpenIncident X to solve a practical gap in AI systems.
Today, models can explain incidents, but they rarely handle them end-to-end like an on-call engineer.
I care deeply about reliability because wrong actions in production have real user impact.
This project focuses on training agents to operate under uncertainty, not just respond to prompts."

Show:

- Landing screen
- Project logo + command center theme

## 0:00-0:25 Cinematic Hook

Say:

"It is 2 AM.
A payment service goes down.
Alerts are firing, users are complaining, and dashboards are half broken.

Logs show one thing, metrics show another.
Nobody knows the root cause yet.

And the engineer on-call has to figure it out fast.

This is the reality of production systems.
And this is exactly the problem I wanted to solve."

Show:

- Open dashboard or landing page
- Slow cursor movement

## 0:25-0:50 Why This Project

Say:

"Today's AI systems can explain incidents well, but they do not actually handle them.
They do not decide what to inspect next, they do not verify recovery, and they do not take responsibility for closure.
That is the gap this project is solving."

Show:

- Guided workflow cards
- Agent panels

## 0:50-1:15 Project Intro

Say:

"This is OpenIncident X, an OpenEnv-compatible multi-agent incident response platform.
It is built to train and evaluate agents on realistic production scenarios, not toy tasks."

Show:

- Login screen
- Transition into app

## 1:15-1:45 Real Context Setup

Say:

"After login, we create a project with real inputs:
repository URL, frontend URL, backend API URL, and health paths.
That gives the system runtime context instead of static prompting."

Show:

- Setup form filled
- Save project

## 1:45-2:15 Incident Generation

Say:

"Now we run health, browser, API, workspace, and route checks.
If validation fails, it becomes a structured incident with evidence."

Show:

- Click checks
- Show incident/event feed

## 2:15-2:40 Real-World Challenge: Misleading Signals

Say:

"Real incidents often have misleading signals.
An API failure can actually originate from a database timeout or a bad deployment dependency.
If you inspect only one signal, you fix the wrong thing."

Show:

- Logs + runtime signals + evidence panel

## 2:40-3:20 Multi-Agent System

Say:

"We use a coordinated agent system.
Planner prioritizes execution.
Frontend and API agents validate behavior.
Observability gathers runtime signals.
Reliability agent correlates evidence and drives incident handling."

Show:

- Agent cards and execution chain
- Event log updates

## 3:20-3:50 Deeper Intelligence Layer

Say:

"Triage explains likely root cause.
Database agent reasons about persistence-side failure paths.
Guardian enforces safe decisions.
Oversight audits decisions and closure quality.
This is structured operational reasoning."

Show:

- Right-side agent intelligence panels
- Incident notes

## 3:50-4:15 Key Difference

Say:

"The key difference is that OpenIncident X does not stop at failure reporting.
It produces actionable diagnosis grounded in runtime evidence."

Show:

- Open incident details
- Evidence list

## 4:15-4:45 RL Environment Intro

Say:

"Under the hood, the trainable environment is ProductionIncidentEnv.
The agent can inspect logs, metrics, traces, identify root cause, apply fixes, rollback when needed, and resolve incidents."

Show:

- Training tab
- Environment/action references

## 4:45-5:10 Partial Observability

Say:

"The environment is partially observable.
The agent never sees all truth at once.
It must choose what to inspect, when to act, and how to avoid unsafe actions."

Show:

- Move between logs/metrics/traces

## 5:10-5:35 Wrong-Fix Risk

Say:

"In production, wrong actions can increase downtime.
For example, a restart can wipe useful in-memory state and make recovery harder.
So we train not just for action speed, but for action quality and safety."

Show:

- Incident evidence where action choice matters

## 5:35-6:00 Reward Design

Say:

"Reward shaping favors evidence-driven diagnosis, safe recovery, and proper closure.
Guessing and premature closure are penalized."

Show:

- Reward/metrics outputs

## 6:00-6:25 Results: Benchmark v1 (Official Packet)

Source:

- `artifacts/colab_demo_v1/medium_epsilon_metrics.json`

Say:

"In stochastic medium profile v1, random baseline has 0% success.
After training, success improves to 26.67%, with strong diagnosis gains."

Show on screen:

- Baseline success: `0.00%`
- Trained success: `26.67%`
- Trained root-cause rate: `63.33%`
- Trained restore rate: `30.00%`
- Trained closure gap: `3.33%`

## 6:25-6:50 Results: Harder Robustness Profile v2

Source:

- `artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_metrics.json`

Say:

"In a stricter v2 profile, success is 27.50%, while root-cause quality increases to 86.25%.
This shows the policy is learning diagnosis discipline under harder dynamics."

Show on screen:

- Baseline success: `0.00%`
- Trained success: `27.50%`
- Trained root-cause rate: `86.25%`
- Trained restore rate: `36.25%`
- Trained closure gap: `8.75%`

## 6:50-7:10 HF TRL + Reproducibility

Say:

"We also provide a reproducible Hugging Face TRL path with Colab notebook and saved artifacts."

Show:

- HF Space
- Colab notebook link
- TRL command

TRL evidence files:

- `artifacts/trl_minimal_v2/medium_stochastic_v2_dataset_summary.json`
- `artifacts/trl_minimal_v2/medium_stochastic_v2_trl_summary.json`

Key TRL stats:

- dataset records: `150`
- episodes collected: `80`
- warmup episodes: `20`
- train loss: `10.8227`
- model: `sshleifer/tiny-gpt2`

## 7:10-7:35 Contribution Summary

Say:

"This project delivers four things:
a realistic incident environment,
a multi-agent reasoning system,
measurable RL improvement over baseline,
and a deployable product workflow."

Show:

- Full command center
- Agent chain
- Training metrics

## 7:35-8:00 Closing

Say:

"If AI agents are going to be trusted in real systems, they cannot just generate answers.
They should handle a 2 AM outage with the discipline of a real engineer.
That is OpenIncident X."

Show:

- Final branded dashboard frame
- Hold for 2-3 seconds

## Recording Checklist (Quick)

- Keep one browser tab for app demo.
- Keep one tab for HF Space results.
- Keep one tab for Colab notebook.
- Zoom UI to 90%-100% for readability.
- Record at 1080p.
- Speak slower than normal conversation pace.
