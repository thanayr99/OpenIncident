export function ProjectLaunch({
  apiHealth,
  account,
  accountForm,
  setAccountForm,
  createAccount,
  signOut,
  projectForm,
  setProjectForm,
  projects,
  selectedProjectId,
  setSelectedProjectId,
  openSelectedProject,
  createProject,
  busy,
  message,
  loadDemoProjectTemplate,
  runInstantAgentDemo,
  instantDemo,
}) {
  const selectedProject = projects.find((project) => project.project_id === selectedProjectId);
  const launchHighlights = [
    {
      title: "Connect code and runtime",
      detail: "Attach repository, frontend URL, backend API, and health endpoints as one incident surface.",
    },
    {
      title: "Orchestrate specialist agents",
      detail: "Planner, frontend, API, reliability, triage, guardian, and oversight agents collaborate in one flow.",
    },
    {
      title: "Train and evaluate behavior",
      detail: "Run OpenEnv-style incident trajectories with rewards, baseline comparison, and reproducible artifacts.",
    },
  ];
  const launchSignals = [
    { label: "API", value: apiHealth.toUpperCase() },
    { label: "Projects", value: `${projects.length}` },
    { label: "Mode", value: account ? "Project setup" : "Operator sign in" },
  ];

  return (
    <div className="launch-shell">
      <div className="ox-scanlines" />
      <div className="ox-vignette" />
      <section className="launch-card">
        <div className="launch-head">
          <div className="launch-steps">
            <span className={account ? "done" : "active"}>1. Login</span>
            <span className={account ? "active" : ""}>2. Create project</span>
            <span>3. Command center</span>
          </div>
          <div className="launch-signal-row">
            {launchSignals.map((signal) => (
              <div className="launch-signal-pill" key={signal.label}>
                <span>{signal.label}</span>
                <strong>{signal.value}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="launch-intro-grid">
          <div className="launch-intro-main">
            <p className="ox-label">OpenIncident X setup</p>
            <h1>{account ? "Create a project to activate your command center" : "Run reliability operations with coordinated agents"}</h1>
            <p className="muted launch-intro-copy">
              {account
                ? "Add project metadata once and let the system connect repository context, runtime checks, incident triage, and training traces."
                : "Sign in with your operator account. If the email does not exist yet, this environment creates it automatically and starts a guided setup."}
            </p>
            <div className="launch-highlight-grid">
              {launchHighlights.map((item) => (
                <article className="launch-highlight-card" key={item.title}>
                  <h3>{item.title}</h3>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
          </div>

          <aside className="launch-intro-side">
            <div className="launch-quick-demo">
              <button type="button" onClick={runInstantAgentDemo} disabled={busy.instantDemo}>
                {busy.instantDemo ? "Running demo..." : "Run instant agent demo"}
              </button>
              <small>Runs a local simulation and shows inspect to diagnose to fix to resolve behavior.</small>
              {instantDemo ? (
                <p className="muted">
                  Latest: {instantDemo.finalStatus} | reward {instantDemo.totalReward} | actions {instantDemo.steps.map((step) => step.action).join(" -> ")}
                </p>
              ) : (
                <p className="muted">No demo run yet. Trigger one click to preview the full decision chain.</p>
              )}
            </div>
            <div className="launch-checklist">
              <span className="ox-label">Quick checklist</span>
              <p>1. Sign in as operator</p>
              <p>2. Attach GitHub + frontend + backend URLs</p>
              <p>3. Open command center and run checks</p>
            </div>
          </aside>
        </div>

        {!account ? (
          <div className="launch-form-zone">
            <span className="ox-label">Operator access</span>
            <form className="ox-form launch-form" onSubmit={createAccount}>
              <input placeholder="Full name" value={accountForm.name} onChange={(event) => setAccountForm((current) => ({ ...current, name: event.target.value }))} />
              <input required type="email" placeholder="Email" value={accountForm.email} onChange={(event) => setAccountForm((current) => ({ ...current, email: event.target.value }))} />
              <input placeholder="Team / company name" value={accountForm.team} onChange={(event) => setAccountForm((current) => ({ ...current, team: event.target.value }))} />
              <input required type="password" placeholder="Password" value={accountForm.password} onChange={(event) => setAccountForm((current) => ({ ...current, password: event.target.value }))} />
              <button type="submit" disabled={busy.account}>{busy.account ? "Signing in..." : "Sign in and continue"}</button>
            </form>
          </div>
        ) : (
          <div className="launch-form-zone">
            <div className="launch-account">
              <span>Signed in as</span>
              <strong>{account.name}</strong>
              <em>{account.email}</em>
              <button type="button" onClick={signOut}>Switch account</button>
            </div>

            <form className="ox-form launch-form" onSubmit={createProject}>
              <div className="template-strip launch-template-strip">
                <button type="button" className="template-chip" onClick={loadDemoProjectTemplate}>Load demo template</button>
              </div>
              <input required placeholder="Project name" value={projectForm.name} onChange={(event) => setProjectForm((current) => ({ ...current, name: event.target.value }))} />
              <input required placeholder="GitHub repository URL" value={projectForm.repository_url} onChange={(event) => setProjectForm((current) => ({ ...current, repository_url: event.target.value }))} />
              <input placeholder="Frontend URL (Vercel)" value={projectForm.frontend_url} onChange={(event) => setProjectForm((current) => ({ ...current, frontend_url: event.target.value, base_url: event.target.value || current.base_url }))} />
              <input placeholder="Backend API URL (Railway)" value={projectForm.backend_url} onChange={(event) => setProjectForm((current) => ({ ...current, backend_url: event.target.value }))} />
              <input placeholder="Frontend health path (default /)" value={projectForm.frontend_healthcheck_path} onChange={(event) => setProjectForm((current) => ({ ...current, frontend_healthcheck_path: event.target.value }))} />
              <input placeholder="Backend health path (default /health)" value={projectForm.backend_healthcheck_path} onChange={(event) => setProjectForm((current) => ({ ...current, backend_healthcheck_path: event.target.value, healthcheck_path: event.target.value || current.healthcheck_path }))} />
              <input placeholder="Project ID (optional advanced)" value={projectForm.project_id} onChange={(event) => setProjectForm((current) => ({ ...current, project_id: event.target.value }))} />
              <button disabled={busy.project} type="submit">{busy.project ? "Creating project..." : "Create project and open dashboard"}</button>
            </form>

            {projects.length ? (
              <div className="launch-existing">
                <span className="ox-label">Existing project</span>
                <select value={selectedProjectId || ""} onChange={(event) => setSelectedProjectId(event.target.value || null)}>
                  <option value="">Select project</option>
                  {projects.map((project) => <option key={project.project_id} value={project.project_id}>{project.name}</option>)}
                </select>
                <button disabled={!selectedProjectId} type="button" onClick={openSelectedProject}>
                  {selectedProject ? `Open ${selectedProject.name}` : "Open selected project"}
                </button>
              </div>
            ) : null}
          </div>
        )}
        <div className="command-message">API {apiHealth}. {message}</div>
      </section>
    </div>
  );
}
