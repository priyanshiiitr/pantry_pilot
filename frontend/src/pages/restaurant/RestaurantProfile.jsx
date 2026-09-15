import { Link } from "react-router-dom";

import Layout from "../../components/Layout.jsx";
import { useProfileForm } from "../../hooks/useProfileForm.js";

/** RestaurantProfile — edit name, address and location. */
export default function RestaurantProfile() {
  const { form, updateField, save, error, saving, savedMessage } = useProfileForm("/api/restaurant/profile");

  return (
    <Layout title="Restaurant profile">
      <p>
        <Link to="/restaurant">← Back to dashboard</Link>
      </p>
      {error && <p className="error-text">{error}</p>}
      {!form ? (
        <p className="status">Loading…</p>
      ) : (
        <form className="form" onSubmit={save}>
          <label className="field">
            <span>Name</span>
            <input value={form.name} onChange={(e) => updateField("name", e.target.value)} required />
          </label>
          <label className="field">
            <span>Address</span>
            <input value={form.address} onChange={(e) => updateField("address", e.target.value)} required />
          </label>
          <div className="field-row">
            <label className="field">
              <span>Latitude</span>
              <input
                type="number"
                step="0.0001"
                value={form.lat}
                onChange={(e) => updateField("lat", Number(e.target.value))}
                required
              />
            </label>
            <label className="field">
              <span>Longitude</span>
              <input
                type="number"
                step="0.0001"
                value={form.lon}
                onChange={(e) => updateField("lon", Number(e.target.value))}
                required
              />
            </label>
          </div>
          <label className="field">
            <span>Phone</span>
            <input value={form.phone} onChange={(e) => updateField("phone", e.target.value)} />
          </label>
          {savedMessage && <p className="status status-good">{savedMessage}</p>}
          <button className="button" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </form>
      )}
    </Layout>
  );
}
