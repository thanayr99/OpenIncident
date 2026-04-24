import { useState } from "react";
import { roleMeta } from "../data/agents";
import { formatPercent } from "../utils/format";
import { OperationsWorkbench } from "./OperationsWorkbench";

function getAgentTrainingView(role, trainingDatasets) {
  if (role === "test_env_guardian") {
    const guardianDataset = trainingDatasets?.guardian;
    if (guardianDataset?.total_decisions) {
      return {
        title: "Guardian gate history",
        dataset: guardianDataset,
        lines: (dataset) => [
          `${dataset?.total_decisions || 0} gate decisions`,
          `Healthy ready ${formatPercent(dataset?.healthy_ready_rate || 0)}`,
          `${dataset?.blocked_decisions || 0} blocked releases`,
        ],
      };
    }
    return {
      title: "Observability evidence",
      dataset: trainingDatasets?.observability,
      lines: (dataset) => [
        `${dataset?.total_records || 0} check records`,
        `Incident link ${formatPercent(dataset?.incident_link_rate || 0)}`,
        `${dataset?.records_with_log_errors || 0} records with log errors`,
      ],
    };
  }

  const datasetMap = {
    planner: {
      title: "Planner decisions",
      dataset: trainingDatasets?.planner,
      lines: (dataset) => [
        `${dataset?.analyzed_records || 0}/${dataset?.total_records || 0} stories analyzed`,
        `Route match ${formatPercent(dataset?.route_match_rate || 0)}`,
        `${dataset?.completed_records || 0} completed, ${dataset?.failed_records || 0} failed`,
      ],
    },
    frontend_tester: {
      title: "Frontend eval set",
      dataset: trainingDatasets?.frontend,
      lines: (dataset) => [
        `${dataset?.planned_records || 0} planned browser cases`,
        `Route hints ${formatPercent(dataset?.route_hint_match_rate || 0)}`,
        `Selector coverage ${formatPercent(dataset?.selector_coverage_rate || 0)}`,
      ],
    },
    api_tester: {
      title: "API eval set",
      dataset: trainingDatasets?.api,
      lines: (dataset) => [
        `${dataset?.planned_records || 0} planned endpoint cases`,
        `Status match ${formatPercent(dataset?.status_match_rate || 0)}`,
        `Explicit hints ${formatPercent(dataset?.explicit_hint_rate || 0)}`,
      ],
    },
    reliability_analyst: {
      title: "Reliability signals",
      dataset: trainingDatasets?.triage,
      lines: (dataset) => [
        `${dataset?.total_triages || 0} triage records`,
        `Avg confidence ${formatPercent(dataset?.average_confidence || 0)}`,
        `Root-cause confirmed ${formatPercent(dataset?.root_cause_confirmed_rate || 0)}`,
      ],
    },
    oversight: {
      title: "Oversight audits",
      dataset: trainingDatasets?.oversight,
      lines: (dataset) => [
        `${dataset?.total_audits || 0} audits logged`,
        `Resolved run audits ${formatPercent(dataset?.resolved_run_audit_rate || 0)}`,
        `${dataset?.story_linked_audits || 0} story-linked reviews`,
      ],
    },
  };

  if (role === "database_analyst") {
    return {
      title: "Database proxy signals",
      dataset: trainingDatasets?.api,
      lines: (dataset) => [
        `${dataset?.planned_records || 0} API/data cases`,
        `Status match ${formatPercent(dataset?.status_match_rate || 0)}`,
        "Dedicated DB dataset comes next",
      ],
    };
  }

  if (role === "observability") {
    return {
      title: "Observability evidence",
      dataset: trainingDatasets?.observability,
      lines: (dataset) => [
        `${dataset?.total_records || 0} check records`,
        `Incident link ${formatPercent(dataset?.incident_link_rate || 0)}`,
        `${dataset?.records_with_log_errors || 0} records with log errors`,
      ],
    };
  }

  return datasetMap[role] || null;
}

