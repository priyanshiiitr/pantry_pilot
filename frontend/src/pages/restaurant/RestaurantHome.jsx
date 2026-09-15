import { Link } from "react-router-dom";

import { apiGet } from "../../api.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import Layout from "../../components/Layout.jsx";
import StatusBadge from "../../components/StatusBadge.jsx";
import { usePolling } from "../../hooks/usePolling.js";

/** RestaurantHome — list of this restaurant's own offers, refreshed every few seconds. */
export default function RestaurantHome() {
  const { user } = useAuth();
  const { data: offers, error } = usePolling(() => apiGet("/api/restaurant/offers"), 3000, []);

  return (
    <Layout title="Restaurant dashboard">
      <div className="actions">
        <Link className="button" to="/restaurant/offers/new">
          Post surplus food
        </Link>
        <Link className="button button-secondary" to="/restaurant/profile">
          Edit profile
        </Link>
      </div>

      <h2>Your offers</h2>
      {error && <p className="error-text">{error}</p>}
      {!offers ? (
        <p className="status">Loading…</p>
      ) : offers.length === 0 ? (
        <p className="muted">
          Welcome, {user.display_name}. You haven't posted anything yet — try "Post surplus food" above.
        </p>
      ) : (
        <ul className="offer-list">
          {offers.map((offer) => (
            <li key={offer.id} className="offer-row">
              <Link to={`/restaurant/offers/${offer.id}`} className="offer-row-title">
                {offer.title}
              </Link>
              <span className="muted">{offer.quantity_text}</span>
              <StatusBadge status={offer.status} />
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}
