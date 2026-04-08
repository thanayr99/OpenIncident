from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from models import IncidentAction, IncidentObservation, StepResult
from server.environment import ProductionIncidentEnv


class ResetRequest(BaseModel):
    task_id: str = "easy"
    max_steps: int | None = None


app = FastAPI(title="Production Incident Debugging Environment", version="1.0.0")
environment = ProductionIncidentEnv()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/reset", response_model=IncidentObservation)
def reset_environment(request: ResetRequest) -> IncidentObservation:
    global environment
    try:
        environment = ProductionIncidentEnv(task_id=request.task_id, max_steps=request.max_steps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return environment.reset()


@app.post("/step", response_model=StepResult)
def step_environment(action: IncidentAction) -> StepResult:
    observation, reward, done, info = environment.step(action)
    return StepResult(observation=observation, reward=reward, done=done, info=info)


@app.get("/state", response_model=IncidentObservation)
def get_state() -> IncidentObservation:
    return environment.state()


def main() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
