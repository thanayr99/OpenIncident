import { roleMeta } from "../data/agents";
import { formatPercent } from "../utils/format";

export function AgentCard({ agent, selected, onSelect }) {
  const meta = roleMeta(agent.role);
  const primaryMetric = agent.stories_validated || agent.completed_tasks || 0;
  const secondaryMetric = agent.incidents_triaged || agent.failed_tasks || 0;

  return (
    <button className={`agent-card ${selected ? "selected" : ""}`} onClick={() => onSelect(agent.role)} type="button">
      <span className="agent-avatar" style={{ borderColor: meta.color, background: `${meta.color}22` }}>
        {meta.emoji}
        <span className={`status-dot dot-${meta.status}`} />
      </span>
      <span className="agent-info">
        <strong>{agent.display_name || meta.name}</strong>
        <small>{agent.specialization || meta.role}</small>
        <span className="trust-row">
          <span className="trust-track">
            <span className="trust-fill" style={{ width: formatPercent(agent.trust_score), background: meta.color }} />
          </span>
          <em>{formatPercent(agent.trust_score)}</em>
        </span>
      </span>
      <span className="maturity-badge" style={{ color: meta.color, borderColor: `${meta.color}88` }}>
        {String(agent.maturity || "new").toUpperCase()}
      </span>
      <span className="agent-card-meta">
        <span>{primaryMetric} done</span>
        <span>{secondaryMetric} signals</span>
      </span>
    </button>
  );
}
