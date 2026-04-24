# How To Test OpenIncident X

This guide is the practical end-to-end checklist for testing the current product yourself.

## 1. What You Are Testing

OpenIncident X has four connected layers:

1. Frontend dashboard
   - Sign in, create projects, run checks, import stories/test cases, connect logs, inspect agents
2. Backend API
   - Auth, projects, stories, checks, logs, incidents, triage, planner/environment summaries
3. Database
   - Neon Postgres stores accounts, projects, runs, stories, logs, metrics, events, and training datasets
4. Agent layer
   - Planner, Environment, Frontend, API, Observability, Reliability, Triage, Guardian, Oversight

## 2. Start The System

### Backend

From the repo root:

```powershell
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Check:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/system/status
```

Expected:

- API responds
- storage engine is `postgresql`
- database target is `neon-postgres`

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local Vite URL in the browser.

## 3. Project Setup Flow

### Step A: Sign in

Use the login screen.

If the account does not exist yet, the app will create it automatically during the login/register flow.

### Step B: Create a project

Fill in:

- project name
- GitHub repository URL
- deployed URL if available
- health path if available

### Step C: Open dashboard

After the project is created or selected, the command center opens.

## 4. Recommended Full End-To-End Test

Use this exact order for a strong product test:

1. Sign in
2. Create a project
3. Open the dashboard
4. Pull GitHub workspace
5. Discover frontend routes
6. Import bulk test cases
7. Run health check
8. Run browser smoke check
9. Run API smoke check
10. Connect logs manually or configure log connector
11. Pull connected logs
12. Run predeploy gate
13. Triage active incident if one exists
14. Inspect Planner Board
15. Inspect Environment Context
16. Inspect Agent Training Lab
17. Inspect Selected Agent Training panel

## 5. How To Check Each Major Agent

### Planner Agent

What it does:

- reads stories/test cases
- classifies domain
- assigns responsible agent
- sets execution priority
- suggests next actions

What to test:

1. Import stories/test cases
2. Open `Planner Board`
3. Confirm:
   - analyzed stories count
   - domain breakdown
   - assigned agents
   - confidence
   - priorities

Useful API:

```text
GET /projects/{project_id}/planner-summary
GET /projects/{project_id}/planner-training-dataset
```

### Environment Agent

What it does:

- inspects repository/workspace
- detects framework
- infers app root
- infers install/test commands
- reports route count

What to test:

1. Click `Pull GitHub workspace`
2. Click `Discover frontend routes`
3. Confirm:
   - framework
   - app root
   - workdir
   - route count
   - recommended commands

Useful API:

```text
GET /projects/{project_id}/environment-summary
```

### Frontend Test Agent

What it does:

- builds browser validation plan
- infers route
- uses expected text / selector signals
- validates UI behavior

What to test:

1. Add a frontend-oriented story/test case
2. Run browser check or story execution
3. Confirm:
   - inferred route
   - expected text
   - selector usage
   - result summary

Useful API:

```text
GET /projects/{project_id}/frontend-training-dataset
```

### API Test Agent

What it does:

- infers or uses API path hints
- checks method/status expectations
- validates API behavior

What to test:

1. Add API-focused test case
2. Run API smoke check
3. Confirm:
   - target path
   - expected status
   - actual status
   - pass/fail result

Useful API:

```text
GET /projects/{project_id}/api-training-dataset
```

### Observability Agent

What it does:

- records check evidence
- correlates logs, degraded metrics, and incidents
- helps explain failure context

What to test:

1. Connect logs manually or via connector
2. Run health/browser/API checks
3. Confirm:
   - logs appear
   - log summary updates
   - observability metrics appear in dashboard

Useful API:

```text
GET /projects/{project_id}/logs
GET /projects/{project_id}/logs/summary
GET /projects/{project_id}/observability-training-dataset
```

### Reliability Agent

What it does:

- handles incident-response style decisions
- inspects evidence
- drives mitigation / restoration / closure

What to test in product:

1. Cause or detect unhealthy checks
2. Confirm active incident/run appears
3. Triage it
4. Check incident summary and recommendations

What to test in RL trainer:

```powershell
python rl_training.py --task-id medium --episodes 30 --policy epsilon --env-mode deterministic
python rl_training.py --task-id medium --episodes 30 --policy epsilon --env-mode stochastic
```

Interpretation:

