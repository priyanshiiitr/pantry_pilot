import { Fragment } from "react";
import { Link, useParams } from "react-router-dom";

import { apiGet } from "../../api.js";
import Layout from "../../components/Layout.jsx";
import StatusBadge from "../../components/StatusBadge.jsx";
import { usePolling } from "../../hooks/usePolling.js";

/** Render one profile field value in a readable way, whatever shape it is. */
function formatValue(value) {
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : "none";
  if (value && typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

/** UserDetail — one user's profile fields plus their recent activity. */
export default function UserDetail() {
  const { userId } = useParams();
  const { data: user, error } = usePolling(() => apiGet(`/api/admin/users/${userId}`), 5000, [userId]);

  return (
    <Layout title="User detail">
      <p>
        <Link to="/admin/users">← Back to all users</Link>
      </p>

      {error && <p className="error-text">{error}</p>}
      {!user ? (
        <p className="status">Loading…</p>
      ) : (
        <>
          <h2>
            {user.display_name} <span className="muted">({user.role})</span>
          </h2>
          <p className="muted">{user.email}</p>

          {Object.keys(user.profile).length > 0 && (
            <section className="card">
              <h3>Profile</h3>
              <dl className="detail-list">
                {Object.entries(user.profile).map(([key, value]) => (
                  <Fragment key={key}>
                    <dt>{key.replaceAll("_", " ")}</dt>
                    <dd>{formatValue(value)}</dd>
                  </Fragment>
                ))}
              </dl>
            </section>
          )}

          <h3>Recent activity</h3>
          {user.recent_activity.length === 0 ? (
            <p className="muted">No recent activity yet.</p>
          ) : (
            <ul className="offer-list">
              {user.recent_activity.map((item, index) => (
                <li key={index} className="offer-row">
                  <span className="offer-row-title">{item.title}</span>
                  <StatusBadge status={item.status} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Layout>
  );
}
