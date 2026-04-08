from __future__ import annotations

from typing import Optional

import requests

from models import IncidentAction, IncidentObservation, StepResult


class OpenEnvClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def reset(self, task_id: str = "easy", max_steps: Optional[int] = None) -> IncidentObservation:
        payload = {"task_id": task_id, "max_steps": max_steps}
        response = requests.post(f"{self.base_url}/reset", json=payload, timeout=20)
        response.raise_for_status()
        return IncidentObservation.model_validate(response.json())

    def step(self, action_type: str, target: Optional[str] = None, content: Optional[str] = None) -> StepResult:
        payload = IncidentAction(action_type=action_type, target=target, content=content).model_dump(mode="json")
        response = requests.post(f"{self.base_url}/step", json=payload, timeout=20)
        response.raise_for_status()
        return StepResult.model_validate(response.json())

    def state(self) -> IncidentObservation:
        response = requests.get(f"{self.base_url}/state", timeout=20)
        response.raise_for_status()
        return IncidentObservation.model_validate(response.json())
