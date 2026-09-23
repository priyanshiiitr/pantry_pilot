import { Fragment } from "react";
import { Link } from "react-router-dom";

import { apiGet } from "../../api.js";
import AppShell from "../../components/AppShell.jsx";
import StatusBadge from "../../components/StatusBadge.jsx";
import { usePolling } from "../../hooks/usePolling.js";

// The five stages of the pipeline, in the order food actually moves through it
// (see docs/architecture.md). `key` matches a count from GET /api/admin/overview.
const PIPELINE_STAGES = [
  { key: "restaurants_posting", name: "Restaurants", note: "posting offers", icon: "▦" },
  { key: "offers_being_evaluated", name: "Matching agent", note: "evaluating", icon: "◈", tone: "is-agent" },
  { key: "pantries_receiving_today", name: "Pantries", note: "receiving today", icon: "⌂" },
  { key: "drivers_en_route", name: "Dispatch agent", note: "drivers en route", icon: "⛟", tone: "is-amber" },
  { key: "drivers_on_duty", name: "Volunteers", note: "active drivers", icon: "◍" },
];

const FEED_ICONS = {
  offer_posted: { icon: "▦", tone: "" },
  matched: { icon: "◈", tone: "is-agent" },
  delivered: { icon: "✓", tone: "" },
  needs_human: { icon: "⚑", tone: "is-amber" },
};

function formatTime(isoString) {
  return new Date(isoString).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatAge(isoString) {
  const minutes = Math.round((Date.now() - new Date(isoString)) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  return `${Math.round(hours / 24)} day${Math.round(hours / 24) === 1 ? "" : "s"} ago`;
}

/** A trend line like "↑ 12% from yesterday", or nothing when there's no honest comparison. */
function Trend({ change }) {
  if (change === null || change === undefined) {
    return <div className="stat-tile-trend">no change since yesterday</div>;
  }
  const isUp = change >= 0;
  return (
    <div className="stat-tile-trend">
      <span className={isUp ? "trend-up" : "trend-down"}>
        {isUp ? "↑" : "↓"} {Math.abs(change)}%
      </span>{" "}
      from yesterday
    </div>
  );
}

function StatTile({ icon, label, value, change, amber }) {
  return (
    <div className="stat-tile">
      <div className={amber ? "stat-tile-icon is-amber" : "stat-tile-icon"} aria-hidden="true">
        {icon}
      </div>
      <div style={{ minWidth: 0 }}>
        <div className="stat-tile-label">{label}</div>
        <div className="stat-tile-value">{value}</div>
        <Trend change={change} />
      </div>
    </div>
  );
}

/**
 * Overview — the admin's home screen: what the agent network is doing right now,
 * and anything waiting on a human.
 */
export default function Overview() {
  const { data, error } = usePolling(() => apiGet("/api/admin/overview"), 5000, []);

  const stats = data?.stats;
  const decisions = data?.pending_decisions ?? [];

  return (
    <AppShell>
      {error && <p className="error-text">{error}</p>}
      {!data ? (
        <p className="status">Loading…</p>
      ) : (
        <>
          <header className="overview-header">
            <div>
              <p className="overview-eyebrow">Welcome to PantryPilot</p>
              <h1>The network is moving food automatically.</h1>
              <p className="muted">
                AI agents are coordinating donations, pantries, and drivers — and only asking you when a real
                decision is needed.
              </p>
            </div>
            <div className="overview-date">
              {new Date().toLocaleDateString([], { weekday: "short", month: "short", day: "numeric", year: "numeric" })}
            </div>
          </header>

          <div className="stat-grid">
            <StatTile
              icon="▦"
              label="Active donations"
              value={stats.active_offers}
              change={stats.active_offers_change}
            />
            <StatTile
              icon="🍽"
              label="Meals being rescued"
              value={stats.meals_rescued}
              change={stats.meals_rescued_change}
            />
            <StatTile
              icon="✓"
              label="Successful matches"
              value={stats.match_rate === null ? "—" : `${stats.match_rate}%`}
              change={undefined}
            />
            <StatTile
              icon="⚑"
              label="Human decisions"
              value={stats.pending_decisions}
              change={stats.pending_decisions_change}
              amber
            />
          </div>

          <section className="panel" style={{ marginBottom: 20 }}>
            <div className="panel-header">
              <h2>Live network activity</h2>
              <span className="live-dot">{data.network.offers_being_evaluated} offers in progress</span>
            </div>
            <div className="pipeline">
              {PIPELINE_STAGES.map((stage, index) => (
                <Fragment key={stage.key}>
                  {index > 0 && (
                    <span className="pipeline-arrow" aria-hidden="true">
                      →
                    </span>
                  )}
                  <div className="pipeline-stage">
                    <div className={`pipeline-icon ${stage.tone ?? ""}`} aria-hidden="true">
                      {stage.icon}
                    </div>
                    <div className="pipeline-name">{stage.name}</div>
                    <div className="pipeline-count">{data.network[stage.key]}</div>
                    <div className="pipeline-note">{stage.note}</div>
                  </div>
                </Fragment>
              ))}
            </div>
          </section>

          <div className="overview-columns is-split">
            <section className="panel">
              <div className="panel-header">
                <h2>Recent activity</h2>
                <Link className="panel-link" to="/admin/activity">
                  View all →
                </Link>
              </div>
              {data.recent_activity.length === 0 ? (
                <p className="empty-note">
                  Nothing has happened yet. Post an offer as a restaurant and the agents will pick it up within 15
                  seconds.
                </p>
              ) : (
                <div className="feed">
                  {data.recent_activity.map((event) => {
                    const style = FEED_ICONS[event.kind] ?? FEED_ICONS.offer_posted;
                    return (
                      <div className="feed-row" key={`${event.kind}-${event.offer_id}-${event.at}`}>
                        <span className="feed-time">{formatTime(event.at)}</span>
                        <span className={`feed-icon ${style.tone}`} aria-hidden="true">
                          {style.icon}
                        </span>
                        <span className="feed-body">
                          <div className="feed-title">{event.title}</div>
                          <div className="feed-detail">{event.detail}</div>
                        </span>
                        <StatusBadge status={event.status} />
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="panel">
              <div className="panel-header">
                <h2>
                  Decisions need your attention{" "}
                  {decisions.length > 0 && <span className="sidebar-link-count">{decisions.length}</span>}
                </h2>
                <Link className="panel-link" to="/admin/decisions">
                  View all →
                </Link>
              </div>
              {decisions.length === 0 ? (
                <p className="empty-note">
                  Nothing needs you right now. The agents will raise a card here the moment they hit a call only a
                  person should make.
                </p>
              ) : (
                decisions.map((decision) => (
                  <article className="decision-mini" key={decision.id}>
                    <div className="decision-mini-head">
                      <span className="feed-icon is-amber" aria-hidden="true">
                        ⚑
                      </span>
                      <span className="decision-mini-title">{decision.card.title ?? "The agent needs a decision"}</span>
                      <span className="decision-mini-age">{formatAge(decision.created_at)}</span>
                    </div>
                    <p>{decision.card.situation ?? decision.card.reasoning ?? ""}</p>
                    <div className="pill-row">
                      <span className="pill">Offer #{decision.offer_id}</span>
                      <span className="pill">{decision.offer_title}</span>
                      {decision.card.urgency && <span className="pill pill-amber">{decision.card.urgency}</span>}
                      <Link className="button-accent" style={{ marginLeft: "auto" }} to="/admin/decisions">
                        Review decision →
                      </Link>
                    </div>
                  </article>
                ))
              )}
            </section>
          </div>
        </>
      )}
    </AppShell>
  );
}
