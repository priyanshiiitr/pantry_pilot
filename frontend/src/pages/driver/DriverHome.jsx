import { Link } from "react-router-dom";

import { apiGet, apiPost } from "../../api.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import DeclineButton from "../../components/DeclineButton.jsx";
import Layout from "../../components/Layout.jsx";
import StatusBadge from "../../components/StatusBadge.jsx";
import { usePolling } from "../../hooks/usePolling.js";

/** DriverHome — pending pickup requests (accept/decline) and active trips (pickup/delivered). */
export default function DriverHome() {
  const { user } = useAuth();
  const { data: requests, error: requestsError } = usePolling(() => apiGet("/api/driver/dispatch-requests"), 3000, []);
  const { data: trips, error: tripsError } = usePolling(() => apiGet("/api/driver/trips"), 3000, []);

  async function handleAccept(requestId) {
    await apiPost(`/api/driver/dispatch-requests/${requestId}/accept`);
  }

  async function handleDecline(requestId, reason) {
    await apiPost(`/api/driver/dispatch-requests/${requestId}/decline`, { reason });
  }

  async function handlePickedUp(deliveryId) {
    await apiPost(`/api/driver/trips/${deliveryId}/picked-up`);
  }

  async function handleDelivered(deliveryId) {
    await apiPost(`/api/driver/trips/${deliveryId}/delivered`);
  }

  return (
    <Layout title="Driver dashboard">
      <p className="muted">Welcome, {user.display_name}.</p>
      <p>
        <Link to="/driver/profile">Edit your profile →</Link>
      </p>

      <h2>Pickup requests</h2>
      {requestsError && <p className="error-text">{requestsError}</p>}
      {!requests ? (
        <p className="status">Loading…</p>
      ) : requests.length === 0 ? (
        <p className="muted">No pending requests.</p>
      ) : (
        <ul className="delivery-list">
          {requests.map((request) => (
            <li key={request.id} className="delivery-card">
              <div className="delivery-card-header">
                <strong>{request.offer_title}</strong>
              </div>
              <p className="muted">
                Pickup: {request.restaurant_name} — {request.restaurant_address}
              </p>
              <p className="muted">
                Drop-off: {request.pantry_name} — {request.pantry_address}
              </p>
              {request.dispatch_reasoning && (
                <p className="agent-reason">
                  <span className="agent-reason-label">Why you:</span> {request.dispatch_reasoning}
                </p>
              )}
              <div className="actions">
                <button className="button button-small" onClick={() => handleAccept(request.id)}>
                  Accept
                </button>
                <DeclineButton onDecline={(reason) => handleDecline(request.id, reason)} />
              </div>
            </li>
          ))}
        </ul>
      )}

      <h2>My active trips</h2>
      {tripsError && <p className="error-text">{tripsError}</p>}
      {!trips ? (
        <p className="status">Loading…</p>
      ) : trips.length === 0 ? (
        <p className="muted">No active trips.</p>
      ) : (
        <ul className="delivery-list">
          {trips.map((trip) => (
            <li key={trip.id} className="delivery-card">
              <div className="delivery-card-header">
                <strong>{trip.offer_title}</strong>
                <StatusBadge status={trip.status} />
              </div>
              <p className="muted">
                Pickup: {trip.restaurant_name} — {trip.restaurant_address}
              </p>
              <p className="muted">
                Drop-off: {trip.pantry_name} — {trip.pantry_address}
              </p>
              <div className="actions">
                {trip.status === "driver_assigned" && (
                  <button className="button button-small" onClick={() => handlePickedUp(trip.id)}>
                    Mark picked up
                  </button>
                )}
                {trip.status === "picked_up" && (
                  <button className="button button-small" onClick={() => handleDelivered(trip.id)}>
                    Mark delivered
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}
