const NAV_ITEMS = [
  ["overview", "Overview"],
  ["execution", "Execution"],
  ["evidence", "Evidence"],
  ["training", "Training"],
];

export function Topbar({ apiHealth, activeIncidentCount, clock, account, selectedProject, summary, stageView, setStageView }) {
  const latestHealth = summary?.latest_health;
  const latestCheck = summary?.latest_check;
  const projectState = selectedProject?.name || "No project";
  const projectSignal = latestHealth?.status || latestCheck?.status || "idle";

  return (
    <header className="ox-topbar">
      <div className="ox-logo">
        <span className="ox-logo-hex">OI</span>
        <strong>Open<span>Incident</span> X</strong>
        <em>3D CMD</em>
      </div>
      <nav>
        {NAV_ITEMS.map(([key, label]) => (
          <button className={stageView === key ? "active" : ""} key={key} onClick={() => setStageView(key)} type="button">
            {label}
          </button>
        ))}
      </nav>
      <div className="ox-top-right">
        <span className="ox-project-pill">
          <strong>{projectState}</strong>
          <em>{projectSignal}</em>
        </span>
        {account ? <span className="ox-operator">{account.name}</span> : null}
        <span className={`ox-api ${apiHealth}`}>API {apiHealth}</span>
        <span className="ox-alert"><i />{activeIncidentCount} ACTIVE INCIDENTS</span>
        <span>{clock.toUTCString().slice(17, 25)} UTC</span>
      </div>
    </header>
  );
}
