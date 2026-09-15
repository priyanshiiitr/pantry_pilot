import { Link } from "react-router-dom";

import { apiGet } from "../../api.js";
import Layout from "../../components/Layout.jsx";
import { usePolling } from "../../hooks/usePolling.js";

// Colour-code by what kind of thing happened, so the timeline is scannable at a glance.
const EVENT_LABELS = {
  tool_call: "Tool call",
  tool_result: "Tool result",
  reasoning: "Reasoning",
  decision: "Decision",
  interrupt: "Interrupt",
  resumed: "Resumed",
  error: "Error",
};

/** ActivityLog — a readable timeline of every tool call, result and decision the agents made. */
export default function ActivityLog() {
  const { data: entries, error } = usePolling(() => apiGet("/api/admin/activity"), 3000, []);

  return (
    <Layout title="Agent activity">
      <p>
        <Link to="/admin">← Back to dashboard</Link>
      </p>
      <p className="muted">
        Every tool an agent called, what it got back, and the reasoning behind its decisions — this is the
        proof that real reasoning is happening, not a hardcoded rule engine.
      </p>

      {error && <p className="error-text">{error}</p>}
      {!entries ? (
        <p className="status">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="muted">No agent activity yet. Try running a script like scripts/try_matching.py.</p>
      ) : (
        <ul className="activity-timeline">
          {entries.map((entry) => (
            <li key={entry.id} className={`activity-entry activity-${entry.event_type}`}>
              <div className="activity-entry-header">
                <span className="activity-event-type">{EVENT_LABELS[entry.event_type] ?? entry.event_type}</span>
                <span className="muted">{entry.agent_name}</span>
                {entry.offer_id && <span className="muted">offer #{entry.offer_id}</span>}
                <span className="muted activity-time">{new Date(entry.created_at).toLocaleTimeString()}</span>
              </div>
              <p className="activity-summary">{entry.summary}</p>
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}
