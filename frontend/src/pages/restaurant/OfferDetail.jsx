import { Link, useParams } from "react-router-dom";

import { apiGet } from "../../api.js";
import Layout from "../../components/Layout.jsx";
import StatusBadge from "../../components/StatusBadge.jsx";
import { usePolling } from "../../hooks/usePolling.js";

/** OfferDetail — one offer's full details and live status, for the restaurant that posted it. */
export default function OfferDetail() {
  const { offerId } = useParams();
  const { data: offer, error } = usePolling(() => apiGet(`/api/restaurant/offers/${offerId}`), 3000, [offerId]);

  return (
    <Layout title="Offer details">
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
            <p className="muted">
              {offer.agent_summary ??
                "No update yet — the AI agents haven't looked at this offer. That arrives in Step 6+."}
            </p>
          </div>
        </section>
      )}
    </Layout>
  );
}
