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
}) {
  const selectedProject = projects.find((project) => project.project_id === selectedProjectId);

  return (
    <div className="launch-shell">
      <div className="ox-scanlines" />
      <div className="ox-vignette" />
      <section className="launch-card">
        <div className="launch-steps">
          <span className={account ? "done" : "active"}>1. Login</span>
          <span className={account ? "active" : ""}>2. Create project</span>
          <span>3. Command center</span>
        </div>
        <p className="ox-label">OpenIncident X setup</p>
        <h1>{account ? "Create a project to unlock the command center" : "Sign in with your operator account"}</h1>
        <p className="muted">
          {account
            ? "Add the project name, GitHub repository, frontend URL, and backend API URL. After this, agents can inspect code, discover routes, validate stories, read signals, and open incidents."
            : "Use your email and password. If the account does not exist yet, it will be created automatically for this environment."}
        </p>

        {!account ? (
          <form className="ox-form launch-form" onSubmit={createAccount}>
            <input placeholder="Full name" value={accountForm.name} onChange={(event) => setAccountForm((current) => ({ ...current, name: event.target.value }))} />
            <input required type="email" placeholder="Email" value={accountForm.email} onChange={(event) => setAccountForm((current) => ({ ...current, email: event.target.value }))} />
            <input placeholder="Team / company name" value={accountForm.team} onChange={(event) => setAccountForm((current) => ({ ...current, team: event.target.value }))} />
            <input required type="password" placeholder="Password" value={accountForm.password} onChange={(event) => setAccountForm((current) => ({ ...current, password: event.target.value }))} />
            <button type="submit" disabled={busy.account}>{busy.account ? "Signing in..." : "Sign in and continue"}</button>
          </form>
        ) : (
          <>
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
              <input placeholder="Project ID optional" value={projectForm.project_id} onChange={(event) => setProjectForm((current) => ({ ...current, project_id: event.target.value }))} />
              <input required placeholder="Project name" value={projectForm.name} onChange={(event) => setProjectForm((current) => ({ ...current, name: event.target.value }))} />
              <input required placeholder="GitHub repository URL" value={projectForm.repository_url} onChange={(event) => setProjectForm((current) => ({ ...current, repository_url: event.target.value }))} />
              <input placeholder="Frontend URL (Vercel)" value={projectForm.frontend_url} onChange={(event) => setProjectForm((current) => ({ ...current, frontend_url: event.target.value, base_url: event.target.value || current.base_url }))} />
              <input placeholder="Backend API URL (Railway)" value={projectForm.backend_url} onChange={(event) => setProjectForm((current) => ({ ...current, backend_url: event.target.value }))} />
              <input placeholder="Frontend health path (optional)" value={projectForm.frontend_healthcheck_path} onChange={(event) => setProjectForm((current) => ({ ...current, frontend_healthcheck_path: event.target.value }))} />
              <input placeholder="Backend health path (optional)" value={projectForm.backend_healthcheck_path} onChange={(event) => setProjectForm((current) => ({ ...current, backend_healthcheck_path: event.target.value, healthcheck_path: event.target.value || current.healthcheck_path }))} />
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
          </>
        )}
        <div className="command-message">API {apiHealth}. {message}</div>
      </section>
    </div>
  );
}
