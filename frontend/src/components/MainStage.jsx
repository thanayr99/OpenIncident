import { useState } from "react";
import { roleMeta } from "../data/agents";
import { formatPercent, formatTime } from "../utils/format";

function summarizeTrainingDatasets(trainingDatasets) {
  return [
    {
      key: "planner",
      label: "Planner",
      total: trainingDatasets?.planner?.analyzed_records || 0,
      metricLabel: "Route match",
      metricValue: formatPercent(trainingDatasets?.planner?.route_match_rate || 0),
      secondary: `${trainingDatasets?.planner?.completed_records || 0} completed`,
    },
    {
      key: "frontend",
      label: "Frontend",
      total: trainingDatasets?.frontend?.planned_records || 0,
      metricLabel: "Route hints",
      metricValue: formatPercent(trainingDatasets?.frontend?.route_hint_match_rate || 0),
      secondary: `${trainingDatasets?.frontend?.successful_records || 0} successful`,
    },
    {
      key: "api",
      label: "API",
      total: trainingDatasets?.api?.planned_records || 0,
      metricLabel: "Status match",
      metricValue: formatPercent(trainingDatasets?.api?.status_match_rate || 0),
      secondary: `${trainingDatasets?.api?.successful_records || 0} successful`,
    },
    {
      key: "observability",
      label: "Observability",
      total: trainingDatasets?.observability?.total_records || 0,
      metricLabel: "Incident link",
      metricValue: formatPercent(trainingDatasets?.observability?.incident_link_rate || 0),
      secondary: `${trainingDatasets?.observability?.records_with_log_errors || 0} log-error records`,
    },
    {
      key: "triage",
      label: "Triage",
      total: trainingDatasets?.triage?.total_triages || 0,
      metricLabel: "Avg confidence",
      metricValue: formatPercent(trainingDatasets?.triage?.average_confidence || 0),
      secondary: `${trainingDatasets?.triage?.records?.length || 0} triage records`,
    },
    {
      key: "guardian",
      label: "Guardian",
      total: trainingDatasets?.guardian?.total_decisions || 0,
      metricLabel: "Healthy ready",
      metricValue: formatPercent(trainingDatasets?.guardian?.healthy_ready_rate || 0),
      secondary: `${trainingDatasets?.guardian?.ready_decisions || 0} ready decisions`,
    },
    {
      key: "oversight",
      label: "Oversight",
      total: trainingDatasets?.oversight?.total_audits || 0,
      metricLabel: "Resolved run audits",
      metricValue: formatPercent(trainingDatasets?.oversight?.resolved_run_audit_rate || 0),
      secondary: `${trainingDatasets?.oversight?.run_linked_audits || 0} run-linked`,
    },
  ];
}

function buildDetailGroups(records, fields) {
  return (records || []).slice(0, 12).map((record, index) => ({
    id: record.story_id || record.run_id || record.validation_id || record.audit_id || record.record_id || record.triage_id || index,
    title: record.title || record.summary || record.label || record.trigger_reason || record.audit_type || record.suspected_root_cause || `Record ${index + 1}`,
    rows: fields
      .map(([label, key]) => {
        const value = record?.[key];
        if (value === null || value === undefined || value === "") return null;
        if (Array.isArray(value)) return [label, value.join(", ") || "None"];
        if (typeof value === "boolean") return [label, value ? "Yes" : "No"];
        return [label, String(value)];
      })
      .filter(Boolean),
  }));
}