- `deterministic` mode is the simple baseline (fast convergence, often near-perfect).
- `stochastic` mode is the realistic benchmark (scenario variability, delayed verification, and non-trivial success rates).

### Triage Agent

What it does:

- summarizes incidents
- proposes likely root cause
- recommends next actions

What to test:

1. Open or detect an incident
2. Click `Triage active incident`
3. Confirm:
   - summary
   - confidence
   - recommended actions

Useful API:

```text
GET /projects/{project_id}/triage-training-dataset
```

### Guardian Agent

What it does:

- decides release readiness
- blocks release if stories/incidents/checks are not acceptable

What to test:

1. Run predeploy gate
2. Confirm:
   - `Ready` or `Blocked`
   - decision summary
   - story/incidence impact on release

Useful API:

```text
GET /projects/{project_id}/guardian-training-dataset
```

### Oversight Agent

What it does:

- audits handoffs and decisions
- captures review-level quality signals

What to test:

1. Run multiple workflows with incidents and story execution
2. Confirm audits accumulate

Useful API:

```text
GET /projects/{project_id}/oversight-training-dataset
```

## 6. Bulk Test Case Format

The bulk import supports structured QA-style cases like this:

```text
Test Case ID: TC_AUTH_001
Title: Verify successful login with valid credentials
Priority: High
Preconditions: The user has a registered account and is on the login page.
Test Steps:
1. Enter valid email in the username field.
2. Enter valid password in the password field.
3. Click the Login button.
Test Data: User: test@example.com, Pass: P@ssword123
Expected Result: User is redirected to the dashboard and a Welcome message is displayed.
Actual Result:
Status:
---
```

It also supports JSON arrays of stories or test cases.

## 7. Log Testing

### Manual logs

Paste lines like:

```text
[ERROR] api: Database connection timeout while serving /api/profile
[WARNING] frontend: Login button render took 2200ms
[INFO] worker: Retry succeeded for profile sync
```

### Log connector

You can configure an HTTP log source with:

- URL
- method
- format (`text` or `json`)
- optional JSON `entries_path`

Example JSON payload:

```json
{
  "data": {
    "logs": [
      {
        "timestamp": "2026-04-22T12:00:00Z",
        "level": "ERROR",
        "source": "api",
        "message": "Database timeout"
      }
    ]
  }
}
```

Use:

```text
entries_path = data.logs
```

## 8. Useful Backend Endpoints

System:

- `GET /health`
- `GET /system/status`
- `GET /system/agent-training-plan`
- `GET /system/database/overview`

Project:

- `GET /projects`
- `GET /projects/{project_id}/summary`
- `GET /projects/{project_id}/planner-summary`
- `GET /projects/{project_id}/environment-summary`

Training datasets:

- `GET /projects/{project_id}/planner-training-dataset`
- `GET /projects/{project_id}/frontend-training-dataset`
- `GET /projects/{project_id}/api-training-dataset`
- `GET /projects/{project_id}/observability-training-dataset`
- `GET /projects/{project_id}/triage-training-dataset`
- `GET /projects/{project_id}/guardian-training-dataset`
- `GET /projects/{project_id}/oversight-training-dataset`

## 9. What “Dataset” Means Here

In this project, a dataset is not a big ML dataset downloaded from somewhere else.

It means:

- structured history of agent decisions
- structured history of execution outcomes
- evidence collected from real project runs

Examples:

- Planner dataset:
  how a story was classified, which agent got assigned, what happened later
- Frontend dataset:
  inferred route, expected text, browser result, pass/fail
- API dataset:
  expected endpoint behavior vs actual endpoint behavior
- Guardian dataset:
  release ready vs blocked decisions over time
- Triage dataset:
  confidence, suspected root cause, recommendations, restoration outcome

So the datasets are the learning and evaluation memory for the agents.

## 10. If Something Looks Wrong

Check in this order:

1. `GET /health`
2. `GET /system/status`
3. project summary
4. planner summary
5. environment summary
6. logs summary
7. latest incidents/runs
8. training dataset endpoints

If the frontend looks wrong but APIs are correct, the issue is likely in rendering or layout.

## 11. Recommended Current Focus

For the next phase, the best practical order is:

1. make the frontend clearer and less cramped
2. validate the full flow on HouseSafe AI
3. inspect datasets after real runs
4. refine agents one by one
5. only after that, generalize aggressively to very different projects
