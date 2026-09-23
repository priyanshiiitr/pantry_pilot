import { useState } from "react";
import { Link } from "react-router-dom";

import { apiGet } from "../../api.js";
import AppShell from "../../components/AppShell.jsx";
import { usePolling } from "../../hooks/usePolling.js";

// The React app's api.js has no apiDelete helper (nothing else needed one yet) —
// this is the one place we build the DELETE call ourselves.
async function deleteFact(factId) {
  const response = await fetch(`/api/admin/memory/${factId}`, { method: "DELETE", credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Request failed (${response.status}).`);
  }
}

const SUBJECT_LABELS = { pantry: "Pantry", driver: "Driver", restaurant: "Restaurant" };

/** AgentMemory — what the agents remember long-term, with the ability to remove a fact. */
export default function AgentMemory() {
  const { data: facts, error } = usePolling(() => apiGet("/api/admin/memory"), 5000, []);
  const [removedIds, setRemovedIds] = useState(() => new Set());
  const [deleteError, setDeleteError] = useState(null);

  async function handleDelete(factId) {
    setDeleteError(null);
    try {
      await deleteFact(factId);
      setRemovedIds((previous) => new Set(previous).add(factId));
    } catch (err) {
      setDeleteError(err.message);
    }
  }

  const visibleFacts = (facts ?? []).filter((fact) => !removedIds.has(fact.id));

  return (
    <AppShell title="What the agent remembers">
      <p>
        <Link to="/admin">← Back to dashboard</Link>
      </p>
      <p className="muted">
        Long-term facts the agents have recorded about a pantry, driver or restaurant — remembered across
        every future offer until removed here.
      </p>

      {error && <p className="error-text">{error}</p>}
      {deleteError && <p className="error-text">{deleteError}</p>}
      {!facts ? (
        <p className="status">Loading…</p>
      ) : visibleFacts.length === 0 ? (
        <p className="muted">Nothing remembered yet.</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Subject</th>
              <th>Fact</th>
              <th>Source</th>
              <th>Remembered</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {visibleFacts.map((fact) => (
              <tr key={fact.id}>
                <td>
                  {SUBJECT_LABELS[fact.subject_type] ?? fact.subject_type}: {fact.subject_name}
                </td>
                <td>{fact.fact}</td>
                <td>{fact.source}</td>
                <td>{new Date(fact.created_at).toLocaleDateString()}</td>
                <td>
                  <button className="button button-danger button-small" onClick={() => handleDelete(fact.id)}>
                    Forget
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </AppShell>
  );
}
