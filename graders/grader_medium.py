from server.environment import ProductionIncidentEnv


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
    return min(1.0, score)
