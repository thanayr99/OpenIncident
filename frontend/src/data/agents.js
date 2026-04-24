export const ROLE_META = {
  planner: { name: "Planner", role: "Strategic Architect", emoji: "N", color: "#7c4dff", three: 0x7c4dff, status: "idle" },
  frontend_tester: { name: "Frontend Tester", role: "UI Quality Inspector", emoji: "UI", color: "#00c896", three: 0x00c896, status: "idle" },
  api_tester: { name: "API Tester", role: "Backend Specialist", emoji: "API", color: "#00e5ff", three: 0x00e5ff, status: "active" },
  database_analyst: { name: "Database Agent", role: "Persistence Specialist", emoji: "DB", color: "#ffb300", three: 0xffb300, status: "idle" },
  reliability_analyst: { name: "Reliability Agent", role: "Incident Response", emoji: "RX", color: "#ff7043", three: 0xff7043, status: "alert" },
  test_env_guardian: { name: "Env Guardian", role: "Release Gatekeeper", emoji: "G", color: "#ff3d57", three: 0xff3d57, status: "blocking" },
  oversight: { name: "Oversight Agent", role: "Elite Auditor", emoji: "OX", color: "#e8edf5", three: 0x00e5ff, status: "idle" },
};

export const FALLBACK_AGENTS = Object.entries(ROLE_META).map(([role, meta]) => ({
  agent_id: role,
  role,
  display_name: meta.name,
  specialization: meta.role,
  maturity: role === "planner" || role === "oversight" ? "lead" : "operational",
  trust_score: role === "oversight" ? 0.98 : role === "test_env_guardian" ? 0.95 : 0.84,
  completed_tasks: 0,
  failed_tasks: 0,
  stories_validated: 0,
  incidents_triaged: 0,
  notes: [],
}));

export function roleMeta(role) {
  return ROLE_META[role] || { name: role || "Agent", role: "Agent", emoji: "AI", color: "#00e5ff", three: 0x00e5ff, status: "idle" };
}
