const state = {
  projects: [],
  selectedProjectId: null,
  selectedRunId: null,
  selectedSessionId: null,
  selectedStoryId: null,
  latestCheck: null,
  checks: [],
  runs: [],
  stories: [],
  storyReport: null,
  logSummary: null,
  triage: null,
  runState: null,
  storyCodeContext: null,
};

const projectForm = document.getElementById("project-form");
const projectMessage = document.getElementById("project-message");
const projectSelect = document.getElementById("project-select");
const refreshProjectsButton = document.getElementById("refresh-projects");
const enableTriggerButton = document.getElementById("enable-trigger");
const projectSummary = document.getElementById("selected-project-summary");
const checkMessage = document.getElementById("check-message");
const latestCheckPanel = document.getElementById("latest-check");
const runsList = document.getElementById("runs-list");
const runStatePanel = document.getElementById("run-state");
const triageOutput = document.getElementById("triage-output");
const apiStatusDot = document.getElementById("api-status-dot");
const apiStatusText = document.getElementById("api-status-text");
const browserCheckForm = document.getElementById("browser-check-form");
const apiCheckForm = document.getElementById("api-check-form");
const runHealthButton = document.getElementById("run-health");
const signalGrid = document.getElementById("signal-grid");
const summaryProjects = document.getElementById("summary-projects");
const summaryIncidents = document.getElementById("summary-incidents");
const summaryStoryProgress = document.getElementById("summary-story-progress");
const summarySignal = document.getElementById("summary-signal");
const storyForm = document.getElementById("story-form");
const storyMessage = document.getElementById("story-message");
const storyReportPanel = document.getElementById("story-report");
const storiesList = document.getElementById("stories-list");
const storyDetailPanel = document.getElementById("story-detail");
const logForm = document.getElementById("log-form");
const logMessage = document.getElementById("log-message");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function toTitleCase(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function toneForStatus(status) {
  const lowered = String(status || "").toLowerCase();
  if (["healthy", "completed", "resolved", "ok"].includes(lowered)) return "ok";
  if (["investigating", "pending", "analyzed", "running", "warning", "blocked"].includes(lowered)) return "warning";
  if (["failed", "unhealthy", "unreachable", "error", "tooling_error"].includes(lowered)) return "error";
  return "neutral";
}

function formatMetricValue(value) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (value == null || value === "") return "Not available";
  return String(value);
}

