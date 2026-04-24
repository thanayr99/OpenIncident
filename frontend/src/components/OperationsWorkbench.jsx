import { formatTime } from "../utils/format";

export function OperationsWorkbench({
  selectedProject,
  bulkStoryInput,
  setBulkStoryInput,
  bulkLogInput,
  setBulkLogInput,
  importBulkStories,
  ingestBulkLogs,
  logConnectorForm,
  setLogConnectorForm,
  saveLogConnector,
  pullConnectedLogs,
  projectSummary,
  stories,
  logs,
  logSummary,
  ingestSampleMetrics,
  busy,
}) {
  const progressItems = [
    ["Account login", true],
    ["Project created", Boolean(selectedProject)],
    ["GitHub repo linked", Boolean(selectedProject?.repository_url)],
    ["Frontend/API endpoint linked", Boolean((selectedProject?.endpoints?.length || 0) > 0 || selectedProject?.base_url)],
    ["Workspace pulled", Boolean(projectSummary?.recent_events?.some((event) => event.event_type === "test_environment_run"))],
    ["Stories or test cases imported", stories.length > 0],
    ["Logs connected", (logSummary?.total_entries || 0) > 0 || Boolean(projectSummary?.log_connector?.url)],
    ["Checks executed", Boolean(projectSummary?.latest_health || projectSummary?.latest_check)],
    ["Incident triaged", Boolean(projectSummary?.recent_events?.some((event) => event.event_type === "triage_completed"))],
  ];
  const completedCount = progressItems.filter(([, done]) => done).length;

  return (
    <section className="ox-panel workbench-panel">
      <p className="ox-label">Bulk Testing + Logs</p>

      <div className="workbench-grid">
        <article className="workbench-card">
          <header>
            <h3>Bulk User Stories / Test Cases</h3>
            <span>{stories.length} tracked</span>
          </header>
          <p className="muted">
            Paste a JSON array or structured QA test cases. Fields like <code>Test Case ID</code>, <code>Preconditions</code>, <code>Test Steps</code>,
            <code> Test Data</code>, and <code>Expected Result</code> are supported and normalized automatically.
          </p>
          <textarea
            className="workbench-textarea"
            value={bulkStoryInput}
            onChange={(event) => setBulkStoryInput(event.target.value)}
            placeholder={`Test Case ID: TC_AUTH_001
Title: Verify successful login with valid credentials
Priority: High
Preconditions: The user has a registered account and is on the login page.
Test Steps: 1. Enter valid email in the username field.
2. Enter valid password in the password field.
3. Click the Login button.
Test Data: User: test@example.com, Pass: P@ssword123.
Expected Result: User is redirected to the dashboard and a Welcome message is displayed.
---`}
          />
          <button disabled={!selectedProject || busy.bulkStories} onClick={importBulkStories} type="button">
            {busy.bulkStories ? "Importing and checking..." : "Import test cases and check everything"}
          </button>
        </article>

        <article className="workbench-card">
          <header>
            <h3>Manual Logs</h3>
            <span>{logSummary?.total_entries || 0} logs</span>
          </header>
          <p className="muted">
            Paste raw runtime logs or a JSON entries array. These logs are attached to the project and included in test execution evidence and triage.
          </p>
          <textarea
            className="workbench-textarea"
            value={bulkLogInput}
            onChange={(event) => setBulkLogInput(event.target.value)}
            placeholder="[ERROR] api: Database connection timeout while serving /api/profile"
          />
          <button disabled={!selectedProject || busy.bulkLogs} onClick={ingestBulkLogs} type="button">
            {busy.bulkLogs ? "Connecting logs..." : "Connect logs to project"}
          </button>
        </article>
      </div>

      <div className="workbench-grid compact">
        <article className="workbench-card">
          <header>
            <h3>Live Log Connector</h3>
            <span>{projectSummary?.log_connector?.last_pulled_at ? "active" : "setup"}</span>
          </header>
          <div className="connector-form">
            <input
              value={logConnectorForm.url}
              onChange={(event) => setLogConnectorForm((current) => ({ ...current, url: event.target.value }))}
              placeholder="https://your-app.com/api/logs"
            />
            <div className="connector-row">
              <select value={logConnectorForm.method} onChange={(event) => setLogConnectorForm((current) => ({ ...current, method: event.target.value }))}>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
              </select>
              <select value={logConnectorForm.format} onChange={(event) => setLogConnectorForm((current) => ({ ...current, format: event.target.value }))}>
                <option value="text">Plain text</option>
                <option value="json">JSON</option>
              </select>
            </div>
            <input
              value={logConnectorForm.entries_path}
              onChange={(event) => setLogConnectorForm((current) => ({ ...current, entries_path: event.target.value }))}
              placeholder="entries path for JSON, e.g. data.logs"
            />
            <div className="connector-actions">
              <button disabled={!selectedProject || !logConnectorForm.url || busy.logConnector} onClick={saveLogConnector} type="button">
                {busy.logConnector ? "Saving..." : "Save connector"}
              </button>
              <button disabled={!selectedProject || !projectSummary?.log_connector?.url || busy.pullLogs} onClick={pullConnectedLogs} type="button">
                {busy.pullLogs ? "Pulling..." : "Pull connected logs"}
              </button>
            </div>
          </div>
        </article>

        <article className="workbench-card summary">
          <header>
            <h3>Progress Tracker</h3>
            <span>{completedCount}/{progressItems.length}</span>
          </header>
          <div className="mini-list">
            {progressItems.map(([label, done]) => (
              <div className="mini-row" key={label}>
                <strong>{done ? "OK" : "..."} {label}</strong>
                <span>{done ? "done" : "left"}</span>
              </div>
            ))}
          </div>
        </article>
      </div>

      <div className="workbench-grid compact">
        <article className="workbench-card summary">
          <header>
            <h3>Imported Queue</h3>
            <span>{stories.length}</span>
          </header>
          <div className="mini-list">
            {stories.length ? (
              stories.slice(0, 6).map((story) => (
                <div className="mini-row" key={story.story_id}>
                  <strong>{story.title}</strong>
                  <span>{story.status}</span>
                </div>
              ))
            ) : (
              <p className="muted">No stories or test cases imported yet.</p>
            )}
          </div>
        </article>

        <article className="workbench-card summary">
          <header>
            <h3>Log Signals</h3>
            <span>{logSummary?.error_entries || 0} errors</span>
          </header>
          <div className="mini-list">
            {logs.length ? (
              logs.slice(0, 6).map((entry) => (
                <div className="mini-row" key={entry.log_id}>
                  <strong>{entry.level} | {entry.source}</strong>
                  <span>{formatTime(entry.timestamp)}</span>
                </div>
              ))
            ) : (
              <p className="muted">No logs connected yet.</p>
            )}
          </div>
        </article>

        <article className="workbench-card summary">
          <header>
            <h3>Metric Signals</h3>
            <span>{projectSummary?.metric_summary?.total_points || 0} points</span>
          </header>
          <div className="mini-list">
            {Object.entries(projectSummary?.metric_summary?.latest_values || {}).slice(0, 6).map(([name, value]) => (
              <div className="mini-row" key={name}>
                <strong>{name}</strong>
                <span>{String(value)}</span>
              </div>
            ))}
            {!Object.keys(projectSummary?.metric_summary?.latest_values || {}).length ? (
              <p className="muted">No metrics connected yet.</p>
            ) : null}
          </div>
          <button disabled={!selectedProject || busy.metrics} onClick={ingestSampleMetrics} type="button">
            {busy.metrics ? "Connecting metrics..." : "Connect sample metrics"}
          </button>
        </article>
      </div>
    </section>
  );
}

