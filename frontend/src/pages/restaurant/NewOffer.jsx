import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiPost } from "../../api.js";
import Layout from "../../components/Layout.jsx";

/** NewOffer — form for a restaurant to post surplus food. */
export default function NewOffer() {
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [quantityText, setQuantityText] = useState("");
  const [allergenNotes, setAllergenNotes] = useState("");
  const [pickupDeadline, setPickupDeadline] = useState(""); // from <input type="datetime-local">
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      // The datetime-local input gives a value like "2026-09-15T18:00" with no
      // timezone, which the browser treats as *your local time*. new Date(...)
      // reads it the same way, and toISOString() converts that to UTC to send.
      const deadlineUtc = new Date(pickupDeadline).toISOString();
      await apiPost("/api/restaurant/offers", {
        title,
        description,
        quantity_text: quantityText,
        allergen_notes: allergenNotes,
        pickup_deadline: deadlineUtc,
      });
      navigate("/restaurant");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title="Post surplus food">
      <p>
        <Link to="/restaurant">← Back to dashboard</Link>
      </p>
      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Title</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Unsold sandwiches"
            required
            autoFocus
          />
        </label>
        <label className="field">
          <span>Description</span>
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is it, roughly how much, any details a pantry should know."
            required
          />
        </label>
        <label className="field">
          <span>Quantity</span>
          <input
            value={quantityText}
            onChange={(e) => setQuantityText(e.target.value)}
            placeholder="e.g. 40 sandwiches"
            required
          />
        </label>
        <label className="field">
          <span>Allergen notes</span>
          <input
            value={allergenNotes}
            onChange={(e) => setAllergenNotes(e.target.value)}
            placeholder="e.g. contains dairy, gluten"
          />
        </label>
        <label className="field">
          <span>Must be collected by</span>
          <input
            type="datetime-local"
            value={pickupDeadline}
            onChange={(e) => setPickupDeadline(e.target.value)}
            required
          />
        </label>
        {error && <p className="error-text">{error}</p>}
        <button className="button" type="submit" disabled={submitting}>
          {submitting ? "Posting…" : "Post offer"}
        </button>
      </form>
    </Layout>
  );
}
