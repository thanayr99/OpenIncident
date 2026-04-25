import { AgentCard } from "./AgentCard";
import { formatTime } from "../utils/format";

export function Sidebar({
  agents,
  selectedRole,
  setSelectedRole,
  selectedProject,
  summary,
  projectForm,
  setProjectForm,
  createProject,
  busy,
  projects,
  selectedProjectId,
  setSelectedProjectId,
  recentEvents,
  openSelectedProject,
  launchDemoFlow,
}) {
  const storyReport = summary?.story_report;
  const latestHealth = summary?.latest_health;
  const endpointCount = selectedProject?.endpoints?.length || (selectedProject?.base_url ? 1 : 0);
  const editingExisting = Boolean(projectForm.project_id);

  return (
    <aside className="ox-left">
      <section className="ox-panel project-rail">
        <p className="ox-label">Project Rail</p>
        <div className="project-rail-header">
          <strong>{selectedProject?.name || "No project selected"}</strong>
          <span>{selectedProject?.repository_url ? "repo linked" : "repo pending"}</span>
        </div>
        <div className="project-rail-grid">
          <div className="project-rail-chip">
            <span>Health</span>
            <strong>{latestHealth?.status || "idle"}</strong>
          </div>
          <div className="project-rail-chip">
            <span>Stories</span>
            <strong>{storyReport ? `${storyReport.completed_stories}/${storyReport.total_stories}` : "0/0"}</strong>
          </div>
          <div className="project-rail-chip">
            <span>Deploy</span>
            <strong>{endpointCount ? "linked" : "pending"}</strong>
          </div>
          <div className="project-rail-chip">
            <span>Repo</span>
            <strong>{selectedProject?.repository_url ? "connected" : "missing"}</strong>
          </div>
          <div className="project-rail-chip">
            <span>Endpoints</span>
            <strong>{endpointCount}</strong>
          </div>
        </div>
        <select value={selectedProjectId || ""} onChange={(event) => setSelectedProjectId(event.target.value || null)}>
          <option value="">Select project</option>
          {projects.map((project) => <option key={project.project_id} value={project.project_id}>{project.name}</option>)}
        </select>
        <div className="project-rail-actions">
          <button disabled={!selectedProjectId} onClick={openSelectedProject} type="button">Open</button>
          <button disabled={!selectedProject || busy.demoFlow} onClick={launchDemoFlow} type="button">
            {busy.demoFlow ? "Running..." : "Demo run"}
          </button>
        </div>
      </section>

      <section className="ox-panel">
        <p className="ox-label">Agent Network - {agents.length} agents</p>
        <div className="agent-list">
          {agents.map((agent) => (
            <AgentCard key={agent.agent_id || agent.role} agent={agent} selected={agent.role === selectedRole} onSelect={setSelectedRole} />
          ))}
        </div>
      </section>

      <section className="ox-panel">
        <p className="ox-label">Create / Update Project</p>
        <form className="ox-form" onSubmit={createProject}>
          <input placeholder="Project ID optional" value={projectForm.project_id} onChange={(event) => setProjectForm((current) => ({ ...current, project_id: event.target.value }))} />
          <input placeholder="Project name" value={projectForm.name} onChange={(event) => setProjectForm((current) => ({ ...current, name: event.target.value }))} />
          <input placeholder="Frontend URL" value={projectForm.frontend_url} onChange={(event) => setProjectForm((current) => ({ ...current, frontend_url: event.target.value, base_url: event.target.value || current.base_url }))} />
          <input placeholder="Backend API URL" value={projectForm.backend_url} onChange={(event) => setProjectForm((current) => ({ ...current, backend_url: event.target.value }))} />
          <input placeholder="Repository URL" value={projectForm.repository_url} onChange={(event) => setProjectForm((current) => ({ ...current, repository_url: event.target.value }))} />
          <button disabled={busy.project} type="submit">
            {busy.project ? "Saving..." : editingExisting ? "Save project changes" : "Create / update project"}
          </button>
        </form>
      </section>

      <section className="ox-panel event-log">
        <p className="ox-label">Event Log</p>
        {recentEvents.slice(0, 6).map((event) => (
          <div className={`event-row severity-${event.severity || "info"}`} key={event.event_id}>
            <span>{formatTime(event.timestamp)}</span>
            <strong>{event.title}</strong>
          </div>
        ))}
        {!recentEvents.length ? <p className="muted">No events yet.</p> : null}
      </section>
    </aside>
  );
}
