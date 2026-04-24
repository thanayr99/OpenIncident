import { useEffect, useMemo, useState } from "react";
import { AgentScene } from "./components/AgentScene";
import { MainStage } from "./components/MainStage";
import { ProjectLaunch } from "./components/ProjectLaunch";
import { RightPanel } from "./components/RightPanel";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { FALLBACK_AGENTS } from "./data/agents";
import { initialAccountForm, initialProjectForm, initialStoryForm } from "./data/forms";
import { apiRequest, clearAuthToken, getAuthToken, setAuthToken } from "./lib/api";
import { parseBulkLogs, parseBulkStories } from "./utils/ingest";

function projectSummaryHasConnector(summary) {
  return Boolean(summary?.log_connector?.url);
}

function getProjectEndpoint(project, preferredSurface) {
  if (!project) return null;
  const endpoints = Array.isArray(project.endpoints) ? project.endpoints : [];
  const bySurface = endpoints.find((endpoint) => (endpoint?.surface || "").toLowerCase() === preferredSurface.toLowerCase());
  if (bySurface) return bySurface;
  const byId = endpoints.find((endpoint) => (endpoint?.endpoint_id || "").toLowerCase() === preferredSurface.toLowerCase());
  if (byId) return byId;
  return endpoints[0] || null;
}

function buildProjectEndpointInputs(form) {
  const endpoints = [];
  const frontendUrl = (form.frontend_url || form.base_url || "").trim();
  const backendUrl = (form.backend_url || "").trim();
  if (frontendUrl) {
    endpoints.push({
      endpoint_id: "frontend",
      label: "Frontend",
      surface: "frontend",
      base_url: frontendUrl,
      healthcheck_path: form.frontend_healthcheck_path?.trim() || "/",
    });
  }
  if (backendUrl) {
    endpoints.push({
      endpoint_id: "backend",
      label: "Backend API",
      surface: "api",
      base_url: backendUrl,
      healthcheck_path: form.backend_healthcheck_path?.trim() || form.healthcheck_path || "/health",
    });
  }
  return endpoints;
}

