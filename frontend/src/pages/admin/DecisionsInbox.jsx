import { useState } from "react";
import { Link } from "react-router-dom";

import { apiGet, apiPost } from "../../api.js";
import AppShell from "../../components/AppShell.jsx";
import { usePolling } from "../../hooks/usePolling.js";

// Keep in sync with the urgency values the ask_admin tool can send
// (agents/tools/human_tools.py) — anything unrecognized falls back to grey.
const URGENCY_COLORS = { high: "bad", medium: "amber", low: "grey" };

/** One decision card: the agent's question, its options, and a way to answer. */
function DecisionCard({ decision, onAnswered }) {
  const [selectedOption, setSelectedOption] = useState(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const card = decision.card;
  const options = card.options ?? [];

  async function handleSubmit() {
    if (!selectedOption) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiPost(`/api/admin/decisions/${decision.id}/answer`, {
        chosen_option: selectedOption,
        admin_note: note.trim() || null,
      });
      onAnswered(decision.id);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <li className={`decision-card urgency-border-${URGENCY_COLORS[card.urgency] ?? "grey"}`}>
      <div className="decision-card-header">
        <span className={`urgency-badge urgency-${URGENCY_COLORS[card.urgency] ?? "grey"}`}>
          {card.urgency ?? "unknown"} urgency
        </span>
        <span className="muted">
          Offer #{decision.offer_id}: {decision.offer_title} — {decision.restaurant_name}
        </span>
      </div>

      <h3 className="decision-title">{card.title}</h3>

      <div className="decision-section">
        <span className="decision-label">Situation</span>
        <p>{card.situation}</p>
      </div>
      <div className="decision-section">
        <span className="decision-label">Why the agent is asking</span>
        <p>{card.reasoning}</p>
      </div>
      {card.recommended_option && (
        <div className="decision-section decision-recommendation">
          <span className="decision-label">Agent's recommendation</span>
          <p>{card.recommended_option}</p>
        </div>
      )}

      <div className="decision-options">
        {options.map((option) => {
          const isRecommended = card.recommended_option?.startsWith(option.label);
          const isSelected = selectedOption === option.label;
          return (
            <button
              key={option.label}
              type="button"
              className={`decision-option${isSelected ? " decision-option-selected" : ""}`}
              onClick={() => setSelectedOption(option.label)}
            >
              <div className="decision-option-label">
                {option.label}
                {isRecommended && <span className="recommended-tag">Recommended</span>}
              </div>
              {option.consequence && <p className="muted decision-option-consequence">{option.consequence}</p>}
            </button>
          );
        })}
      </div>

      <label className="field">
        <span>Note (optional, shown to the agent when it resumes)</span>
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Any extra context for the agent…"
        />
      </label>

      {error && <p className="error-text">{error}</p>}
      <button className="button" onClick={handleSubmit} disabled={!selectedOption || submitting}>
        {submitting ? "Submitting…" : "Confirm decision"}
      </button>
    </li>
  );
}

/**
 * DecisionsInbox — the human-in-the-loop centerpiece. Every card here is a real
 * pause: the Coordinator agent hit a genuine judgment call, called its
 * ask_admin tool, and its whole reasoning process is frozen mid-conversation
 * until someone answers. Picking an option here doesn't just record a choice —
 * the worker resumes that exact paused conversation within a few seconds.
 */
export default function DecisionsInbox() {
  const { data: decisions, error } = usePolling(() => apiGet("/api/admin/decisions"), 3000, []);
  const [justAnswered, setJustAnswered] = useState(() => new Set());

  function handleAnswered(decisionId) {
    // Hide the card immediately rather than waiting for the next poll —
    // answering already happened; there's nothing left to show here.
    setJustAnswered((previous) => new Set(previous).add(decisionId));
  }

  const visibleDecisions = (decisions ?? []).filter((decision) => !justAnswered.has(decision.id));

  return (
    <AppShell title="Decisions inbox">
      <p>
        <Link to="/admin">← Back to dashboard</Link>
      </p>
      <p className="muted">
        The agent pauses here when it hits a genuine judgment call — pick an option and it resumes on its
        own within a few seconds.
      </p>

      {error && <p className="error-text">{error}</p>}
      {!decisions ? (
        <p className="status">Loading…</p>
      ) : visibleDecisions.length === 0 ? (
        <p className="muted">No decisions waiting right now.</p>
      ) : (
        <ul className="decisions-list">
          {visibleDecisions.map((decision) => (
            <DecisionCard key={decision.id} decision={decision} onAnswered={handleAnswered} />
          ))}
        </ul>
      )}
    </AppShell>
  );
}