function formatDate(value) {
  if (!value) return "Not available";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function getSelectedProject() {
  return state.projects.find((project) => project.project_id === state.selectedProjectId) || null;
}

function getSelectedStory() {
  return state.stories.find((story) => story.story_id === state.selectedStoryId) || null;
}

function renderEmpty(element, message) {
  element.className = "data-panel empty-state";
  element.innerHTML = `<p>${escapeHtml(message)}</p>`;
}

function renderKeyValueRows(entries) {
  return entries
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(
      ([label, value]) => `
        <div class="kv-row">
          <span class="kv-label">${escapeHtml(label)}</span>
          <span class="kv-value">${escapeHtml(value)}</span>
        </div>
      `,
    )
    .join("");
}

function renderListSection(title, items, emptyMessage = "Nothing captured yet.") {
  const safeItems = Array.isArray(items) ? items.filter(Boolean) : [];
  return `
    <section class="detail-block">
      <h3>${escapeHtml(title)}</h3>
      ${
        safeItems.length
          ? `<ul class="bullet-list">${safeItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : `<p class="muted">${escapeHtml(emptyMessage)}</p>`
      }
    </section>
  `;
}

function setFeedback(element, message, mode = "") {
  element.textContent = message;
  element.className = `feedback ${mode}`.trim();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const detail = typeof data === "object" && data?.detail ? data.detail : text;
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  return data;
}

async function withButtonLock(button, work) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Working...";
  try {
    return await work();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function ensureProjectMonitor(project) {
  if (!project?.base_url) return;
  await api(`/projects/${project.project_id}/monitor`, {
    method: "PUT",
    body: JSON.stringify({
      base_url: project.base_url,
      healthcheck_path: project.healthcheck_path || "/health",
      expected_status: 200,
      timeout_seconds: 10,
      enabled: true,
      headers: {},
    }),
  });
}

function updateOverview() {
  summaryProjects.textContent = String(state.projects.length);
  summaryIncidents.textContent = String(state.runs.filter((run) => run.status !== "resolved").length);
  const progress = state.storyReport?.progress_percent ?? 0;
  summaryStoryProgress.textContent = `${Math.round(progress)}%`;

  const latestSignal =
    state.latestCheck?.status ||
    state.storyReport?.total_stories
      ? state.latestCheck?.status || `${state.storyReport.completed_stories}/${state.storyReport.total_stories} stories`
      : "Waiting";
  summarySignal.textContent = toTitleCase(latestSignal);
}

function renderSelectedProjectSummary() {
  const project = getSelectedProject();
  if (!project) {
    projectSummary.textContent = "Create or select a project to begin.";
    return;
  }
  projectSummary.textContent = `${project.name} is connected to ${project.base_url || "no base URL"} and will use ${project.healthcheck_path || "/health"} for health checks.`;
}

function renderLatestCheck() {
  const data = state.latestCheck;
  if (!data) {
    renderEmpty(latestCheckPanel, "Run a health, browser, or API check to see the latest validation summary.");
    return;
  }

  latestCheckPanel.className = "data-panel";
  latestCheckPanel.innerHTML = `
    <div class="panel-stack">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Latest Signal</p>
          <h3>${escapeHtml(data.label || `${toTitleCase(data.check_type)} check`)}</h3>
        </div>
        <span class="status-pill ${toneForStatus(data.status)}">${escapeHtml(toTitleCase(data.status || "unknown"))}</span>
      </div>
      <div class="detail-grid">
        <section class="detail-block">
          <h3>Observation</h3>
          <div class="kv-list">
            ${renderKeyValueRows([
              ["Check type", toTitleCase(data.check_type)],
              ["Target URL", data.target_url],
              ["Observed URL", data.observed_url],
              ["Page title", data.page_title],
              ["Engine", data.engine],
            ])}
          </div>
        </section>
        <section class="detail-block">
          <h3>Response</h3>
          <div class="kv-list">
            ${renderKeyValueRows([
              ["Status code", data.status_code],
              ["Response time (ms)", data.response_time_ms],
              ["Checked at", formatDate(data.checked_at)],
              ["Error", data.error_message],
            ])}
          </div>
        </section>
      </div>
      <section class="detail-block">
        <h3>Excerpt</h3>
        <div class="excerpt-box">${escapeHtml(data.response_excerpt || "No excerpt captured.")}</div>
      </section>
    </div>
  `;
}

function renderSignalGrid() {
  const project = getSelectedProject();
  if (!project) {
    signalGrid.innerHTML = '<div class="signal-card muted-card">Select a project to see health, validation, logs, stories, and incidents.</div>';
    return;
  }

  const latestByType = {};
  for (const check of state.checks) {
    latestByType[check.check_type] = check;
  }

  const signalCards = [
    {
      title: "Browser",
      status: latestByType.browser?.status || "waiting",
      detail: latestByType.browser?.label || "No browser check yet",
      meta: latestByType.browser?.error_message || latestByType.browser?.page_title || "Rendered flow status appears here",
    },
    {
      title: "API",
      status: latestByType.api?.status || "waiting",
      detail: latestByType.api?.label || "No API check yet",
      meta: latestByType.api?.error_message || latestByType.api?.target_url || "Endpoint validation appears here",
    },
    {
      title: "Health",
      status: latestByType.health?.status || "waiting",
      detail: latestByType.health?.target_url || `${project.base_url || "No base URL"}${project.healthcheck_path || "/health"}`,
      meta: latestByType.health?.error_message || "Service heartbeat status appears here",
    },
    {
      title: "Logs",
      status: state.logSummary?.error_entries ? "warning" : state.logSummary?.total_entries ? "healthy" : "waiting",
      detail: state.logSummary?.total_entries ? `${state.logSummary.total_entries} log entries loaded` : "No logs yet",
      meta: state.logSummary?.latest_errors?.[0] || "Runtime evidence appears here",
    },
    {
      title: "Stories",
      status: state.storyReport?.failed_stories ? "warning" : state.storyReport?.completed_stories ? "healthy" : "waiting",
      detail: state.storyReport?.total_stories ? `${state.storyReport.completed_stories}/${state.storyReport.total_stories} completed` : "No stories yet",
      meta: state.storyReport?.failed_stories ? `${state.storyReport.failed_stories} stories failing or incomplete` : "Story validation progress appears here",
    },
    {
      title: "Incidents",
      status: state.runs.some((run) => run.status !== "resolved") ? "error" : "healthy",
      detail: state.runs.some((run) => run.status !== "resolved")
        ? `${state.runs.filter((run) => run.status !== "resolved").length} active incident(s)`
        : "No open incidents",
      meta: state.runs[0]?.trigger_reason || "Incident pressure appears here",
    },
  ];

  signalGrid.innerHTML = signalCards
    .map(
      (card) => `
        <article class="signal-card">
          <div class="signal-card-head">
            <h3>${escapeHtml(card.title)}</h3>
            <span class="status-pill ${toneForStatus(card.status)}">${escapeHtml(toTitleCase(card.status))}</span>
          </div>
          <p class="signal-detail">${escapeHtml(card.detail)}</p>
          <p class="muted">${escapeHtml(card.meta)}</p>
        </article>
      `,
    )
    .join("");
}

function renderStoryReport() {
  if (!state.storyReport) {
    storyReportPanel.innerHTML = '<div class="muted-card">No story report yet for this project.</div>';
    return;
  }

  const report = state.storyReport;
  storyReportPanel.innerHTML = `
    <article class="report-stat">
      <span class="summary-label">Total Stories</span>
      <strong class="summary-value">${escapeHtml(report.total_stories)}</strong>
    </article>
    <article class="report-stat">
      <span class="summary-label">Completed</span>
      <strong class="summary-value">${escapeHtml(report.completed_stories)}</strong>
    </article>
    <article class="report-stat">
      <span class="summary-label">Failed</span>
      <strong class="summary-value">${escapeHtml(report.failed_stories)}</strong>
    </article>
    <article class="report-stat">
      <span class="summary-label">Blocked</span>
      <strong class="summary-value">${escapeHtml(report.blocked_stories)}</strong>
    </article>
    <article class="report-stat wide">
      <span class="summary-label">Project Progress</span>
      <strong class="summary-value">${escapeHtml(Math.round(report.progress_percent))}%</strong>
      <p class="muted">Generated ${escapeHtml(formatDate(report.generated_at))}</p>
    </article>
  `;
}

function attachStoryListEvents() {
  storiesList.querySelectorAll(".story-open").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedStoryId = button.dataset.story;
      state.storyCodeContext = null;
      renderStoryDetail();
    });
  });

  storiesList.querySelectorAll(".story-analyze").forEach((button) => {
    button.addEventListener("click", async () => {
      await withButtonLock(button, async () => {
        try {
          await api(`/stories/${button.dataset.story}/analyze`, { method: "POST" });
          setFeedback(storyMessage, "Story analyzed successfully.", "ok");
          await refreshSelectedProjectData();
          state.selectedStoryId = button.dataset.story;
          renderStoryDetail();
        } catch (error) {
          setFeedback(storyMessage, error.message, "error");
        }
      });
    });
  });

  storiesList.querySelectorAll(".story-execute").forEach((button) => {
    button.addEventListener("click", async () => {
      await withButtonLock(button, async () => {
        try {
          const result = await api(`/stories/${button.dataset.story}/execute`, { method: "POST" });
          setFeedback(
            storyMessage,
            `Story execution finished with status "${result.status}".`,
            result.success ? "ok" : result.status === "blocked" ? "warning" : "error",
          );
          await refreshSelectedProjectData();
          state.selectedStoryId = button.dataset.story;
          if (result.linked_run_id) {
            state.selectedRunId = result.linked_run_id;
            state.selectedSessionId = result.linked_session_id;
            await loadSelectedRunState();
          }
          renderStoryDetail();
        } catch (error) {
          setFeedback(storyMessage, error.message, "error");
        }
      });
    });
  });

  storiesList.querySelectorAll(".story-code").forEach((button) => {
    button.addEventListener("click", async () => {
      await withButtonLock(button, async () => {
        try {
          state.selectedStoryId = button.dataset.story;
          state.storyCodeContext = await api(`/stories/${button.dataset.story}/code-context`);
          renderStoryDetail();
          setFeedback(storyMessage, "Loaded repository context for the selected story.", "ok");
        } catch (error) {
          setFeedback(storyMessage, error.message, "error");
        }
      });
    });
  });
}

function renderStoriesList() {
  if (!state.stories.length) {
    storiesList.innerHTML = '<p class="muted">No stories yet for this project.</p>';
    return;
  }

  storiesList.innerHTML = state.stories
    .map((story) => {
      const isSelected = story.story_id === state.selectedStoryId;
      const result = story.latest_result;
      return `
        <article class="story-card ${isSelected ? "selected" : ""}">
          <div class="story-card-head">
            <div>
              <h3>${escapeHtml(story.title)}</h3>
              <p class="muted">${escapeHtml(story.description)}</p>
            </div>
            <span class="status-pill ${toneForStatus(story.status)}">${escapeHtml(toTitleCase(story.status))}</span>
          </div>
          <div class="run-meta">
            <span class="pill">${escapeHtml(toTitleCase(story.analysis?.primary_domain || "pending"))}</span>
            <span class="pill">${escapeHtml(toTitleCase(story.analysis?.assigned_agent || "planner"))}</span>
            <span class="pill">${escapeHtml(toTitleCase(result?.test_type || "none"))}</span>
          </div>
          <p class="story-summary">${escapeHtml(result?.summary || story.analysis?.reasoning || "Waiting for analysis or execution.")}</p>
          <div class="inline-actions">
            <button type="button" class="secondary story-open" data-story="${story.story_id}">View</button>
            <button type="button" class="secondary story-analyze" data-story="${story.story_id}">Analyze</button>
            <button type="button" class="story-execute" data-story="${story.story_id}">Execute</button>
            <button type="button" class="secondary story-code" data-story="${story.story_id}">Code context</button>
          </div>
        </article>
      `;
    })
    .join("");

  attachStoryListEvents();
}

function renderRunList() {
  const openRuns = state.runs.filter((run) => run.status !== "resolved");
  if (!openRuns.length) {
    runsList.innerHTML = '<p class="muted">No active incidents for this project.</p>';
    return;
  }

  runsList.innerHTML = openRuns
    .slice()
    .reverse()
    .map(
      (run) => `
        <article class="run-item ${run.run_id === state.selectedRunId ? "selected" : ""}">
          <div class="run-item-head">
            <div>
              <h3>${escapeHtml(run.project?.name || run.task_id || "Incident")}</h3>
              <p class="muted">${escapeHtml(run.trigger_reason || "Manual run")}</p>
            </div>
            <span class="status-pill ${toneForStatus(run.status)}">${escapeHtml(toTitleCase(run.status))}</span>
          </div>
          <div class="run-meta">
            <span class="pill">${escapeHtml(toTitleCase(run.source || "manual"))}</span>
            <span class="pill">${escapeHtml(run.source_check_type ? toTitleCase(run.source_check_type) : "Incident")}</span>
            <span class="pill">${escapeHtml(run.run_id.slice(0, 8))}</span>
          </div>
          <div class="inline-actions">
            <button type="button" class="secondary run-open" data-run="${run.run_id}" data-session="${run.session_id}">View incident</button>
            <button type="button" class="run-triage" data-run="${run.run_id}" data-session="${run.session_id}">Triage run</button>
          </div>
        </article>
      `,
    )
    .join("");

  runsList.querySelectorAll(".run-open").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedRunId = button.dataset.run;
      state.selectedSessionId = button.dataset.session;
      await loadSelectedRunState();
    });
  });

  runsList.querySelectorAll(".run-triage").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedRunId = button.dataset.run;
      state.selectedSessionId = button.dataset.session;
      await loadSelectedRunState();
      await loadTriage();
    });
  });
}

function renderRunState() {
  const data = state.runState;
  if (!data) {
    renderEmpty(runStatePanel, "Select an incident to see what OpenIncident knows so far.");
    return;
  }

  const metrics = Object.entries(data.metrics || {});
  runStatePanel.className = "data-panel";
  runStatePanel.innerHTML = `
    <div class="panel-stack">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Incident Summary</p>
          <h3>${escapeHtml(data.incident_summary || "Incident details")}</h3>
        </div>
        <span class="status-pill ${toneForStatus(data.current_status)}">${escapeHtml(toTitleCase(data.current_status || "unknown"))}</span>
      </div>

      <div class="detail-grid">
        <section class="detail-block">
          <h3>Overview</h3>
          <div class="kv-list">
            ${renderKeyValueRows([
              ["Incident ID", data.incident_id],
              ["Project or service", data.service_name],
              ["Severity", data.severity],
              ["User impact", data.user_impact],
              ["Last error", data.last_action_error],
            ])}
          </div>
        </section>
        <section class="detail-block">
          <h3>Progress</h3>
          <div class="kv-list">
            ${renderKeyValueRows([
              ["Steps taken", `${data.steps_taken ?? 0} / ${data.max_steps ?? 0}`],
              ["Passed checks", data.passed_checks],
              ["Failed checks", data.failed_checks],
              ["Reliability score", data.reliability_score],
              ["Service restored", data.service_restored ? "Yes" : "No"],
            ])}
          </div>
        </section>
      </div>

      ${
        metrics.length
          ? `
            <section class="detail-block">
              <h3>Operational Metrics</h3>
              <div class="metric-grid">
                ${metrics
                  .map(
                    ([key, value]) => `
                      <div class="metric-card">
                        <span class="metric-label">${escapeHtml(toTitleCase(key))}</span>
                        <strong class="metric-value">${escapeHtml(formatMetricValue(value))}</strong>
                      </div>
                    `,
                  )
                  .join("")}
              </div>
            </section>
          `
          : ""
      }

      ${renderListSection("Logs", data.logs, "No logs have been attached yet.")}
      ${renderListSection("Investigation notes", data.investigation_notes, "No investigation notes yet.")}
      ${renderListSection("Available dashboards", data.available_dashboards, "No dashboards configured yet.")}
    </div>
  `;
}

function renderTriage() {
  const data = state.triage;
  if (!data) {
    renderEmpty(triageOutput, 'Select an incident and click "Triage run" to generate a diagnosis.');
    return;
  }

  const recommendations = Array.isArray(data.recommended_actions) ? data.recommended_actions : [];
  triageOutput.className = "data-panel";
  triageOutput.innerHTML = `
    <div class="panel-stack">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">AI Triage</p>
          <h3>${escapeHtml(data.summary || "No summary available")}</h3>
        </div>
        <span class="status-pill neutral">Confidence ${escapeHtml(Math.round((data.confidence || 0) * 100))}%</span>
      </div>
      <section class="detail-block">
        <h3>Suspected Root Cause</h3>
        <p>${escapeHtml(data.suspected_root_cause || "No root cause suggested yet.")}</p>
      </section>
      ${renderListSection("Evidence Used", data.evidence, "No evidence summary returned yet.")}
      <section class="detail-block">
        <h3>Recommended Actions</h3>
        ${
          recommendations.length
            ? `<div class="recommendation-list">
                ${recommendations
                  .map(
                    (item) => `
                      <article class="recommendation-card">
                        <div class="recommendation-head">
                          <span class="status-pill neutral">${escapeHtml(toTitleCase(item.action_type))}</span>
                        </div>
                        <p>${escapeHtml(item.rationale || "No rationale provided.")}</p>
                      </article>
                    `,
                  )
                  .join("")}
              </div>`
            : '<p class="muted">No next actions were suggested.</p>'
        }
      </section>
    </div>
  `;
}

function renderStoryDetail() {
  const story = getSelectedStory();
  if (!story) {
    renderEmpty(storyDetailPanel, "Select a story to inspect its analysis, execution result, and code context.");
    return;
  }

  const result = story.latest_result;
  const repoContext = state.storyCodeContext || result?.output?.repo_context || null;
  const logSummary = result?.output?.log_summary || null;
  storyDetailPanel.className = "data-panel";
  storyDetailPanel.innerHTML = `
    <div class="panel-stack">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Selected Story</p>
          <h3>${escapeHtml(story.title)}</h3>
        </div>
        <span class="status-pill ${toneForStatus(story.status)}">${escapeHtml(toTitleCase(story.status))}</span>
      </div>

      <section class="detail-block">
        <h3>Description</h3>
        <p>${escapeHtml(story.description)}</p>
      </section>

      <div class="detail-grid">
        <section class="detail-block">
          <h3>Planner Analysis</h3>
          <div class="kv-list">
            ${renderKeyValueRows([
              ["Primary domain", toTitleCase(story.analysis?.primary_domain || "pending")],
              ["Assigned agent", toTitleCase(story.analysis?.assigned_agent || "planner")],
              [
                "Suggested tests",
                (story.analysis?.suggested_test_types || []).map((item) => toTitleCase(item)).join(", "),
              ],
            ])}
          </div>
          <p class="muted top-gap">${escapeHtml(story.analysis?.reasoning || "This story has not been analyzed yet.")}</p>
        </section>
        <section class="detail-block">
          <h3>Latest Execution</h3>
          <div class="kv-list">
            ${renderKeyValueRows([
              ["Execution status", toTitleCase(result?.status || "pending")],
              ["Test type", toTitleCase(result?.test_type || "none")],
              ["Success", result ? (result.success ? "Yes" : "No") : "Not run"],
              ["Executed at", formatDate(result?.executed_at)],
              ["Linked incident", result?.linked_run_id ? result.linked_run_id.slice(0, 8) : null],
            ])}
          </div>
          <p class="muted top-gap">${escapeHtml(result?.summary || "Run this story to capture execution evidence.")}</p>
        </section>
      </div>

      ${renderListSection("Acceptance Criteria", story.acceptance_criteria, "No acceptance criteria captured.")}
      ${renderListSection("Execution Evidence", result?.evidence, "No execution evidence captured yet.")}

      ${
        logSummary
          ? `
            <section class="detail-block">
              <h3>Linked Log Summary</h3>
              <div class="kv-list">
                ${renderKeyValueRows([
                  ["Total entries", logSummary.total_entries],
                  ["Error entries", logSummary.error_entries],
                  ["Warning entries", logSummary.warning_entries],
                  ["Top signals", (logSummary.top_signals || []).join(", ")],
                ])}
              </div>
            </section>
          `
          : ""
      }

      ${
        repoContext
          ? `
            <section class="detail-block">
              <h3>Repository Context</h3>
              ${
                repoContext.matches?.length
                  ? repoContext.matches
                      .slice(0, 3)
                      .map(
                        (match) => `
                          <article class="code-match">
                            <div class="code-match-head">
                              <strong>${escapeHtml(match.path)}</strong>
                              <span class="pill">Score ${escapeHtml(formatMetricValue(match.score))}</span>
                            </div>
                            <p class="muted">${escapeHtml(match.reason)}</p>
                            <div class="excerpt-box">${escapeHtml(match.snippet || "No snippet available.")}</div>
                          </article>
                        `,
                      )
                      .join("")
                  : `<p class="muted">${escapeHtml(repoContext.error_message || "No repository matches found yet.")}</p>`
              }
            </section>
          `
          : ""
      }
    </div>
  `;
}

async function checkApiStatus() {
  try {
    const data = await api("/health");
    apiStatusDot.classList.add("ok");
    apiStatusDot.classList.remove("error");
    apiStatusText.textContent = data.status === "ok" ? "Healthy" : "Unexpected";
  } catch (error) {
    apiStatusDot.classList.add("error");
    apiStatusDot.classList.remove("ok");
    apiStatusText.textContent = `Unavailable: ${error.message}`;
  }
}

async function loadProjects() {
  state.projects = await api("/projects");
  projectSelect.innerHTML = "";

  if (!state.projects.length) {
    const option = document.createElement("option");
    option.textContent = "No projects yet";
    option.value = "";
    projectSelect.appendChild(option);
    state.selectedProjectId = null;
    state.selectedRunId = null;
    state.selectedSessionId = null;
    state.selectedStoryId = null;
    state.latestCheck = null;
    state.checks = [];
    state.runs = [];
    state.stories = [];
    state.storyReport = null;
    state.logSummary = null;
    state.runState = null;
    state.triage = null;
    state.storyCodeContext = null;
    renderSelectedProjectSummary();
    renderSignalGrid();
    renderLatestCheck();
    renderRunList();
    renderRunState();
    renderTriage();
    renderStoryReport();
    renderStoriesList();
    renderStoryDetail();
    updateOverview();
    return;
  }

  for (const project of state.projects) {
    const option = document.createElement("option");
    option.value = project.project_id;
    option.textContent = `${project.name} (${project.project_id.slice(0, 8)})`;
    projectSelect.appendChild(option);
  }

  if (!state.selectedProjectId || !state.projects.some((project) => project.project_id === state.selectedProjectId)) {
    state.selectedProjectId = state.projects[state.projects.length - 1].project_id;
  }

  projectSelect.value = state.selectedProjectId;
  renderSelectedProjectSummary();
  await refreshSelectedProjectData();
}

async function refreshSelectedProjectData() {
  if (!state.selectedProjectId) {
    updateOverview();
    return;
  }

  const project = getSelectedProject();
  const [checksResult, runsResult, storiesResult, reportResult, logsResult] = await Promise.allSettled([
    api(`/projects/${state.selectedProjectId}/checks`),
    api(`/runs?project_id=${encodeURIComponent(state.selectedProjectId)}`),
    api(`/projects/${state.selectedProjectId}/stories`),
    api(`/projects/${state.selectedProjectId}/story-report`),
    api(`/projects/${state.selectedProjectId}/logs/summary`),
  ]);

  state.checks = checksResult.status === "fulfilled" ? checksResult.value : [];
  state.runs = runsResult.status === "fulfilled" ? runsResult.value : [];
  state.stories = storiesResult.status === "fulfilled" ? storiesResult.value : [];
  state.storyReport = reportResult.status === "fulfilled" ? reportResult.value : null;
  state.logSummary = logsResult.status === "fulfilled" ? logsResult.value : null;

  state.latestCheck = state.checks.length ? state.checks[state.checks.length - 1] : null;

  if (!state.selectedStoryId || !state.stories.some((story) => story.story_id === state.selectedStoryId)) {
    state.selectedStoryId = state.stories[0]?.story_id || null;
    state.storyCodeContext = null;
  }

  if (!state.selectedRunId || !state.runs.some((run) => run.run_id === state.selectedRunId)) {
    const latestOpenRun = state.runs.find((run) => run.status !== "resolved");
    state.selectedRunId = latestOpenRun?.run_id || null;
    state.selectedSessionId = latestOpenRun?.session_id || null;
    state.runState = null;
    state.triage = null;
  }

  renderSelectedProjectSummary(project);
  renderSignalGrid();
  renderLatestCheck();
  renderStoryReport();
  renderStoriesList();
  renderRunList();
  renderStoryDetail();
  updateOverview();

  if (state.selectedSessionId) {
    await loadSelectedRunState();
  } else {
    renderRunState();
    renderTriage();
  }
}

async function loadSelectedRunState() {
  if (!state.selectedSessionId) {
    state.runState = null;
    renderRunState();
    return;
  }
  try {
    state.runState = await api(`/sessions/${state.selectedSessionId}/state`);
  } catch (error) {
    state.runState = null;
    renderEmpty(runStatePanel, error.message);
    return;
  }
  renderRunState();
}

async function loadTriage() {
  if (!state.selectedRunId) {
    state.triage = null;
    renderTriage();
    return;
  }
  try {
    state.triage = await api(`/runs/${state.selectedRunId}/triage`, { method: "POST" });
  } catch (error) {
    state.triage = null;
    renderEmpty(triageOutput, error.message);
    return;
  }
  renderTriage();
}

projectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(projectForm);
  const payload = {
    name: formData.get("name"),
    base_url: formData.get("base_url"),
    repository_url: formData.get("repository_url"),
    healthcheck_path: formData.get("healthcheck_path"),
    metadata: { source: "dashboard" },
  };

  const submitButton = projectForm.querySelector("button[type='submit']");
  await withButtonLock(submitButton, async () => {
    try {
      const project = await api("/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await ensureProjectMonitor(project);
      state.selectedProjectId = project.project_id;
      setFeedback(projectMessage, `Created project ${project.name}.`, "ok");
      await loadProjects();
    } catch (error) {
      setFeedback(projectMessage, error.message, "error");
    }
  });
});

projectSelect.addEventListener("change", async () => {
  state.selectedProjectId = projectSelect.value || null;
  state.selectedRunId = null;
  state.selectedSessionId = null;
  state.selectedStoryId = null;
  state.storyCodeContext = null;
  renderSelectedProjectSummary();
  await refreshSelectedProjectData();
});

refreshProjectsButton.addEventListener("click", async () => {
  await withButtonLock(refreshProjectsButton, async () => {
    try {
      await loadProjects();
      setFeedback(projectMessage, "Project list refreshed.", "ok");
    } catch (error) {
      setFeedback(projectMessage, error.message, "error");
    }
  });
});

enableTriggerButton.addEventListener("click", async () => {
  if (!state.selectedProjectId) {
    setFeedback(projectMessage, "Select a project first.", "error");
    return;
  }

  await withButtonLock(enableTriggerButton, async () => {
    try {
      await api(`/projects/${state.selectedProjectId}/monitor/trigger`, {
        method: "PUT",
        body: JSON.stringify({
          enabled: true,
          failure_task_id: "easy",
          severity: "high",
          auto_create_run: true,
        }),
      });
      setFeedback(projectMessage, "Auto incident trigger enabled for this project.", "ok");
    } catch (error) {
      setFeedback(projectMessage, error.message, "error");
    }
  });
});

runHealthButton.addEventListener("click", async () => {
  const project = getSelectedProject();
  if (!project) {
    setFeedback(checkMessage, "Select a project first.", "error");
    return;
  }

  await withButtonLock(runHealthButton, async () => {
    try {
      await ensureProjectMonitor(project);
      state.latestCheck = await api(`/projects/${project.project_id}/monitor/check`, { method: "POST" });
      setFeedback(checkMessage, `Health check finished with status "${state.latestCheck.status}".`, state.latestCheck.status === "healthy" ? "ok" : "error");
      await refreshSelectedProjectData();
    } catch (error) {
      setFeedback(checkMessage, error.message, "error");
    }
  });
});

browserCheckForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedProjectId) {
    setFeedback(checkMessage, "Select a project first.", "error");
    return;
  }

  const formData = new FormData(browserCheckForm);
  const submitButton = browserCheckForm.querySelector("button[type='submit']");
  await withButtonLock(submitButton, async () => {
    try {
      state.latestCheck = await api(`/projects/${state.selectedProjectId}/checks/browser`, {
        method: "POST",
        body: JSON.stringify({
          path: formData.get("path"),
          expected_text: formData.get("expected_text") || null,
          expected_selector: formData.get("expected_selector") || null,
          timeout_seconds: 8,
          label: formData.get("label"),
          browser_mode: formData.get("browser_mode"),
          wait_until: "networkidle",
        }),
      });
      setFeedback(
        checkMessage,
        `Browser check finished with status "${state.latestCheck.status}" using ${state.latestCheck.engine || formData.get("browser_mode")} mode.`,
        state.latestCheck.status === "healthy" ? "ok" : "error",
      );
      await refreshSelectedProjectData();
    } catch (error) {
      setFeedback(checkMessage, error.message, "error");
    }
  });
});

apiCheckForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedProjectId) {
    setFeedback(checkMessage, "Select a project first.", "error");
    return;
  }

  const formData = new FormData(apiCheckForm);
  const submitButton = apiCheckForm.querySelector("button[type='submit']");
  await withButtonLock(submitButton, async () => {
    try {
      state.latestCheck = await api(`/projects/${state.selectedProjectId}/checks/api`, {
        method: "POST",
        body: JSON.stringify({
          path: formData.get("path"),
          method: formData.get("method"),
          expected_status: Number(formData.get("expected_status")),
          timeout_seconds: 8,
          label: formData.get("label"),
        }),
      });
      setFeedback(checkMessage, `API check finished with status "${state.latestCheck.status}".`, state.latestCheck.status === "healthy" ? "ok" : "error");
      await refreshSelectedProjectData();
    } catch (error) {
      setFeedback(checkMessage, error.message, "error");
    }
  });
});

storyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedProjectId) {
    setFeedback(storyMessage, "Select a project first.", "error");
    return;
  }

  const formData = new FormData(storyForm);
  const submitButton = storyForm.querySelector("button[type='submit']");
  const tags = String(formData.get("tags") || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const acceptanceCriteria = String(formData.get("acceptance_criteria") || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

  await withButtonLock(submitButton, async () => {
    try {
      const stories = await api(`/projects/${state.selectedProjectId}/stories`, {
        method: "POST",
        body: JSON.stringify({
          stories: [
            {
              title: formData.get("title"),
              description: formData.get("description"),
              acceptance_criteria: acceptanceCriteria,
              tags,
              hints: {
                path: formData.get("path") || null,
                expected_text: formData.get("expected_text") || null,
                api_path: formData.get("api_path") || null,
              },
            },
          ],
        }),
      });
      state.selectedStoryId = stories[0]?.story_id || null;
      setFeedback(storyMessage, "Story added to the project backlog.", "ok");
      await refreshSelectedProjectData();
    } catch (error) {
      setFeedback(storyMessage, error.message, "error");
    }
  });
});

logForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedProjectId) {
    setFeedback(logMessage, "Select a project first.", "error");
    return;
  }

  const formData = new FormData(logForm);
  const submitButton = logForm.querySelector("button[type='submit']");
  await withButtonLock(submitButton, async () => {
    try {
      await api(`/projects/${state.selectedProjectId}/logs`, {
        method: "POST",
        body: JSON.stringify({
          entries: [
            {
              level: formData.get("level"),
              source: formData.get("source"),
              message: formData.get("message"),
              context: {},
            },
          ],
        }),
      });
      setFeedback(logMessage, "Runtime log entry added to this project.", "ok");
      await refreshSelectedProjectData();
    } catch (error) {
      setFeedback(logMessage, error.message, "error");
    }
  });
});

async function init() {
  renderLatestCheck();
  renderRunState();
  renderTriage();
  renderStoryDetail();
  renderSignalGrid();
  renderStoryReport();
  renderStoriesList();
  await checkApiStatus();
  await loadProjects();
}

init();
