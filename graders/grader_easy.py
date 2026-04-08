from server.environment import ProductionIncidentEnv


def grader_easy(environment: ProductionIncidentEnv) -> float:
    state = environment.state()
    score = 0.0
    if state.root_cause_confirmed:
        score += 0.5
    if state.service_restored:
        score += 0.4
    if state.current_status == "resolved":
        score += 0.1
    return min(1.0, score)