export default function App() {
  const [apiHealth, setApiHealth] = useState("checking");
  const [clock, setClock] = useState(new Date());
  const [account, setAccount] = useState(null);
  const [accountForm, setAccountForm] = useState(initialAccountForm);
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [plannerSummary, setPlannerSummary] = useState(null);
  const [environmentSummary, setEnvironmentSummary] = useState(null);
  const [trainingDatasets, setTrainingDatasets] = useState({});
  const [frontendDiscovery, setFrontendDiscovery] = useState(null);
  const [latestCheck, setLatestCheck] = useState(null);
  const [predeployResult, setPredeployResult] = useState(null);
  const [stories, setStories] = useState([]);
  const [logs, setLogs] = useState([]);
  const [logSummary, setLogSummary] = useState(null);
  const [logConnectorForm, setLogConnectorForm] = useState({
    url: "",
    method: "GET",
    format: "text",
    entries_path: "",
    enabled: true,
  });
  const [bulkStoryInput, setBulkStoryInput] = useState(`[
  {
    "title": "Login page should load",
    "description": "The login page should render for users.",
    "acceptance_criteria": ["The /login page loads", "Sign in is visible"],
    "tags": ["frontend", "auth"],
    "path": "/login",
    "expected_text": "Sign in"
  },
  {
    "title": "Profile API should respond",
    "description": "The profile endpoint should return success.",
    "acceptance_criteria": ["GET /api/profile returns 200"],
    "tags": ["api", "profile"],
    "api_path": "/api/profile",
    "expected_status": 200
  }
]`);
  const [bulkLogInput, setBulkLogInput] = useState("[ERROR] api: Database connection timeout while serving /api/profile");
  const [selectedRole, setSelectedRole] = useState("reliability_analyst");
  const [projectForm, setProjectForm] = useState(initialProjectForm);
  const [storyForm, setStoryForm] = useState(initialStoryForm);
  const [latestStory, setLatestStory] = useState(null);
  const [message, setMessage] = useState("Ready.");
  const [dashboardOpen, setDashboardOpen] = useState(false);
  const [stageView, setStageView] = useState("overview");
  const [busy, setBusy] = useState({});

  function buildStoryDraft() {
    return {
      title: storyForm.title,
      description: storyForm.description,
      acceptance_criteria: storyForm.acceptance_criteria.split("\n").map((item) => item.trim()).filter(Boolean),
      tags: storyForm.tags.split(",").map((item) => item.trim()).filter(Boolean),
    };
  }

  function loadDemoProjectTemplate() {
    setProjectForm((current) => ({
      ...current,
      name: current.name || "HouseSafe AI",
      repository_url: current.repository_url || "https://github.com/example/housesafe-ai",
      frontend_url: current.frontend_url || current.base_url || "https://house-safe-ai.vercel.app",
      backend_url: current.backend_url || "https://house-safe-api.railway.app",
      base_url: current.base_url || current.frontend_url || "https://house-safe-ai.vercel.app",
      frontend_healthcheck_path: current.frontend_healthcheck_path || "/",
      backend_healthcheck_path: current.backend_healthcheck_path || "/health",
      healthcheck_path: current.healthcheck_path || current.backend_healthcheck_path || "/health",
    }));
    setMessage("Demo project template loaded. Replace the URLs with your real project values if needed.");
  }

  function applyStoryTemplate(templateKey) {
    const templates = {
      auth: {
        title: "User can login",
        description: "Login page should render the sign in form and complete the auth journey.",
        acceptance_criteria: "Login page loads\nSign in form is visible\nSuccessful login redirects to the dashboard",
        tags: "frontend,auth,login",
      },
      api: {
        title: "Health API should respond",
        description: "The deployment health endpoint should return a successful response.",
        acceptance_criteria: "Health endpoint returns HTTP 200\nResponse completes quickly",
        tags: "api,health",
      },
      frontend: {
        title: "Home page should render",
        description: "The frontend landing experience should load without a fatal render error.",
        acceptance_criteria: "Homepage loads\nPrimary call to action is visible",
        tags: "frontend,ui",
      },
    };
    const nextTemplate = templates[templateKey];
    if (!nextTemplate) return;
    setStoryForm(nextTemplate);
    setMessage(`${nextTemplate.title} template loaded.`);
  }

  const selectedProject = projects.find((project) => project.project_id === selectedProjectId) || null;
  const selectedFrontendEndpoint = getProjectEndpoint(selectedProject, "frontend");
  const selectedApiEndpoint = getProjectEndpoint(selectedProject, "api");
  const agents = summary?.agent_roster?.agents?.length ? summary.agent_roster.agents : FALLBACK_AGENTS;
  const selectedAgent = agents.find((agent) => agent.role === selectedRole) || agents[0];
  const conversations = summary?.conversation_trace?.messages || [];
  const handoffs = summary?.coordination_trace?.entries || [];
  const activeRuns = summary?.active_runs || [];
  const storyReport = summary?.story_report;
  const recentEvents = summary?.recent_events || [];

  const metricCards = useMemo(() => {
    const latest = summary?.metric_summary?.latest_values || {};
    const check = latestCheck || summary?.latest_check;
    return [
      ["Health", summary?.latest_health?.status || "unknown", summary?.latest_health?.target_url || "Run health check", summary?.latest_health?.status === "healthy" ? "ok" : "bad"],
      ["Latest Check", check?.status || "none", check?.label || "Run browser/API smoke", check?.status === "healthy" ? "ok" : check ? "bad" : "info"],
      ["Stories", storyReport ? `${storyReport.completed_stories}/${storyReport.total_stories}` : "0/0", "Completed user stories", "info"],
      ["Incidents", activeRuns.length, activeRuns.length ? "Response work active" : "No active incidents", activeRuns.length ? "bad" : "ok"],
    ];
  }, [activeRuns.length, latestCheck, storyReport, summary]);

  async function runTask(key, work) {
    setBusy((current) => ({ ...current, [key]: true }));
    try {
      await work();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy((current) => ({ ...current, [key]: false }));
    }
  }

  async function checkHealth() {
    try {
      const data = await apiRequest("/health");
      setApiHealth(data.status === "ok" ? "healthy" : "warning");
    } catch {
      setApiHealth("error");
    }
  }

  async function loadProjects(preferredId = null) {
    if (!getAuthToken()) {
      setProjects([]);
      setSelectedProjectId(null);
      return;
    }
    const data = await apiRequest("/projects");
    setProjects(data);
    const nextId = preferredId || selectedProjectId || null;
    setSelectedProjectId(nextId);
    if (nextId) await refreshSummary(nextId);
  }

  async function refreshSummary(projectId = selectedProjectId) {
    if (!projectId) return;
    const [
      summaryData,
      plannerData,
      environmentData,
      storyItems,
      logItems,
      logDigest,
      plannerTraining,
      frontendTraining,
      apiTraining,
      observabilityTraining,
      triageTraining,
      guardianTraining,
      oversightTraining,
    ] = await Promise.all([
      apiRequest(`/projects/${projectId}/summary`),
      apiRequest(`/projects/${projectId}/planner-summary`).catch(() => null),
      apiRequest(`/projects/${projectId}/environment-summary`).catch(() => null),
      apiRequest(`/projects/${projectId}/stories`).catch(() => []),
      apiRequest(`/projects/${projectId}/logs`).catch(() => []),
      apiRequest(`/projects/${projectId}/logs/summary`).catch(() => null),
      apiRequest(`/projects/${projectId}/planner-training-dataset`).catch(() => null),
      apiRequest(`/projects/${projectId}/frontend-training-dataset`).catch(() => null),
      apiRequest(`/projects/${projectId}/api-training-dataset`).catch(() => null),
      apiRequest(`/projects/${projectId}/observability-training-dataset`).catch(() => null),
      apiRequest(`/projects/${projectId}/triage-training-dataset`).catch(() => null),
      apiRequest(`/projects/${projectId}/guardian-training-dataset`).catch(() => null),
      apiRequest(`/projects/${projectId}/oversight-training-dataset`).catch(() => null),
    ]);
    setSummary(summaryData);
    setPlannerSummary(plannerData);
    setEnvironmentSummary(environmentData);
    setTrainingDatasets({
      planner: plannerTraining,
      frontend: frontendTraining,
      api: apiTraining,
      observability: observabilityTraining,
      triage: triageTraining,
      guardian: guardianTraining,
      oversight: oversightTraining,
    });
    setLogConnectorForm((current) => ({
      ...current,
      url: summaryData.log_connector?.url || current.url,
      method: summaryData.log_connector?.method || current.method,
      format: summaryData.log_connector?.format || current.format,
      entries_path: summaryData.log_connector?.entries_path || current.entries_path,
      enabled: typeof summaryData.log_connector?.enabled === "boolean" ? summaryData.log_connector.enabled : current.enabled,
    }));
    setStories(storyItems);
    setLogs(logItems);
    setLogSummary(logDigest);
    setMessage("Command center synced.");
  }

  async function createProject(event) {
    event.preventDefault();
    if (!account) {
      setMessage("Sign in before creating a project.");
      return;
    }
    if (!projectForm.repository_url.trim()) {
      setMessage("GitHub repository URL is required.");
      return;
    }
    await runTask("project", async () => {
      const endpoints = buildProjectEndpointInputs(projectForm);
      const frontendEndpoint = endpoints.find((endpoint) => endpoint.surface === "frontend") || null;
      const apiEndpoint = endpoints.find((endpoint) => endpoint.surface === "api") || null;
      const payload = {
        ...projectForm,
        base_url: (frontendEndpoint?.base_url || projectForm.base_url || "").trim(),
        repository_url: projectForm.repository_url.trim(),
        healthcheck_path: (apiEndpoint?.healthcheck_path || projectForm.healthcheck_path || "/health").trim(),
        endpoints,
        metadata: {
          owner_id: account.account_id,
          owner_name: account.name,
          owner_email: account.email,
          owner_team: account.team,
        },
      };
      if (!payload.project_id) delete payload.project_id;
      const project = await apiRequest("/projects", { method: "POST", body: JSON.stringify(payload) });
      const projectApiEndpoint = getProjectEndpoint(project, "api");
      if (projectApiEndpoint?.base_url || project.base_url) {
        await apiRequest(`/projects/${project.project_id}/monitor`, {
          method: "PUT",
          body: JSON.stringify({
            endpoint_id: projectApiEndpoint?.endpoint_id || null,
            base_url: projectApiEndpoint?.base_url || project.base_url,
            healthcheck_path: projectApiEndpoint?.healthcheck_path || project.healthcheck_path || "/health",
            expected_status: 200,
            timeout_seconds: 10,
            enabled: true,
            headers: {},
          }),
        });
      }
      await loadProjects(project.project_id);
      await refreshSummary(project.project_id);
      setDashboardOpen(true);
      setStageView("overview");
      setMessage(`Project ${project.name} registered with ${project.endpoints?.length || 0} endpoint(s). Dashboard opened.`);
    });
  }

  async function pullWorkspace() {
    if (!selectedProject) return;
    if (!selectedProject.repository_url) {
      setMessage("Add a GitHub repository URL before pulling the test environment.");
      return;
    }
    await runTask("workspace", async () => {
      await apiRequest(`/projects/${selectedProject.project_id}/testing/environment`, {
        method: "PUT",
        body: JSON.stringify({
          repository_url: selectedProject.repository_url,
          branch: "main",
          install_command: "npm install",
          test_command: "npm test",
          workdir: "",
          enabled: true,
          shell: "powershell",
          env: {},
        }),
      });
      const result = await apiRequest(`/projects/${selectedProject.project_id}/testing/environment/run`, {
        method: "POST",
        body: JSON.stringify({ pull_latest: true, run_install: false, run_tests: false, timeout_seconds: 300 }),
      });
      setMessage(`Workspace ready: ${result.workspace_path}`);
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function discoverFrontend() {
    if (!selectedProject) return;
    await runTask("discover", async () => {
      const data = await apiRequest(`/projects/${selectedProject.project_id}/frontend/discover`);
      setFrontendDiscovery(data);
      setMessage(data.error_message || `Discovered ${data.routes.length} frontend route(s).`);
    });
  }

  async function runHealthCheck() {
    if (!selectedProject) return;
    const healthEndpoint = selectedApiEndpoint || selectedFrontendEndpoint;
    if (!healthEndpoint?.base_url && !selectedProject.base_url) {
      setMessage("Add a frontend or backend URL to run live health checks.");
      return;
    }
    await runTask("healthCheck", async () => {
      const result = await apiRequest(`/projects/${selectedProject.project_id}/monitor/check`, {
        method: "POST",
      });
      setMessage(`Health check ${result.status}: ${result.error_message || result.target_url}`);
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function runBrowserSmoke() {
    if (!selectedProject) return;
    const browserEndpoint = selectedFrontendEndpoint || selectedApiEndpoint;
    if (!browserEndpoint?.base_url && !selectedProject.base_url) {
      setMessage("Add a frontend URL to run browser checks.");
      return;
    }
    await runTask("browserCheck", async () => {
      const result = await apiRequest(`/projects/${selectedProject.project_id}/checks/browser`, {
        method: "POST",
        body: JSON.stringify({
          endpoint_id: browserEndpoint?.endpoint_id || null,
          path: "/",
          expected_text: null,
          expected_selector: null,
          timeout_seconds: 15,
          label: "Homepage browser smoke",
          browser_mode: "playwright",
          wait_until: "networkidle",
        }),
      });
      setLatestCheck(result);
      setMessage(`Browser check ${result.status}: ${result.error_message || result.page_title || result.target_url}`);
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function runApiSmoke() {
    if (!selectedProject) return;
    const apiEndpoint = selectedApiEndpoint || selectedFrontendEndpoint;
    if (!apiEndpoint?.base_url && !selectedProject.base_url) {
      setMessage("Add a backend API URL to run API checks.");
      return;
    }
    await runTask("apiCheck", async () => {
      const result = await apiRequest(`/projects/${selectedProject.project_id}/checks/api`, {
        method: "POST",
        body: JSON.stringify({
          endpoint_id: apiEndpoint?.endpoint_id || null,
          method: "GET",
          path: apiEndpoint?.healthcheck_path || selectedProject.healthcheck_path || "/health",
          expected_status: 200,
          timeout_seconds: 10,
          headers: {},
          body: null,
          label: "Health API smoke",
        }),
      });
      setLatestCheck(result);
      setMessage(`API check ${result.status}: ${result.error_message || result.target_url}`);
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function runPredeployGate() {
    if (!selectedProject) return;
    await runTask("predeploy", async () => {
      const result = await apiRequest(`/projects/${selectedProject.project_id}/testing/predeploy`, { method: "POST" });
      setPredeployResult(result);
      setMessage(result.summary || (result.release_ready ? "Predeploy gate passed." : "Predeploy gate blocked release."));
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function createAnalyzeExecuteStory(event) {
    event.preventDefault();
    if (!selectedProject) return;
    await runTask("story", async () => {
      const [story] = await apiRequest(`/projects/${selectedProject.project_id}/stories`, {
        method: "POST",
        body: JSON.stringify({
          stories: [
              {
                ...buildStoryDraft(),
              },
          ],
        }),
      });
      const analyzed = await apiRequest(`/stories/${story.story_id}/analyze`, { method: "POST" });
      const plan = await apiRequest(`/stories/${story.story_id}/frontend-plan`);
      const result = await apiRequest(`/stories/${story.story_id}/execute`, { method: "POST" });
      setLatestStory({ story: analyzed, plan, result });
      setMessage(`Story executed: ${result.summary}`);
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function importBulkStories() {
    if (!selectedProject) return;
    await runTask("bulkStories", async () => {
      const parsedStories = parseBulkStories(bulkStoryInput);
      await apiRequest(`/projects/${selectedProject.project_id}/stories`, {
        method: "POST",
        body: JSON.stringify({ stories: parsedStories }),
      });
      const result = await apiRequest(`/projects/${selectedProject.project_id}/testing/predeploy`, { method: "POST" });
      setPredeployResult(result);
      setMessage(`Imported ${parsedStories.length} test case(s). ${result.summary}`);
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function ingestBulkLogs() {
    if (!selectedProject) return;
    await runTask("bulkLogs", async () => {
      const entries = parseBulkLogs(bulkLogInput);
      await apiRequest(`/projects/${selectedProject.project_id}/logs`, {
        method: "POST",
        body: JSON.stringify({ entries }),
      });
      setMessage(`Connected ${entries.length} log entr${entries.length === 1 ? "y" : "ies"} to the project.`);
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function ingestSampleMetrics() {
    if (!selectedProject) return;
    await runTask("metrics", async () => {
      const now = new Date().toISOString();
      const baselineLatency = 180 + Math.round(Math.random() * 120);
      const baselineErrorRate = Number((Math.random() * 0.08).toFixed(4));
      const baselineAvailability = Number((99.2 + Math.random() * 0.7).toFixed(2));
      const points = [
        {
          timestamp: now,
          name: "latency_ms",
          value: baselineLatency,
          unit: "ms",
          source: "demo",
          dimensions: { service: "web" },
        },
        {
          timestamp: now,
          name: "error_rate",
          value: baselineErrorRate,
          unit: "ratio",
          source: "demo",
          dimensions: { service: "api" },
        },
        {
          timestamp: now,
          name: "availability_percent",
          value: baselineAvailability,
          unit: "%",
          source: "demo",
          dimensions: { service: "platform" },
        },
      ];
      await apiRequest(`/projects/${selectedProject.project_id}/metrics`, {
        method: "POST",
        body: JSON.stringify({ points }),
      });
      setMessage(`Connected ${points.length} metric point${points.length === 1 ? "" : "s"} to the project.`);
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function saveLogConnector() {
    if (!selectedProject) return;
    await runTask("logConnector", async () => {
      await apiRequest(`/projects/${selectedProject.project_id}/logs/connector`, {
        method: "PUT",
        body: JSON.stringify({
          url: logConnectorForm.url.trim(),
          method: logConnectorForm.method,
          headers: {},
          enabled: logConnectorForm.enabled,
          format: logConnectorForm.format,
          entries_path: logConnectorForm.entries_path.trim() || null,
          level_field: "level",
          source_field: "source",
          message_field: "message",
          timestamp_field: "timestamp",
        }),
      });
      setMessage("Log connector saved.");
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function pullConnectedLogs() {
    if (!selectedProject) return;
    await runTask("pullLogs", async () => {
      const result = await apiRequest(`/projects/${selectedProject.project_id}/logs/connector/pull`, {
        method: "POST",
        body: JSON.stringify({ limit: 100 }),
      });
      setMessage(result.summary || result.error_message || "Log pull finished.");
      await refreshSummary(selectedProject.project_id);
    });
  }

  async function runMissionControl() {
    if (!selectedProject) return;
    await runTask("mission", async () => {
      const steps = [];

      if (selectedProject.repository_url) {
        try {
          await apiRequest(`/projects/${selectedProject.project_id}/testing/environment`, {
            method: "PUT",
            body: JSON.stringify({
              repository_url: selectedProject.repository_url,
              branch: "main",
              install_command: "npm install",
              test_command: "npm test",
              workdir: "",
              enabled: true,
              shell: "powershell",
              env: {},
            }),
          });
          await apiRequest(`/projects/${selectedProject.project_id}/testing/environment/run`, {
            method: "POST",
            body: JSON.stringify({ pull_latest: true, run_install: false, run_tests: false, timeout_seconds: 300 }),
          });
          steps.push("workspace ready");
        } catch (error) {
          steps.push(`workspace issue: ${error.message}`);
        }

        try {
          const discovery = await apiRequest(`/projects/${selectedProject.project_id}/frontend/discover`);
          setFrontendDiscovery(discovery);
          steps.push(`frontend ${discovery.routes?.length || 0} route(s)`);
        } catch (error) {
          steps.push(`frontend discovery issue: ${error.message}`);
        }
      }

      if (bulkStoryInput.trim()) {
        try {
          const parsedStories = parseBulkStories(bulkStoryInput);
          await apiRequest(`/projects/${selectedProject.project_id}/stories`, {
            method: "POST",
            body: JSON.stringify({ stories: parsedStories }),
          });
          const predeploy = await apiRequest(`/projects/${selectedProject.project_id}/testing/predeploy`, { method: "POST" });
          setPredeployResult(predeploy);
          steps.push(`stories ${parsedStories.length} imported`);
        } catch (error) {
          steps.push(`story run issue: ${error.message}`);
        }
      }

      if (projectSummaryHasConnector(summary)) {
        try {
          const pullResult = await apiRequest(`/projects/${selectedProject.project_id}/logs/connector/pull`, {
            method: "POST",
            body: JSON.stringify({ limit: 100 }),
          });
          steps.push(pullResult.summary);
        } catch (error) {
          steps.push(`log pull issue: ${error.message}`);
        }
      } else if (bulkLogInput.trim()) {
        try {
          const entries = parseBulkLogs(bulkLogInput);
          await apiRequest(`/projects/${selectedProject.project_id}/logs`, {
            method: "POST",
            body: JSON.stringify({ entries }),
          });
          steps.push(`logs ${entries.length} connected`);
        } catch (error) {
          steps.push(`log issue: ${error.message}`);
        }
      }

      try {
        const now = new Date().toISOString();
        await apiRequest(`/projects/${selectedProject.project_id}/metrics`, {
          method: "POST",
          body: JSON.stringify({
            points: [
              {
                timestamp: now,
                name: "latency_ms",
                value: 220,
                unit: "ms",
                source: "mission",
                dimensions: { phase: "smoke" },
              },
              {
                timestamp: now,
                name: "error_rate",
                value: 0.03,
                unit: "ratio",
                source: "mission",
                dimensions: { phase: "smoke" },
              },
            ],
          }),
        });
        steps.push("metrics connected");
      } catch (error) {
        steps.push(`metrics issue: ${error.message}`);
      }

      const healthEndpoint = selectedApiEndpoint || selectedFrontendEndpoint;
      if (healthEndpoint?.base_url || selectedProject.base_url) {
        try {
          await apiRequest(`/projects/${selectedProject.project_id}/monitor/check`, { method: "POST" });
          steps.push("health checked");
        } catch (error) {
          steps.push(`health issue: ${error.message}`);
        }

        try {
          const browser = await apiRequest(`/projects/${selectedProject.project_id}/checks/browser`, {
            method: "POST",
            body: JSON.stringify({
              endpoint_id: (selectedFrontendEndpoint || selectedApiEndpoint)?.endpoint_id || null,
              path: "/",
              expected_text: null,
              expected_selector: null,
              timeout_seconds: 15,
              label: "Homepage browser smoke",
              browser_mode: "playwright",
              wait_until: "networkidle",
            }),
          });
          setLatestCheck(browser);
          steps.push(`browser ${browser.status}`);
        } catch (error) {
          steps.push(`browser issue: ${error.message}`);
        }

        try {
          const api = await apiRequest(`/projects/${selectedProject.project_id}/checks/api`, {
            method: "POST",
            body: JSON.stringify({
              endpoint_id: (selectedApiEndpoint || selectedFrontendEndpoint)?.endpoint_id || null,
              method: "GET",
              path: (selectedApiEndpoint || selectedFrontendEndpoint)?.healthcheck_path || selectedProject.healthcheck_path || "/health",
              expected_status: 200,
              timeout_seconds: 10,
              headers: {},
              body: null,
              label: "Health API smoke",
            }),
          });
          setLatestCheck(api);
          steps.push(`api ${api.status}`);
        } catch (error) {
          steps.push(`api issue: ${error.message}`);
        }
      }

      await refreshSummary(selectedProject.project_id);

      const currentRuns = await apiRequest(`/runs?project_id=${selectedProject.project_id}`).catch(() => []);
      const openRun = currentRuns.find((run) => run.status !== "resolved");
      if (openRun) {
        try {
          const triage = await apiRequest(`/runs/${openRun.run_id}/triage`, { method: "POST" });
          steps.push(`triage ${triage.confidence}`);
        } catch (error) {
          steps.push(`triage issue: ${error.message}`);
        }
      }

      await refreshSummary(selectedProject.project_id);
      setMessage(`Mission run complete: ${steps.join(" | ")}`);
    });
  }

  async function triageFirstIncident() {
    const run = activeRuns[0];
    if (!run) {
      setMessage("No active incident to triage.");
      return;
    }
    await runTask("triage", async () => {
      const result = await apiRequest(`/runs/${run.run_id}/triage`, { method: "POST" });
      setMessage(`Triage: ${result.summary}`);
      await refreshSummary(selectedProjectId);
    });
  }

  async function launchDemoFlow() {
    if (!selectedProject) return;
    await runTask("demoFlow", async () => {
      if (!stories.length) {
        await apiRequest(`/projects/${selectedProject.project_id}/stories`, {
          method: "POST",
          body: JSON.stringify({ stories: [buildStoryDraft()] }),
        });
      }

      if (!environmentSummary?.workspace_ready && selectedProject.repository_url) {
        try {
          await apiRequest(`/projects/${selectedProject.project_id}/testing/environment`, {
            method: "PUT",
            body: JSON.stringify({
              repository_url: selectedProject.repository_url,
              branch: "main",
              install_command: "npm install",
              test_command: "npm test",
              workdir: "",
              enabled: true,
              shell: "powershell",
              env: {},
            }),
          });
          await apiRequest(`/projects/${selectedProject.project_id}/testing/environment/run`, {
            method: "POST",
            body: JSON.stringify({ pull_latest: true, run_install: false, run_tests: false, timeout_seconds: 300 }),
          });
        } catch {
          // Keep the demo path resilient; mission control will surface remaining issues.
        }
      }

      await runMissionControl();
      await refreshSummary(selectedProject.project_id);
      setStageView("execution");
      setMessage("Demo flow completed. Review execution, evidence, and training tabs.");
    });
  }

  async function createAccount(event) {
    event.preventDefault();
    const email = accountForm.email.trim();
    const password = accountForm.password;
    const name = accountForm.name.trim();
    const team = accountForm.team.trim();
    if (!email || !password) {
      setMessage("Email and password are required.");
      return;
    }

    await runTask("account", async () => {
      let loginResponse = null;
      try {
        loginResponse = await apiRequest(
          "/auth/login",
          {
            method: "POST",
            body: JSON.stringify({ email, password }),
            skipAuth: true,
          },
        );
      } catch {
        await apiRequest(
          "/auth/register",
          {
            method: "POST",
            body: JSON.stringify({ name: name || email.split("@")[0], email, password, team }),
            skipAuth: true,
          },
        );
        loginResponse = await apiRequest(
          "/auth/login",
          {
            method: "POST",
            body: JSON.stringify({ email, password }),
            skipAuth: true,
          },
        );
      }

      setAuthToken(loginResponse.token);
      setAccount(loginResponse.account);
      await loadProjects();
      setDashboardOpen(false);
      setMessage(`Welcome ${loginResponse.account.name}. Create a project to open the command center.`);
    });
  }

  async function signOut() {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } catch {
      // Ignore logout failures during local development.
    }
    clearAuthToken();
    setAccount(null);
    setDashboardOpen(false);
    setSelectedProjectId(null);
    setSummary(null);
    setPlannerSummary(null);
    setEnvironmentSummary(null);
    setTrainingDatasets({});
    setFrontendDiscovery(null);
    setStories([]);
    setLogs([]);
    setLogSummary(null);
    setProjects([]);
    setMessage("Signed out. Sign in again to continue.");
  }

  async function openSelectedProject() {
    if (!account) {
      setMessage("Sign in first.");
      return;
    }
    if (!selectedProjectId) {
      setMessage("Select a project first.");
      return;
    }
    await refreshSummary(selectedProjectId);
    setDashboardOpen(true);
    setStageView("overview");
  }

  useEffect(() => {
    const bootstrap = async () => {
      checkHealth();
      const token = getAuthToken();
      if (!token) {
        setAccount(null);
        return;
      }
      try {
        const me = await apiRequest("/auth/me");
        setAccount(me);
      } catch {
        clearAuthToken();
        setAccount(null);
      }
      await loadProjects();
    };

    void bootstrap();
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      refreshSummary(selectedProjectId);
    }
  }, [selectedProjectId]);

  if (!account || !dashboardOpen || !selectedProject) {
    return (
      <ProjectLaunch
        apiHealth={apiHealth}
        account={account}
        accountForm={accountForm}
        setAccountForm={setAccountForm}
        createAccount={createAccount}
        signOut={signOut}
        projectForm={projectForm}
        setProjectForm={setProjectForm}
        projects={projects}
        selectedProjectId={selectedProjectId}
        setSelectedProjectId={setSelectedProjectId}
        openSelectedProject={openSelectedProject}
        createProject={createProject}
        busy={busy}
        message={message}
        loadDemoProjectTemplate={loadDemoProjectTemplate}
      />
    );
  }

  return (
    <div className="ox-shell">
      <div className="ox-scanlines" />
      <div className="ox-vignette" />
      <AgentScene agents={agents} selectedRole={selectedRole} onSelectRole={setSelectedRole} />
      <Topbar
        apiHealth={apiHealth}
        activeIncidentCount={activeRuns.length}
        clock={clock}
        account={account}
        selectedProject={selectedProject}
        summary={summary}
        stageView={stageView}
        setStageView={setStageView}
      />
      <Sidebar
        agents={agents}
        selectedRole={selectedRole}
        setSelectedRole={setSelectedRole}
        selectedProject={selectedProject}
        summary={summary}
        projectForm={projectForm}
        setProjectForm={setProjectForm}
        createProject={createProject}
        busy={busy}
        projects={projects}
        selectedProjectId={selectedProjectId}
        setSelectedProjectId={setSelectedProjectId}
        recentEvents={recentEvents}
        openSelectedProject={openSelectedProject}
        launchDemoFlow={launchDemoFlow}
      />
      <MainStage
        selectedProject={selectedProject}
        activeRuns={activeRuns}
        latestStory={latestStory}
        metricCards={metricCards}
        summary={summary}
        plannerSummary={plannerSummary}
        environmentSummary={environmentSummary}
        trainingDatasets={trainingDatasets}
        stageView={stageView}
        setStageView={setStageView}
        logs={logs}
        logSummary={logSummary}
        recentEvents={recentEvents}
        frontendDiscovery={frontendDiscovery}
        latestCheck={latestCheck || summary?.latest_check}
        predeployResult={predeployResult}
        handoffs={handoffs}
        conversations={conversations}
        pullWorkspace={pullWorkspace}
        discoverFrontend={discoverFrontend}
        runHealthCheck={runHealthCheck}
        runBrowserSmoke={runBrowserSmoke}
        runApiSmoke={runApiSmoke}
        runPredeployGate={runPredeployGate}
        runMissionControl={runMissionControl}
        triageFirstIncident={triageFirstIncident}
        busy={busy}
        launchDemoFlow={launchDemoFlow}
      />
      <RightPanel
        selectedAgent={selectedAgent}
        storyForm={storyForm}
        setStoryForm={setStoryForm}
        createAnalyzeExecuteStory={createAnalyzeExecuteStory}
        selectedProject={selectedProject}
        busy={busy}
        frontendDiscovery={frontendDiscovery}
        latestStory={latestStory}
        stories={stories}
        logs={logs}
        logSummary={logSummary}
        logConnectorForm={logConnectorForm}
        setLogConnectorForm={setLogConnectorForm}
        bulkStoryInput={bulkStoryInput}
        setBulkStoryInput={setBulkStoryInput}
        bulkLogInput={bulkLogInput}
        setBulkLogInput={setBulkLogInput}
        importBulkStories={importBulkStories}
        ingestBulkLogs={ingestBulkLogs}
        saveLogConnector={saveLogConnector}
        pullConnectedLogs={pullConnectedLogs}
        projectSummary={summary}
        plannerSummary={plannerSummary}
        environmentSummary={environmentSummary}
        trainingDatasets={trainingDatasets}
        message={message}
        applyStoryTemplate={applyStoryTemplate}
        ingestSampleMetrics={ingestSampleMetrics}
      />
    </div>
  );
}
