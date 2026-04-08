from server.environment import ProductionIncidentEnv


def _strict_score(value: float) -> float:
    return max(0.01, min(0.99, round(value, 4)))


def grader_medium(environment: ProductionIncidentEnv) -> float:
    state = environment.state()
    score = 0.0
    if state.root_cause_confirmed:
        score += 0.4
    if state.service_restored:
        score += 0.4
    if state.failed_checks == 0:
        score += 0.1
    if "restart_service" not in environment.action_history:
        score += 0.1
    return _strict_score(score)
