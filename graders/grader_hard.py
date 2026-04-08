from server.environment import ProductionIncidentEnv


def _strict_score(value: float) -> float:
    return max(0.01, min(0.99, round(value, 4)))


def grader_hard(environment: ProductionIncidentEnv) -> float:
    state = environment.state()
    score = 0.0
    if state.root_cause_confirmed:
        score += 0.35
    if state.service_restored:
        score += 0.30
    if state.mitigation_applied:
        score += 0.15
    if state.monitoring_added:
        score += 0.10
    if state.steps_taken <= 8:
        score += 0.10
    return _strict_score(score)
