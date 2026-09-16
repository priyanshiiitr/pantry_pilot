import { Link } from "react-router-dom";

import { apiGet } from "../../api.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import Layout from "../../components/Layout.jsx";
import StatCard from "../../components/StatCard.jsx";
import StatusBadge from "../../components/StatusBadge.jsx";
import { usePolling } from "../../hooks/usePolling.js";

/** AdminHome — overview stat cards, quick links, and every offer in the system. */
export default function AdminHome() {
  const { user } = useAuth();
  const { data: stats } = usePolling(() => apiGet("/api/admin/stats"), 5000, []);
  const { data: offers, error } = usePolling(() => apiGet("/api/admin/offers"), 3000, []);
  const { data: decisions } = usePolling(() => apiGet("/api/admin/decisions"), 3000, []);
  const pendingCount = decisions?.length ?? 0;

  return (
    <Layout title="Admin dashboard">
      <p className="muted">Welcome, {user.display_name}.</p>

      {stats && (
        <div className="stat-cards">
          <StatCard label="Active offers" value={stats.active_offers} />
          <StatCard
            label="Pending decisions"
            value={stats.pending_decisions}
            accent={stats.pending_decisions > 0 ? "amber" : undefined}
          />
          <StatCard label="Completed today" value={stats.completed_today} accent="good" />
          <StatCard label="kg saved today" value={stats.kg_saved_today} />
          <StatCard label="Meals saved today" value={stats.meals_saved_today} />
          <StatCard label="kg saved (all time)" value={stats.kg_saved_total} />
        </div>
      )}

      <div className="actions">
        <Link to="/admin/decisions" className="button">
          Decisions inbox{pendingCount > 0 && <span className="inbox-count">{pendingCount}</span>}
        </Link>
        <Link to="/admin/activity" className="button button-secondary">
          Agent activity log
        </Link>
        <Link to="/admin/users" className="button button-secondary">
          All users
        </Link>
        <Link to="/admin/memory" className="button button-secondary">
          What the agent remembers
        </Link>
      </div>

      <h2>All offers</h2>

      {error && <p className="error-text">{error}</p>}
      {!offers ? (
        <p className="status">Loading…</p>
      ) : offers.length === 0 ? (
        <p className="muted">No offers have been posted yet.</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Restaurant</th>
              <th>Title</th>
              <th>Quantity</th>
              <th>Status</th>
              <th>Collect by</th>
            </tr>
          </thead>
          <tbody>
            {offers.map((offer) => (
              <tr key={offer.id}>
                <td>{offer.restaurant_name}</td>
                <td>{offer.title}</td>
                <td>{offer.quantity_text}</td>
                <td>
                  <StatusBadge status={offer.status} />
                </td>
                <td>{new Date(offer.pickup_deadline).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Layout>
  );
}
