# OpenIncident X Hackathon Demo Script

## Target Length

90 seconds to 2 minutes

## Opening

OpenIncident X is an OpenEnv-compatible multi-agent environment for training
LLMs on realistic software incident response.

Instead of toy tasks, the agent operates in a professional software-operations
world with partial observability. It has to inspect evidence, identify likely
root cause, choose mitigation actions, and resolve incidents correctly.

## Problem

Real incidents are hard for LLMs because:

- they are long-horizon
- the model does not see everything at once
- the wrong early action can make later decisions worse
- success is not just "do something" but "restore service and close correctly"

## Environment

Our core environment is `ProductionIncidentEnv`.

It exposes:

- `reset()`
- `step(action)`

The action space includes:

- inspect logs
- inspect metrics
- inspect traces
- inspect deploys
- inspect config
- inspect code
- identify root cause
- apply fix
- rollback deploy
- restart service
- resolve incident

## Training Target

For this hackathon, we train the `Reliability Agent`.

This is the strongest RL target in our system because it has:

- a real sequential action space
- a reward loop
- success and failure conditions
- meaningful recovery behavior

## Reward Story

The agent is rewarded for:

- gathering useful evidence
- identifying the right root cause
- restoring service
- resolving the incident properly

It is penalized for:

- wasted actions
- harmful actions
- premature closure
- restored-but-not-resolved outcomes

## Results

We compare:

- a random baseline
- an epsilon-greedy trained policy

And we track more than just raw reward:

- root cause rate
- restore rate
- success rate
- closure gap rate

That lets us show real behavioral improvement, not just a bigger number.

## Multi-Agent Story

Around the trained Reliability Agent, we also model a realistic multi-agent
 workflow:

- Planner routes tasks
- Frontend and API agents generate validation signals
- Observability provides runtime evidence
- Triage summarizes likely cause
- Guardian blocks unsafe release
- Oversight audits the workflow

So this is both a trainable environment and a believable professional system.

## Closing

OpenIncident X shows how to train LLMs on realistic incident-response behavior:
long-horizon reasoning, partial observability, operational recovery, and
multi-agent coordination in a professional software environment.