export function MainStage({
  selectedProject,
  activeRuns,
  latestStory,
  metricCards,
  summary,
  plannerSummary,
  environmentSummary,
  trainingDatasets,
  stageView,
  setStageView,
  logs,
  logSummary,
  recentEvents,
  frontendDiscovery,
  latestCheck,
  predeployResult,
  handoffs,
  conversations,
  pullWorkspace,
  discoverFrontend,
  runHealthCheck,
  runBrowserSmoke,
  runApiSmoke,
  runPredeployGate,
  runMissionControl,
  triageFirstIncident,
  busy,
  launchDemoFlow,
}) {
  const [detailPanel, setDetailPanel] = useState(null);
  const fallbackHandoffs = [
    { from_role: "planner", to_role: "api_tester", handoff_type: "demo" },
    { from_role: "api_tester", to_role: "reliability_analyst", handoff_type: "demo" },
    { from_role: "reliability_analyst", to_role: "oversight", handoff_type: "demo" },
  ];
  const fallbackMessages = [
    {
      message_id: "demo-1",
      sender_role: "planner",
      recipient_role: "frontend_tester",
      content: "Planner is ready to route stories into frontend, API, database, and reliability workflows.",
      timestamp: new Date().toISOString(),
    },
    {
      message_id: "demo-2",
      sender_role: "test_env_guardian",
      recipient_role: "oversight",
      content: "Guardian will block release readiness until user stories, repo tests, and incidents are clean.",
      timestamp: new Date().toISOString(),
    },
  ];

  const configuredEndpoints = Array.isArray(selectedProject?.endpoints) ? selectedProject.endpoints : [];
  const frontendEndpoint = configuredEndpoints.find((endpoint) => (endpoint?.surface || "").toLowerCase() === "frontend")
    || configuredEndpoints.find((endpoint) => (endpoint?.endpoint_id || "").toLowerCase() === "frontend")
    || configuredEndpoints[0]
    || null;
  const apiEndpoint = configuredEndpoints.find((endpoint) => (endpoint?.surface || "").toLowerCase() === "api")
    || configuredEndpoints.find((endpoint) => (endpoint?.endpoint_id || "").toLowerCase() === "backend")
    || null;
  const productionUrl = frontendEndpoint?.base_url || selectedProject?.base_url || "";
  const apiBaseUrl = apiEndpoint?.base_url || "";
  const repositoryName = selectedProject?.repository_url?.split("/").slice(-2).join("/").replace(".git", "") || "Repository not linked";
  const latestHealth = summary?.latest_health;
  const metricSummary = summary?.metric_summary;
  const latestMetricEntries = Object.entries(metricSummary?.latest_values || {}).slice(0, 4);
  const storyReport = summary?.story_report;
  const plannerBreakdown = plannerSummary?.domain_breakdown || [];
  const plannerTopStories = plannerSummary?.stories?.slice(0, 4) || [];
  const environmentActions = environmentSummary?.next_actions || [];
  const trainingCards = summarizeTrainingDatasets(trainingDatasets);
  const hasTrainingData = trainingCards.some((item) => item.total > 0);
  const strongestTrainingCard = [...trainingCards].sort((a, b) => b.total - a.total)[0];
  const highestSignalTrainingCard = [...trainingCards].sort((a, b) => {
    const aValue = Number.parseInt(a.metricValue, 10) || 0;
    const bValue = Number.parseInt(b.metricValue, 10) || 0;
    return bValue - aValue;
  })[0];
  const latestConversationItems = (conversations.length ? conversations : fallbackMessages).slice(0, 8);
  const latestHandoffItems = (handoffs.length ? handoffs.slice(0, 7).reverse() : fallbackHandoffs);
  const recentEvidenceEvents = (recentEvents || []).slice(0, 6);
  const trainingDetailMap = {
    planner: {
      title: "Planner dataset records",
      subtitle: "Story routing, priority, and outcome alignment",
      groups: buildDetailGroups(trainingDatasets?.planner?.records, [
        ["Primary domain", "primary_domain"],
        ["Assigned agent", "assigned_agent"],
        ["Priority", "execution_priority"],
        ["Confidence", "confidence_score"],
        ["Outcome", "outcome_label"],
        ["Executed test", "executed_test_type"],
      ]),
    },
    frontend: {
      title: "Frontend dataset records",
      subtitle: "Route inference, selectors, expected text, and browser outcome",
      groups: buildDetailGroups(trainingDatasets?.frontend?.records, [
        ["Route", "inferred_route"],
        ["Expected text", "expected_text"],
        ["Expected selector", "expected_selector"],
        ["Outcome", "outcome_label"],
        ["Observed URL", "observed_url"],
        ["Page title", "page_title"],
      ]),
    },
    api: {
      title: "API dataset records",
      subtitle: "Endpoint expectations vs actual API responses",
      groups: buildDetailGroups(trainingDatasets?.api?.records, [
        ["Method", "expected_method"],
        ["Path", "inferred_path"],
        ["Expected status", "expected_status"],
        ["Actual status", "actual_status"],
        ["Outcome", "outcome_label"],
        ["Error", "error_message"],
      ]),
    },
    observability: {
      title: "Observability dataset records",
      subtitle: "Checks, log signals, degraded metrics, and incident linkage",
      groups: buildDetailGroups(trainingDatasets?.observability?.records, [
        ["Check type", "check_type"],
        ["Status", "status"],
        ["Target URL", "target_url"],
        ["Response ms", "response_time_ms"],
        ["Log errors", "log_error_entries"],
        ["Signals", "top_signals"],
      ]),
    },
    triage: {
      title: "Triage dataset records",
      subtitle: "Incident explanations, confidence, and recommended action history",
      groups: buildDetailGroups(trainingDatasets?.triage?.records, [
        ["Run status", "run_status"],
        ["Confidence", "confidence"],
        ["Root cause", "suspected_root_cause"],
        ["Recommendations", "recommended_action_types"],
        ["Service restored", "service_restored"],
        ["Root cause confirmed", "root_cause_confirmed"],
      ]),
    },
    guardian: {
      title: "Guardian dataset records",
      subtitle: "Release gate decisions and blocking conditions",
      groups: buildDetailGroups(trainingDatasets?.guardian?.records, [
        ["Decision", "decision_label"],
        ["Release ready", "release_ready"],
        ["Open incidents", "open_incident_count"],
        ["Latest check", "latest_check_status"],
        ["Failed stories", "failed_stories"],
        ["Blocked stories", "blocked_stories"],
      ]),
    },
    oversight: {
      title: "Oversight dataset records",
      subtitle: "Audit reviews tied to stories, runs, and workflow handoffs",
      groups: buildDetailGroups(trainingDatasets?.oversight?.records, [
        ["Audit type", "audit_type"],
        ["Source role", "source_role"],
        ["Story status", "linked_story_status"],
        ["Run status", "linked_run_status"],
        ["Confidence", "confidence_signal"],
        ["Session", "related_session_id"],
      ]),
    },
  };
  const checks = [
    {
      label: "Connect Git Repository",
      done: Boolean(selectedProject?.repository_url),
      action: "Repository linked",
    },
    {
      label: "Preview Deployment",
      done: Boolean(productionUrl || apiBaseUrl),
      action: productionUrl || apiBaseUrl ? "Live endpoint connected" : "Add frontend/backend URL",
    },
    {
      label: "Run Health Check",
      done: latestHealth?.status === "healthy",
      action: latestHealth?.status || "Not checked",
    },
    {
      label: "Discover Frontend Routes",
      done: Boolean(frontendDiscovery?.routes?.length),
      action: frontendDiscovery?.routes?.length ? `${frontendDiscovery.routes.length} routes` : "Not discovered",
    },
    {
      label: "Validate User Stories",
      done: Boolean(storyReport?.completed_stories),
      action: storyReport ? `${storyReport.completed_stories}/${storyReport.total_stories} complete` : "No story run",
    },
  ];
  const prototypeFlow = [
    {
      label: "Workspace",
      done: Boolean(environmentSummary?.workspace_ready),
      action: pullWorkspace,
      busyKey: "workspace",
      button: "Pull workspace",
      description: "Prepare repo context for the environment and planner agents.",
    },
    {
      label: "Frontend discovery",
      done: Boolean(frontendDiscovery?.routes?.length),
      action: discoverFrontend,
      busyKey: "discover",
      button: "Discover frontend",
      description: "Infer routes and UI surfaces before running browser-oriented stories.",
    },
    {
      label: "Story validation",
      done: Boolean(storyReport?.total_stories),
      action: launchDemoFlow,
      busyKey: "demoFlow",
      button: "Run demo flow",
      description: "Import the current story template if needed, then run the mission path.",
    },
    {
      label: "Release gate",
      done: Boolean(predeployResult),
      action: runPredeployGate,
      busyKey: "predeploy",
      button: "Run predeploy",
      description: "Compute a ready-or-blocked decision from all gathered evidence.",
    },
  ];
  const setupConnected = Boolean(selectedProject?.repository_url && (productionUrl || apiBaseUrl));
  const environmentReady = Boolean(environmentSummary?.workspace_ready || frontendDiscovery?.routes?.length);
  const storyValidated = Boolean(storyReport?.completed_stories || storyReport?.failed_stories || storyReport?.blocked_stories);
  const investigationReady = Boolean(activeRuns.length || logs.length || logSummary?.total_logs || recentEvidenceEvents.length);
  const gateReady = Boolean(predeployResult);
  const improvementReady = Boolean(hasTrainingData);
  const workflowSteps = [
    {
      key: "connect",
      label: "Connect",
      title: "Connect project",
      done: setupConnected,
      description: "Create or select a project, then provide GitHub plus frontend/backend deployment URLs.",
      actionLabel: selectedProject ? "Project connected" : "Use left setup",
      action: null,
    },
    {
      key: "prepare",
      label: "Prepare",
      title: "Prepare environment",
      done: environmentReady,
      description: "Pull repo context and discover frontend/backend surfaces for the agents.",
      actionLabel: environmentSummary?.workspace_ready ? "Discover frontend" : "Pull workspace",
      action: environmentSummary?.workspace_ready ? discoverFrontend : pullWorkspace,
      busyKey: environmentSummary?.workspace_ready ? "discover" : "workspace",
    },
    {
      key: "test",
      label: "Test",
      title: "Run story validation",
      done: storyValidated,
      description: "Execute the demo story/testcase flow and let agents produce evidence.",
      actionLabel: "Run demo flow",
      action: launchDemoFlow,
      busyKey: "demoFlow",
    },
    {
      key: "investigate",
      label: "Investigate",
      title: "Investigate failures",
      done: investigationReady,
      description: "Inspect logs, incidents, handoffs, and triage if failures appear.",
      actionLabel: activeRuns.length ? "Triage incident" : "Run health check",
      action: activeRuns.length ? triageFirstIncident : runHealthCheck,
      busyKey: activeRuns.length ? "triage" : "health",
    },
    {
      key: "gate",
      label: "Gate",
      title: "Run release gate",
      done: gateReady,
      description: "Ask Guardian whether the project is ready or blocked.",
      actionLabel: "Run predeploy",
      action: runPredeployGate,
      busyKey: "predeploy",
    },
    {
      key: "improve",
      label: "Improve",
      title: "Review agent learning",
      done: improvementReady,
      description: "Inspect agent datasets and the hackathon training story.",
      actionLabel: "Open training",
      action: () => setStageView("training"),
    },
  ];
  const currentWorkflowStep = workflowSteps.find((item) => !item.done) || workflowSteps[workflowSteps.length - 1];
  const currentWorkflowIndex = workflowSteps.findIndex((item) => item.key === currentWorkflowStep.key);
  const workflowProgress = Math.round((workflowSteps.filter((item) => item.done).length / workflowSteps.length) * 100);

  return (
    <main className="ox-main">
      <section className="stage-tabs">
        <button className={stageView === "overview" ? "active" : ""} onClick={() => setStageView("overview")} type="button">Overview</button>
        <button className={stageView === "execution" ? "active" : ""} onClick={() => setStageView("execution")} type="button">Execution</button>
        <button className={stageView === "evidence" ? "active" : ""} onClick={() => setStageView("evidence")} type="button">Evidence</button>
        <button className={stageView === "training" ? "active" : ""} onClick={() => setStageView("training")} type="button">Training</button>
      </section>

      <section className="guided-workflow">
        <div className="guided-workflow-main">
          <p className="ox-label">Guided Prototype Workflow</p>
          <h2>{currentWorkflowStep.title}</h2>
          <p>{currentWorkflowStep.description}</p>
          <div className="guided-workflow-actions">
            <button
              className="primary-action"
              type="button"
              disabled={!selectedProject || !currentWorkflowStep.action || busy[currentWorkflowStep.busyKey]}
              onClick={currentWorkflowStep.action || undefined}
            >
              {busy[currentWorkflowStep.busyKey] ? "Running..." : currentWorkflowStep.actionLabel}
            </button>
            <span>{workflowProgress}% complete</span>
          </div>
        </div>
        <div className="workflow-stepper">
          {workflowSteps.map((item, index) => (
            <button
              key={item.key}
              type="button"
              className={`${item.done ? "done" : ""} ${index === currentWorkflowIndex ? "current" : ""}`}
              onClick={() => {
                if (item.key === "test") setStageView("execution");
                else if (item.key === "investigate" || item.key === "gate") setStageView("evidence");
                else if (item.key === "improve") setStageView("training");
                else setStageView("overview");
              }}
            >
              <i>{item.done ? "OK" : index + 1}</i>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="project-hero">
        <header className="project-hero-top">
          <div>
            <p className="ox-label">Overview</p>
            <h1>{selectedProject?.name || "Project command center"}</h1>
            <p>{productionUrl || apiBaseUrl || "No deployed URL connected yet"}</p>
          </div>
          <div className="header-actions">
            <button className="primary-action" onClick={runMissionControl} disabled={!selectedProject || busy.mission} type="button">
              {busy.mission ? "Running mission..." : "Run Full Mission"}
            </button>
            <a className="hero-link" href={selectedProject?.repository_url || "#"} target="_blank" rel="noreferrer">Repository</a>
            <button onClick={runPredeployGate} disabled={!selectedProject || busy.predeploy} type="button">{busy.predeploy ? "Running..." : "Predeploy Gate"}</button>
            <a className="hero-link solid" href={productionUrl || apiBaseUrl || "#"} target="_blank" rel="noreferrer">Visit</a>
          </div>
        </header>

        <div className="deployment-card">
          <div className="deployment-preview">
            {productionUrl ? (
              <iframe title={`${selectedProject?.name} preview`} src={productionUrl} loading="lazy" />
            ) : (
              <div className="preview-empty">Deployment preview appears after adding a live URL.</div>
            )}
          </div>
          <div className="deployment-details">
            <span>Frontend</span>
            <strong>{productionUrl ? productionUrl.replace(/^https?:\/\//, "").replace(/\/$/, "") : "Not linked"}</strong>
            <span>Backend API</span>
            <strong>{apiBaseUrl ? apiBaseUrl.replace(/^https?:\/\//, "").replace(/\/$/, "") : "Not linked"}</strong>
            <span>Repository</span>
            <strong>{repositoryName}</strong>
            <span>Status</span>
            <strong className={latestHealth?.status === "healthy" ? "status-ready" : "status-warn"}>
              {latestHealth?.status === "healthy" ? "Ready" : latestHealth?.status || "Unchecked"}
            </strong>
            <span>Latest signal</span>
            <strong>{latestCheck?.label || activeRuns[0]?.trigger_reason || "No checks yet"}</strong>
          </div>
        </div>
      </section>

      <section className="metrics-strip">
        {metricCards.map(([label, value, hint, tone]) => (
          <article className={`metric-card ${tone}`} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <em>{hint}</em>
          </article>
        ))}
      </section>

      {stageView === "overview" ? (
        <section className="console-grid">
          <article className="overview-card prototype-card">
            <header>
              <h2>Prototype Flow</h2>
              <span>{prototypeFlow.filter((item) => item.done).length}/{prototypeFlow.length}</span>
            </header>
            <div className="prototype-flow-list">
              {prototypeFlow.map((item) => (
                <div className={`prototype-flow-row ${item.done ? "done" : ""}`} key={item.label}>
                  <div>
                    <strong>{item.done ? "OK" : "..."} {item.label}</strong>
                    <p>{item.description}</p>
                  </div>
                  <button
                    disabled={!selectedProject || item.done || busy[item.busyKey]}
                    onClick={item.action}
                    type="button"
                  >
                    {busy[item.busyKey] ? "Running..." : item.button}
                  </button>
                </div>
              ))}
            </div>
          </article>

          <article className="overview-card checklist-card">
            <header>
              <h2>Production Checklist</h2>
              <span>{checks.filter((item) => item.done).length}/{checks.length}</span>
            </header>
            {checks.map((item) => (
              <div className={item.done ? "check-row done" : "check-row"} key={item.label}>
                <i>{item.done ? "OK" : "..."}</i>
                <strong>{item.label}</strong>
                <em>{item.action}</em>
              </div>
            ))}
          </article>

          <article className="overview-card planner-card">
            <header>
              <h2>Planner Board</h2>
              <span>{plannerSummary ? `${plannerSummary.analyzed_stories}/${plannerSummary.total_stories}` : "No plan"}</span>
            </header>
            {plannerSummary ? (
              <>
                <div className="planner-actions">
                  {(plannerSummary.next_recommended_actions || []).slice(0, 3).map((item) => (
                    <span className="planner-pill" key={item}>{item}</span>
                  ))}
                </div>
                <div className="planner-breakdown">
                  {plannerBreakdown.slice(0, 4).map((item) => (
                    <div className="planner-domain-row" key={item.domain}>
                      <strong>{item.domain}</strong>
                      <span>{item.total_stories} stories</span>
                      <em>{item.assigned_agent}</em>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="muted">Analyze stories to see planner routing, priority, and next recommended actions.</p>
            )}
          </article>

          <article className="overview-card environment-card">
            <header>
              <h2>Environment Context</h2>
              <span>{environmentSummary?.workspace_ready ? "Workspace ready" : "Not ready"}</span>
            </header>
            {environmentSummary ? (
              <>
                <div className="environment-grid">
                  <div className="environment-chip">
                    <span>Framework</span>
                    <strong>{environmentSummary.framework || "Unknown"}</strong>
                  </div>
                  <div className="environment-chip">
                    <span>Routes</span>
                    <strong>{environmentSummary.route_count || 0}</strong>
                  </div>
                  <div className="environment-chip">
                    <span>Branch</span>
                    <strong>{environmentSummary.branch || "main"}</strong>
                  </div>
                  <div className="environment-chip">
                    <span>Workdir</span>
                    <strong>{environmentSummary.recommended_workdir || environmentSummary.app_root || "/"}</strong>
                  </div>
                </div>
                <div className="environment-command-list">
                  <div className="environment-command">
                    <span>Install</span>
                    <strong>{environmentSummary.recommended_install_command || "Not inferred"}</strong>
                  </div>
                  <div className="environment-command">
                    <span>Test</span>
                    <strong>{environmentSummary.recommended_test_command || "Not set"}</strong>
                  </div>
                </div>
                <div className="planner-actions environment-actions">
                  {environmentActions.slice(0, 3).map((item) => (
                    <span className="planner-pill environment-pill" key={item}>{item}</span>
                  ))}
                </div>
              </>
            ) : (
              <p className="muted">Pull a repository workspace to let the environment agent infer framework, routes, and setup commands.</p>
            )}
          </article>

          <article className="overview-card">
            <header>
              <h2>Observability</h2>
              <span>Live</span>
            </header>
            <div className="signal-row"><span>Response time</span><strong>{latestHealth?.response_time_ms ? `${latestHealth.response_time_ms}ms` : "Not checked"}</strong></div>
            <div className="signal-row"><span>Status code</span><strong>{latestHealth?.status_code || latestCheck?.status_code || "None"}</strong></div>
            <div className="signal-row"><span>Incidents</span><strong>{activeRuns.length}</strong></div>
            <div className="signal-row"><span>Release gate</span><strong>{predeployResult ? (predeployResult.release_ready ? "Ready" : "Blocked") : "Not run"}</strong></div>
          </article>
        </section>
      ) : null}

      {stageView === "execution" ? (
        <>
          <section className="console-grid execution-grid">
            <article className="overview-card ops-card">
              <header>
                <h2>Run Checks</h2>
                <span>Actions</span>
              </header>
              <button onClick={runHealthCheck} disabled={!selectedProject || busy.healthCheck} type="button">{busy.healthCheck ? "Checking..." : "Run health check"}</button>
              <button onClick={runBrowserSmoke} disabled={!selectedProject || busy.browserCheck} type="button">{busy.browserCheck ? "Rendering..." : "Run Playwright browser check"}</button>
              <button onClick={runApiSmoke} disabled={!selectedProject || busy.apiCheck} type="button">{busy.apiCheck ? "Calling..." : "Run API smoke check"}</button>
              <button onClick={pullWorkspace} disabled={!selectedProject || busy.workspace} type="button">{busy.workspace ? "Pulling..." : "Pull GitHub workspace"}</button>
              <button onClick={discoverFrontend} disabled={!selectedProject || busy.discover} type="button">{busy.discover ? "Scanning..." : "Discover frontend routes"}</button>
              <button onClick={triageFirstIncident} disabled={!activeRuns.length || busy.triage} type="button">Triage active incident</button>
            </article>

            <article className="overview-card mission-card">
              <header>
                <h2>Execution Snapshot</h2>
                <span>{activeRuns.length ? "Incident active" : "Stable"}</span>
              </header>
              <div className="signal-row"><span>Latest browser/API label</span><strong>{latestCheck?.label || "No active check"}</strong></div>
              <div className="signal-row"><span>Story progress</span><strong>{storyReport ? `${storyReport.completed_stories}/${storyReport.total_stories}` : "0/0"}</strong></div>
              <div className="signal-row"><span>Workspace context</span><strong>{environmentSummary?.workspace_ready ? "Ready" : "Pending"}</strong></div>
              <div className="signal-row"><span>Planner priorities</span><strong>{plannerTopStories.length}</strong></div>
            </article>
          </section>

          <section className="handoff-strip planner-story-strip">
            <p className="ox-label">Planner priorities</p>
            <div className="planner-story-grid">
              {plannerTopStories.length ? plannerTopStories.map((story) => (
                <article className="planner-story-card" key={story.story_id}>
                  <header>
                    <strong>{story.title}</strong>
                    <span>{story.analysis?.execution_priority || "medium"}</span>
                  </header>
                  <p>{story.analysis?.reasoning || "Waiting for planner analysis."}</p>
                  <footer>
                    <em>{story.analysis?.assigned_agent || "planner"}</em>
                    <small>{Math.round((story.analysis?.confidence_score || 0) * 100)}% confidence</small>
                  </footer>
                </article>
              )) : (
                <p className="muted">No prioritized stories yet.</p>
              )}
            </div>
          </section>
        </>
      ) : null}

      {stageView === "evidence" ? (
        <>
          <section className="console-grid evidence-grid">
            <article className="overview-card">
              <header>
                <h2>Runtime Signals</h2>
                <span>{logs?.length || 0} logs</span>
              </header>
              <div className="signal-row"><span>Error logs</span><strong>{logSummary?.error_entries || 0}</strong></div>
              <div className="signal-row"><span>Warning logs</span><strong>{logSummary?.warning_entries || 0}</strong></div>
              <div className="signal-row"><span>Latest health</span><strong>{latestHealth?.status || "unknown"}</strong></div>
              <div className="signal-row"><span>Latest check</span><strong>{latestCheck?.status || "none"}</strong></div>
            </article>

            <article className="overview-card">
              <header>
                <h2>Metric Signals</h2>
                <span>{metricSummary?.total_points || 0} points</span>
              </header>
              {latestMetricEntries.length ? latestMetricEntries.map(([name, value]) => (
                <div className="signal-row" key={name}>
                  <span>{name}</span>
                  <strong>{String(value)}</strong>
                </div>
              )) : (
                <p className="muted">No metric points yet. Connect sample metrics from the evidence panel.</p>
              )}
              <div className="signal-row">
                <span>Degraded metrics</span>
                <strong>{metricSummary?.degraded_metrics?.length || 0}</strong>
              </div>
            </article>

            <article className="overview-card">
              <header>
                <h2>Incident Evidence</h2>
                <span>{activeRuns.length} active</span>
              </header>
              {activeRuns.length ? activeRuns.slice(0, 4).map((run) => (
                <button className="signal-row signal-button" key={run.run_id} onClick={() => setDetailPanel({
                  title: "Incident run detail",
                  subtitle: "Current incident response context",
                  groups: [{
                    id: run.run_id,
                    title: run.trigger_reason || run.task_id || "Incident run",
                    rows: [
                      ["Status", run.status || "unknown"],
                      ["Run ID", run.run_id],
                      ["Session", run.session_id || "n/a"],
                      ["Task", run.task_id || "n/a"],
                      ["Source", run.source || "n/a"],
                    ],
                  }],
                })} type="button">
                  <span>{run.status}</span>
                  <strong>{run.trigger_reason || run.task_id || "Incident run"}</strong>
                </button>
              )) : (
                <p className="muted">No open incidents right now.</p>
              )}
            </article>
          </section>

          <section className="handoff-strip">
            <p className="ox-label">Coordination chain</p>
            <div className="handoff-chain">
              {latestHandoffItems.map((entry, index) => {
                const to = roleMeta(entry.to_role);
                return (
                  <div className="handoff-node" key={`${entry.entry_id || index}`}>
                    <span style={{ borderColor: to.color, color: to.color }}>{to.emoji}</span>
                    <small>{to.name}</small>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="feed-container">
            <div className="feed-header">
              <p className="ox-label">Agent reasoning + handoff feed</p>
              <span className="live-chip"><i />Live</span>
            </div>
            <div className="feed-messages">
              {latestConversationItems.map((messageItem) => {
                const sender = roleMeta(messageItem.sender_role);
                const recipient = messageItem.recipient_role ? roleMeta(messageItem.recipient_role) : null;
                return (
                  <article className="feed-msg" key={messageItem.message_id}>
                    <span className="msg-avatar" style={{ borderColor: sender.color, background: `${sender.color}22` }}>{sender.emoji}</span>
                    <div>
                      <header>
                        <strong style={{ color: sender.color }}>{sender.name}</strong>
                        {recipient ? <><span>{"->"}</span><em>{recipient.name}</em></> : null}
                        <time>{formatTime(messageItem.timestamp)}</time>
                      </header>
                      <p>{messageItem.content}</p>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="overview-card">
            <header>
              <h2>Recent Evidence Events</h2>
              <span>{recentEvidenceEvents.length}</span>
            </header>
            {recentEvidenceEvents.length ? recentEvidenceEvents.map((event) => (
              <button className="signal-row signal-button" key={event.event_id} onClick={() => setDetailPanel({
                title: "Evidence event detail",
                subtitle: "Recent event emitted by the project workflow",
                groups: [{
                  id: event.event_id,
                  title: event.title,
                  rows: [
                    ["Severity", event.severity || "info"],
                    ["Time", formatTime(event.timestamp)],
                    ["Type", event.event_type || "event"],
                    ["Event ID", event.event_id],
                  ],
                }],
              })} type="button">
                <span>{formatTime(event.timestamp)}</span>
                <strong>{event.title}</strong>
              </button>
            )) : (
              <p className="muted">No recent project events yet.</p>
            )}
          </section>
        </>
      ) : null}

      {stageView === "training" ? (
        <>
          <section className="console-grid training-summary-grid">
            <article className="overview-card">
              <header>
                <h2>Training Coverage</h2>
                <span>{hasTrainingData ? "Active" : "Idle"}</span>
              </header>
              <div className="signal-row"><span>Best-covered agent</span><strong>{strongestTrainingCard?.label || "None yet"}</strong></div>
              <div className="signal-row"><span>Most confident signal</span><strong>{highestSignalTrainingCard?.label || "None yet"}</strong></div>
              <div className="signal-row"><span>Datasets live</span><strong>{trainingCards.filter((item) => item.total > 0).length}/7</strong></div>
              <div className="signal-row"><span>Total records</span><strong>{trainingCards.reduce((sum, item) => sum + item.total, 0)}</strong></div>
            </article>

            <article className="overview-card">
              <header>
                <h2>What Dataset Means</h2>
                <span>Guide</span>
              </header>
              <p className="muted">
                A dataset here is structured history from real project runs: what an agent planned, what actually executed, and whether the outcome matched the decision.
              </p>
            </article>
          </section>

          <section className="overview-card training-card">
            <header>
              <h2>Agent Training Lab</h2>
              <span>{hasTrainingData ? "Live datasets" : "Waiting for evidence"}</span>
            </header>
            {hasTrainingData ? (
              <div className="training-grid">
                {trainingCards.map((item) => (
                  <button className="training-mini-card training-button" key={item.key} onClick={() => setDetailPanel(trainingDetailMap[item.key])} type="button">
                    <div className="training-mini-top">
                      <strong>{item.label}</strong>
                      <span>{item.total} records</span>
                    </div>
                    <div className="training-mini-metric">
                      <em>{item.metricLabel}</em>
                      <strong>{item.metricValue}</strong>
                    </div>
                    <p>{item.secondary}</p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted">Run stories, checks, triage, and release gates to accumulate training/evaluation records for each agent.</p>
            )}
          </section>
        </>
      ) : null}

      {detailPanel ? (
        <section className="detail-overlay" onClick={() => setDetailPanel(null)}>
          <div className="detail-modal" onClick={(event) => event.stopPropagation()}>
            <header className="detail-header">
              <div>
                <p className="ox-label">Inspection</p>
                <h2>{detailPanel.title}</h2>
                <p className="muted">{detailPanel.subtitle}</p>
              </div>
              <button className="detail-close" onClick={() => setDetailPanel(null)} type="button">Close</button>
            </header>
            <div className="detail-body">
              {detailPanel.groups?.length ? detailPanel.groups.map((group) => (
                <article className="detail-group" key={group.id}>
                  <strong>{group.title}</strong>
                  <div className="detail-rows">
                    {group.rows?.map(([label, value]) => (
                      <div className="detail-row" key={`${group.id}-${label}`}>
                        <span>{label}</span>
                        <em>{value}</em>
                      </div>
                    ))}
                  </div>
                </article>
              )) : (
                <p className="muted">No records captured yet for this view.</p>
              )}
            </div>
          </div>
        </section>
      ) : null}
    </main>
  );
}
