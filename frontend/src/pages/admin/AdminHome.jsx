import { Link } from "react-router-dom";

import { apiGet } from "../../api.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import Layout from "../../components/Layout.jsx";
import StatusBadge from "../../components/StatusBadge.jsx";
import { usePolling } from "../../hooks/usePolling.js";

/** AdminHome — a basic list of every offer in the system. The full dashboard arrives in Step 12. */
export default function AdminHome() {
  const { user } = useAuth();
  const { data: offers, error } = usePolling(() => apiGet("/api/admin/offers"), 3000, []);

  return (
    <Layout title="Admin dashboard">
      <p className="muted">
        Welcome, {user.display_name}. The overview and Decisions inbox arrive in Steps 11–12 — for now,
        here is every offer in the system.
      </p>
      <p>
        <Link to="/admin/activity">View agent activity log →</Link>
      </p>

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
