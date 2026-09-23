import { Link, useParams } from "react-router-dom";

import { apiGet } from "../../api.js";
import AppShell from "../../components/AppShell.jsx";
import StatusBadge from "../../components/StatusBadge.jsx";
import { usePolling } from "../../hooks/usePolling.js";

// Shown until the agent team has written its own summary of what it did.
const WAITING_MESSAGES = {
  posted: "Waiting for the agent team to pick this up — usually within 15 seconds.",
  agent_working: "The agent team is working on this right now: reading the offer, then finding a pantry and a driver.",
  needs_human: "The agent team paused to ask a coordinator a question about this offer.",
};
const DEFAULT_WAITING_MESSAGE = "No update from the agent team yet.";

// The marker drawn against each stage, by its state (see services/progress.py).
const STAGE_MARKS = { done: "✓", active: "◍", blocked: "⚑", waiting: "○" };

/** OfferDetail — one offer's full details and live status, for the restaurant that posted it. */
export default function OfferDetail() {
  const { offerId } = useParams();
  const { data: offer, error } = usePolling(() => apiGet(`/api/restaurant/offers/${offerId}`), 3000, [offerId]);

  return (
    <AppShell title="Offer details">
      <p>
        <Link to="/restaurant">← Back to dashboard</Link>
      </p>
      {error && <p className="error-text">{error}</p>}
      {!offer ? (
        <p className="status">Loading…</p>
      ) : (
        <section className="card offer-detail">
          <div className="offer-detail-header">
            <h2>{offer.title}</h2>
            <StatusBadge status={offer.status} />
          </div>
          <dl className="detail-list">
            <dt>Quantity</dt>
            <dd>{offer.quantity_text}</dd>
            <dt>Description</dt>
            <dd>{offer.description}</dd>
            <dt>Allergen notes</dt>
            <dd>{offer.allergen_notes || "None given"}</dd>
            <dt>Must be collected by</dt>
            <dd>{new Date(offer.pickup_deadline).toLocaleString()}</dd>
            <dt>Posted</dt>
            <dd>{new Date(offer.created_at).toLocaleString()}</dd>
          </dl>
          <div className="agent-summary">
            <h3>Agent update</h3>
            <p className="muted">{offer.agent_summary ?? WAITING_MESSAGES[offer.status] ?? DEFAULT_WAITING_MESSAGE}</p>
          </div>
        </section>
      )}

      <AgentProgress offerId={offerId} status={offer?.status} />
    </AppShell>
  );
}

/**
 * AgentProgress — a live, plain-English trace of what the agents have done on
 * this offer.
 *
 * Without it the restaurant sees only an "Agent working…" badge, which is
 * indistinguishable from a crash when a run legitimately takes minutes.
 */
function AgentProgress({ offerId, status }) {
  const { data } = usePolling(() => apiGet(`/api/restaurant/offers/${offerId}/activity`), 3000, [offerId]);

  if (!data) return null;

  return (
    <>
      <section className="panel" style={{ marginTop: 20 }}>
        <div className="panel-header">
          <h2>Progress</h2>
          {status === "agent_working" && <span className="live-dot">agents working now</span>}
        </div>
        <ol className="stage-track">
          {data.stages.map((stage) => (
            <li className={`stage stage-${stage.state}`} key={stage.key}>
              <span className="stage-marker" aria-hidden="true">
                {STAGE_MARKS[stage.state]}
              </span>
              <span className="stage-body">
                <span className="stage-name">{stage.name}</span>
                <span className="stage-detail">{stage.detail}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>

      {data.entries.length > 0 && (
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="panel-header">
            <h2>What the agents did</h2>
          </div>
          <div className="feed">
            {data.entries.map((entry) => (
              <div className="feed-row" key={entry.id}>
                <span className="feed-time">{new Date(entry.created_at).toLocaleTimeString()}</span>
                <span className="feed-icon is-agent" aria-hidden="true">
                  ◈
                </span>
                <span className="feed-body">
                  <div className="feed-title">{entry.tool_name ?? entry.agent_name}</div>
                  <div className="feed-detail">{entry.summary}</div>
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
