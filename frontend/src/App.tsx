import { useState } from "react";
import { RunList } from "./components/RunList";
import { RunView } from "./components/RunView";

export default function App() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const toggleTheme = () => {
    const root = document.documentElement;
    const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
    root.setAttribute("data-theme", next);
  };

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand" onClick={() => setSelectedRunId(null)} style={{ cursor: "pointer" }}>
          🔍 LensTrace <span className="dim">· traces</span>
        </span>
        <span className="spacer" />
        {selectedRunId && (
          <button className="btn ghost" onClick={() => setSelectedRunId(null)}>
            ← All runs
          </button>
        )}
        <button className="btn ghost" title="Toggle theme" onClick={toggleTheme}>
          ◐
        </button>
      </header>
      <main className="content">
        {selectedRunId === null ? (
          <RunList onSelect={setSelectedRunId} />
        ) : (
          <RunView runId={selectedRunId} onBack={() => setSelectedRunId(null)} />
        )}
      </main>
    </div>
  );
}
