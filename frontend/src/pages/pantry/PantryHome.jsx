import { Link } from "react-router-dom";

import { apiGet, apiPost } from "../../api.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import DeclineButton from "../../components/DeclineButton.jsx";
import AppShell from "../../components/AppShell.jsx";
import { usePolling } from "../../hooks/usePolling.js";

/** PantryHome — incoming deliveries the agent has assigned, with Accept/Decline. */
export default function PantryHome() {
  const { user } = useAuth();
  const { data: deliveries, error } = usePolling(() => apiGet("/api/pantry/deliveries"), 3000, []);

  async function handleAccept(deliveryId) {
    await apiPost(`/api/pantry/deliveries/${deliveryId}/accept`);
  }

  async function handleDecline(deliveryId, reason) {
    await apiPost(`/api/pantry/deliveries/${deliveryId}/decline`, { reason });
  }

  return (
    <AppShell title="Pantry dashboard">
      <p className="muted">Welcome, {user.display_name}.</p>
      <p>
        <Link to="/pantry/profile">Edit your profile →</Link>
      </p>

      <h2>Incoming deliveries</h2>
      {error && <p className="error-text">{error}</p>}
      {!deliveries ? (
        <p className="status">Loading…</p>
      ) : deliveries.length === 0 ? (
        <p className="muted">Nothing waiting on you right now.</p>
      ) : (
        <ul className="delivery-list">
          {deliveries.map((delivery) => (
            <li key={delivery.id} className="delivery-card">
              <div className="delivery-card-header">
                <strong>{delivery.offer_title}</strong>
                <span className="muted">from {delivery.restaurant_name}</span>
              </div>
              <p className="muted">{delivery.quantity_text}</p>
              {delivery.match_reasoning && (
                <p className="agent-reason">
                  <span className="agent-reason-label">Why you:</span> {delivery.match_reasoning}
                </p>
              )}
              <div className="actions">
                <button className="button button-small" onClick={() => handleAccept(delivery.id)}>
                  Accept
                </button>
                <DeclineButton onDecline={(reason) => handleDecline(delivery.id, reason)} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
