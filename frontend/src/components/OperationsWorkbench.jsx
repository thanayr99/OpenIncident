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
  applySplunkConnectorTemplate,
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
  const connector = projectSummary?.log_connector || null;
  const connectorHealthLabel = !connector
    ? "Not configured"
    : !connector.enabled
      ? "Disabled"
      : connector.last_pull_success === true
        ? "Healthy"
        : connector.last_pull_success === false
          ? "Degraded"
          : "Configured";
  const connectorHealthTone = connectorHealthLabel.toLowerCase().replace(/\s+/g, "-");
  const connectorLastPull = connector?.last_pulled_at ? formatTime(connector.last_pulled_at) : "Never";
  const connectorFailureCount = Number.isFinite(connector?.consecutive_failures) ? connector.consecutive_failures : 0;
  const connectorDetail = connector?.last_pull_error || connector?.last_pull_summary || "No connector pull has run yet.";

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
            <span>{connectorHealthLabel}</span>
          </header>
          <div className="connector-health">
            <div className={`connector-pill ${connectorHealthTone}`}>{connectorHealthLabel}</div>
            <div className="connector-health-grid">
              <div>
                <span>Last pull</span>
                <strong>{connectorLastPull}</strong>
              </div>
              <div>
                <span>Fetched</span>
                <strong>{connector?.last_fetched_entries ?? 0}</strong>
              </div>
              <div>
                <span>Imported</span>
                <strong>{connector?.last_imported_entries ?? 0}</strong>
              </div>
              <div>
                <span>Failures</span>
                <strong>{connectorFailureCount}</strong>
              </div>
            </div>
            <p className="muted">{connectorDetail}</p>
          </div>
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
                <option value="splunk_jsonl">Splunk JSONL</option>
              </select>
            </div>
            <div className="connector-row">
              <select value={logConnectorForm.payload_encoding} onChange={(event) => setLogConnectorForm((current) => ({ ...current, payload_encoding: event.target.value }))}>
                <option value="json">Payload JSON</option>
                <option value="form">Payload form-data</option>
              </select>
              <button onClick={applySplunkConnectorTemplate} type="button">Use Splunk template</button>
            </div>
            <input
              value={logConnectorForm.entries_path}
              onChange={(event) => setLogConnectorForm((current) => ({ ...current, entries_path: event.target.value }))}
              placeholder="entries path for JSON, e.g. data.logs"
            />
            <textarea
              className="workbench-textarea"
              value={logConnectorForm.headers_json}
              onChange={(event) => setLogConnectorForm((current) => ({ ...current, headers_json: event.target.value }))}
              placeholder='Headers JSON, e.g. {"Authorization":"Splunk <token>"}'
            />
            <textarea
              className="workbench-textarea"
              value={logConnectorForm.query_params_json}
              onChange={(event) => setLogConnectorForm((current) => ({ ...current, query_params_json: event.target.value }))}
              placeholder='Query params JSON, e.g. {"output_mode":"json"}'
            />
            <textarea
              className="workbench-textarea"
              value={logConnectorForm.payload_json}
              onChange={(event) => setLogConnectorForm((current) => ({ ...current, payload_json: event.target.value }))}
              placeholder='Payload JSON, e.g. {"search":"search index=main | head 100","output_mode":"json"}'
            />
            <div className="connector-row">
              <input
                value={logConnectorForm.level_field}
                onChange={(event) => setLogConnectorForm((current) => ({ ...current, level_field: event.target.value }))}
                placeholder="level field (e.g. level)"
              />
              <input
                value={logConnectorForm.source_field}
                onChange={(event) => setLogConnectorForm((current) => ({ ...current, source_field: event.target.value }))}
                placeholder="source field (e.g. source)"
              />
            </div>
            <div className="connector-row">
              <input
                value={logConnectorForm.message_field}
                onChange={(event) => setLogConnectorForm((current) => ({ ...current, message_field: event.target.value }))}
                placeholder="message field (e.g. _raw)"
              />
              <input
                value={logConnectorForm.timestamp_field}
                onChange={(event) => setLogConnectorForm((current) => ({ ...current, timestamp_field: event.target.value }))}
                placeholder="timestamp field (e.g. _time)"
              />
            </div>
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

