# OpenIncident X Colab Quickstart

## Goal

This is the fastest path to run the hackathon training demo in Google Colab.

The notebook flow is intentionally small:

1. install dependencies
2. clone the repo
3. run the baseline and trained policy
4. inspect saved artifacts

## Mandatory HF TRL Notebook Path

For the explicit hackathon requirement ("minimal HF TRL or Unsloth training
in Colab"), use:

- `colab/OpenIncidentX_HF_TRL_Minimal.ipynb`

Or run the script directly:

```python
!python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --env-profile v1 --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

If running locally on Windows PowerShell, set UTF-8 mode first:

```powershell
$env:PYTHONUTF8='1'
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --env-profile v1 --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

## Recommended Colab Cells

### 1. Clone the repo

```python
!git clone <YOUR_REPO_URL>
%cd AgenEnv
```

### 2. Install dependencies

```python
!python -m pip install --upgrade pip
!python -m pip install fastapi openai openenv-core playwright pydantic pyyaml requests sqlalchemy "psycopg[binary]" uvicorn matplotlib
```

If you want the HuggingFace policy path too:

```python
!python -m pip install transformers torch
```

### 3. Run the hackathon-friendly wrapper

```python
!python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo
```

If you are running locally in PowerShell or CMD instead of Colab, remove the `!`:

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo
```

### 4. Inspect the saved metrics JSON

```python
import json
from pathlib import Path

metrics = json.loads(Path("artifacts/colab_demo/medium_epsilon_metrics.json").read_text())
metrics
```

### 5. Display the reward plot

```python
from IPython.display import Image, display
display(Image(filename="artifacts/colab_demo/medium_epsilon_rewards.png"))
```

## What This Produces

The wrapper saves:

- rewards CSV
- reward plot PNG
- metrics JSON

Example output files:

- `artifacts/colab_demo/medium_epsilon_rewards.csv`
- `artifacts/colab_demo/medium_epsilon_rewards.png`
- `artifacts/colab_demo/medium_epsilon_metrics.json`

## What To Say In The Demo

Use the metrics JSON and reward plot to explain:

- baseline vs trained behavior
- success rate improvement
- closure gap reduction
- shorter average trajectories

## Recommended Hackathon Run

For the clearest current story, use:

```python
!python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo
```

Local PowerShell equivalent:

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo
```

This is the most stable and believable training result in the current project.

For the stricter environment upgrade path, run V2 side-by-side (without replacing V1 artifacts):

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 40 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2
```

```powershell
$env:PYTHONUTF8='1'
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --env-profile v2 --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal_v2
```

To show contrast in your demo, run deterministic once and stochastic once:

```python
!python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode deterministic --env-profile v1 --output-dir artifacts/colab_deterministic
!python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_stochastic
```

## Optional HuggingFace Policy Run

If compute and time allow:

```python
!python colab/run_openincident_hackathon.py --task-id hard --episodes 10 --baseline-random 5 --policy hf --hf-model distilgpt2 --output-dir artifacts/colab_hf
```

Local PowerShell equivalent:

```powershell
python colab/run_openincident_hackathon.py --task-id hard --episodes 10 --baseline-random 5 --policy hf --hf-model distilgpt2 --output-dir artifacts/colab_hf
```

This is optional. The main hackathon story should still be the medium-task
epsilon-greedy training result.