export function RightPanel({
  selectedAgent,
  storyForm,
  setStoryForm,
  createAnalyzeExecuteStory,
  selectedProject,
  busy,
  frontendDiscovery,
  latestStory,
  stories,
  logs,
  logSummary,
  logConnectorForm,
  setLogConnectorForm,
  bulkStoryInput,
  setBulkStoryInput,
  bulkLogInput,
  setBulkLogInput,
  importBulkStories,
  ingestBulkLogs,
  saveLogConnector,
  pullConnectedLogs,
  projectSummary,
  plannerSummary,
  environmentSummary,
  trainingDatasets,
  message,
  applyStoryTemplate,
  ingestSampleMetrics,
}) {
  const selectedMeta = roleMeta(selectedAgent?.role);
  const selectedTraining = getAgentTrainingView(selectedAgent?.role, trainingDatasets);
  const [panelTab, setPanelTab] = useState("inspect");

  return (
    <aside className="ox-right">
      <section className="panel-tabs">
        <button className={panelTab === "inspect" ? "active" : ""} onClick={() => setPanelTab("inspect")} type="button">Inspect</button>
        <button className={panelTab === "operate" ? "active" : ""} onClick={() => setPanelTab("operate")} type="button">Operate</button>
        <button className={panelTab === "evidence" ? "active" : ""} onClick={() => setPanelTab("evidence")} type="button">Evidence</button>
      </section>

      <section className="active-spotlight">
        <p className="ox-label">Selected agent</p>
        <div className="spotlight-avatar" style={{ borderColor: selectedMeta.color, background: `${selectedMeta.color}20` }}>{selectedMeta.emoji}</div>
        <h2>{selectedAgent?.display_name || selectedMeta.name}</h2>
        <p>{selectedAgent?.specialization || selectedMeta.role}</p>
        <div className="task-block">
          <span>Maturity</span>
          <strong>{String(selectedAgent?.maturity || "bootstrap").toUpperCase()}</strong>
        </div>
        <div className="task-block">
          <span>Trust</span>
          <strong>{formatPercent(selectedAgent?.trust_score)}</strong>
        </div>
        <div className="reasoning-block" style={{ borderColor: selectedMeta.color }}>
          {(selectedAgent?.notes || []).slice(0, 3).map((note) => <p key={note}>{note}</p>)}
          {!selectedAgent?.notes?.length ? <p>Standing by for the next workflow signal.</p> : null}
        </div>
      </section>

      {panelTab === "inspect" ? (
        <>
          <section className="ox-panel">
            <p className="ox-label">Planner intelligence</p>
            {plannerSummary ? (
              <div className="route-list">
                <strong>{plannerSummary.analyzed_stories}/{plannerSummary.total_stories} stories analyzed</strong>
                {(plannerSummary.next_recommended_actions || []).slice(0, 4).map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            ) : (
              <p className="muted">Planner summary appears after story analysis.</p>
            )}
          </section>

          <section className="ox-panel">
            <p className="ox-label">Environment agent</p>
            {environmentSummary ? (
              <div className="route-list">
                <strong>{environmentSummary.framework || "Framework pending"}</strong>
                <span>Workspace: {environmentSummary.workspace_ready ? "ready" : "not ready"}</span>
                <span>App root: {environmentSummary.app_root || environmentSummary.recommended_workdir || "not inferred"}</span>
                <span>Routes detected: {environmentSummary.route_count || 0}</span>
                {(environmentSummary.next_actions || []).slice(0, 3).map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            ) : (
              <p className="muted">Environment summary appears after repository setup begins.</p>
            )}
          </section>

          <section className="ox-panel">
            <p className="ox-label">Selected agent training</p>
            {selectedTraining?.dataset ? (
              <div className="route-list training-panel-list">
                <strong>{selectedTraining.title}</strong>
                {selectedTraining.lines(selectedTraining.dataset).map((line) => (
                  <span key={line}>{line}</span>
                ))}
              </div>
            ) : (
              <p className="muted">Training metrics for this agent will appear once the related datasets start collecting records.</p>
            )}
          </section>
        </>
      ) : null}

      {panelTab === "operate" ? (
        <>
          <section className="ox-panel">
            <p className="ox-label">Automated story validation</p>
            <form className="ox-form" onSubmit={createAnalyzeExecuteStory}>
              <div className="template-strip">
                <button type="button" className="template-chip" onClick={() => applyStoryTemplate("auth")}>Auth login</button>
                <button type="button" className="template-chip" onClick={() => applyStoryTemplate("api")}>API health</button>
                <button type="button" className="template-chip" onClick={() => applyStoryTemplate("frontend")}>Frontend render</button>
              </div>
              <input placeholder="Story title" value={storyForm.title} onChange={(event) => setStoryForm((current) => ({ ...current, title: event.target.value }))} />
              <textarea placeholder="Story description" value={storyForm.description} onChange={(event) => setStoryForm((current) => ({ ...current, description: event.target.value }))} />
              <textarea placeholder="Acceptance criteria, one per line" value={storyForm.acceptance_criteria} onChange={(event) => setStoryForm((current) => ({ ...current, acceptance_criteria: event.target.value }))} />
              <input placeholder="Tags, comma separated" value={storyForm.tags} onChange={(event) => setStoryForm((current) => ({ ...current, tags: event.target.value }))} />
              <button disabled={!selectedProject || busy.story} type="submit">{busy.story ? "Validating..." : "Create + analyze + execute"}</button>
            </form>
          </section>

          <OperationsWorkbench
            selectedProject={selectedProject}
            bulkStoryInput={bulkStoryInput}
            setBulkStoryInput={setBulkStoryInput}
            bulkLogInput={bulkLogInput}
            setBulkLogInput={setBulkLogInput}
            importBulkStories={importBulkStories}
            ingestBulkLogs={ingestBulkLogs}
            logConnectorForm={logConnectorForm}
            setLogConnectorForm={setLogConnectorForm}
            saveLogConnector={saveLogConnector}
            pullConnectedLogs={pullConnectedLogs}
            projectSummary={projectSummary}
            stories={stories}
            logs={logs}
            logSummary={logSummary}
            ingestSampleMetrics={ingestSampleMetrics}
            busy={busy}
          />
        </>
      ) : null}

      {panelTab === "evidence" ? (
        <>
          <section className="ox-panel">
            <p className="ox-label">Frontend discovery</p>
            {frontendDiscovery ? (
              <div className="route-list">
                <strong>{frontendDiscovery.framework || "Unknown framework"}</strong>
                {frontendDiscovery.routes.slice(0, 7).map((route) => (
                  <span key={`${route.source_path}-${route.route}`}>{route.route} <em>{route.source_path}</em></span>
                ))}
              </div>
            ) : (
              <p className="muted">Pull workspace, then discover frontend.</p>
            )}
          </section>

          <section className="ox-panel">
            <p className="ox-label">Latest story result</p>
            {latestStory ? (
              <div className="route-list">
                <strong>{latestStory.result.status}</strong>
                <span>Route: {latestStory.plan.inferred_route || "not inferred"}</span>
                <span>Selector: {latestStory.plan.expected_selector || "none"}</span>
                <span>{latestStory.result.summary}</span>
              </div>
            ) : (
              <p className="muted">No story executed in this session.</p>
            )}
          </section>

          <section className="ox-panel">
            <p className="ox-label">Project evidence</p>
            <div className="route-list">
              <strong>{stories.length} stories, {logs.length} logs</strong>
              <span>{logSummary?.error_entries || 0} error logs, {logSummary?.warning_entries || 0} warnings</span>
              <span>{projectSummary?.active_runs?.length || 0} active incidents</span>
            </div>
          </section>

          <section className="ox-panel">
            <p className="ox-label">Metric evidence</p>
            <div className="route-list">
              <strong>{projectSummary?.metric_summary?.total_points || 0} metric points</strong>
              <span>Latest values: {Object.keys(projectSummary?.metric_summary?.latest_values || {}).length}</span>
              <span>Degraded metrics: {(projectSummary?.metric_summary?.degraded_metrics || []).length}</span>
              {(projectSummary?.metric_summary?.degraded_metrics || []).slice(0, 3).map((metric) => (
                <span key={metric}>{metric}</span>
              ))}
            </div>
            <button
              disabled={!selectedProject || busy.metrics}
              onClick={ingestSampleMetrics}
              type="button"
            >
              {busy.metrics ? "Connecting..." : "Connect sample metrics"}
            </button>
          </section>
        </>
      ) : null}

      <div className="command-message">{message}</div>
    </aside>
  );
}
