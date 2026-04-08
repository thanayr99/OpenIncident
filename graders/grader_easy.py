from server.environment import ProductionIncidentEnv


def _strict_score(value: float) -> float:
    return max(0.01, min(0.99, round(value, 4)))


def grader_easy(environment: ProductionIncidentEnv) -> float:
    state = environment.state()
    score = 0.0
    if state.root_cause_confirmed:
        score += 0.5
    if state.service_restored:
        score += 0.4
    if state.current_status == "resolved":
        score += 0.1
    return _strict_score(score)
