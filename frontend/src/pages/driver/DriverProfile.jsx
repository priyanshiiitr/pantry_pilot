import { Link } from "react-router-dom";

import AppShell from "../../components/AppShell.jsx";
import WeeklyHoursEditor from "../../components/WeeklyHoursEditor.jsx";
import { useProfileForm } from "../../hooks/useProfileForm.js";

/** DriverProfile — edit vehicle, capacity, service area, availability and on-duty status. */
export default function DriverProfile() {
  const { form, updateField, save, error, saving, savedMessage } = useProfileForm("/api/driver/profile");

  return (
    <AppShell title="Driver profile">
      <p>
        <Link to="/driver">← Back to dashboard</Link>
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
            <span>Phone</span>
            <input value={form.phone} onChange={(e) => updateField("phone", e.target.value)} />
          </label>
          <div className="field-row">
            <label className="field">
              <span>Home latitude</span>
              <input
                type="number"
                step="0.0001"
                value={form.lat}
                onChange={(e) => updateField("lat", Number(e.target.value))}
                required
              />
            </label>
            <label className="field">
              <span>Home longitude</span>
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
            <span>Vehicle</span>
            <input value={form.vehicle} onChange={(e) => updateField("vehicle", e.target.value)} placeholder="car, van, cargo bike…" />
          </label>
          <div className="field-row">
            <label className="field">
              <span>Service radius (km)</span>
              <input
                type="number"
                min="1"
                value={form.service_radius_km}
                onChange={(e) => updateField("service_radius_km", Number(e.target.value))}
                required
              />
            </label>
            <label className="field">
              <span>Max load (kg)</span>
              <input
                type="number"
                min="1"
                value={form.max_kg}
                onChange={(e) => updateField("max_kg", Number(e.target.value))}
                required
              />
            </label>
          </div>
          <label className="checkbox-item">
            <input type="checkbox" checked={form.has_cooler} onChange={(e) => updateField("has_cooler", e.target.checked)} />
            Vehicle has a cooler (needed for perishable food)
          </label>
          <label className="checkbox-item">
            <input type="checkbox" checked={form.on_duty} onChange={(e) => updateField("on_duty", e.target.checked)} />
            Currently on duty (available for dispatch requests)
          </label>

          <div className="field">
            <span>Weekly availability</span>
            <WeeklyHoursEditor value={form.availability} onChange={(hours) => updateField("availability", hours)} />
          </div>

          {savedMessage && <p className="status status-good">{savedMessage}</p>}
          <button className="button" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </form>
      )}
    </AppShell>
  );
}
