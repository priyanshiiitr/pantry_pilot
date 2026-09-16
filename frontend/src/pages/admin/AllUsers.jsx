import { Link } from "react-router-dom";

import { apiGet } from "../../api.js";
import Layout from "../../components/Layout.jsx";
import { usePolling } from "../../hooks/usePolling.js";

const ROLE_LABELS = { restaurant: "Restaurant", pantry: "Pantry", driver: "Driver", admin: "Admin" };

/** AllUsers — every restaurant, pantry, driver and admin account, with a link to each detail page. */
export default function AllUsers() {
  const { data: users, error } = usePolling(() => apiGet("/api/admin/users"), 5000, []);

  return (
    <Layout title="All users">
      <p>
        <Link to="/admin">← Back to dashboard</Link>
      </p>

      {error && <p className="error-text">{error}</p>}
      {!users ? (
        <p className="status">Loading…</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Email</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.display_name}</td>
                <td>{ROLE_LABELS[user.role] ?? user.role}</td>
                <td>{user.email}</td>
                <td>{user.status_label}</td>
                <td>
                  <Link to={`/admin/users/${user.id}`}>View →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Layout>
  );
}
