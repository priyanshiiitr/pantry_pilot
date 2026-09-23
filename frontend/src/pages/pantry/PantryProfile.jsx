import { Link } from "react-router-dom";

import AppShell from "../../components/AppShell.jsx";
import WeeklyHoursEditor from "../../components/WeeklyHoursEditor.jsx";
import { useProfileForm } from "../../hooks/useProfileForm.js";

// Keep this list in sync with DIETARY_RESTRICTIONS in pantrypilot/models/places.py.
const DIETARY_TAGS = [
  { value: "no_pork", label: "No pork" },
  { value: "no_beef", label: "No beef" },
  { value: "halal_only", label: "Halal only" },
  { value: "kosher_only", label: "Kosher only" },
  { value: "vegetarian_only", label: "Vegetarian only" },
  { value: "no_nuts", label: "No nuts" },
  { value: "no_alcohol", label: "No alcohol" },
];

/** PantryProfile — edit capacity, storage, opening hours and dietary restrictions. */
export default function PantryProfile() {
  const { form, updateField, save, error, saving, savedMessage } = useProfileForm("/api/pantry/profile");

  function toggleDietaryTag(tag, checked) {
    const next = checked ? [...form.dietary_restrictions, tag] : form.dietary_restrictions.filter((t) => t !== tag);
    updateField("dietary_restrictions", next);
  }

  return (
    <AppShell title="Pantry profile">
      <p>
        <Link to="/pantry">← Back to dashboard</Link>
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
          <label className="field">
            <span>Capacity (kg of food per day)</span>
            <input
              type="number"
              min="1"
              value={form.capacity_kg_per_day}
              onChange={(e) => updateField("capacity_kg_per_day", Number(e.target.value))}
              required
            />
          </label>
          <label className="checkbox-item">
            <input type="checkbox" checked={form.has_fridge} onChange={(e) => updateField("has_fridge", e.target.checked)} />
            Has a fridge
          </label>
          <label className="checkbox-item">
            <input
              type="checkbox"
              checked={form.has_freezer}
              onChange={(e) => updateField("has_freezer", e.target.checked)}
            />
            Has a freezer
          </label>
          <label className="checkbox-item">
            <input
              type="checkbox"
              checked={form.accepting_donations}
              onChange={(e) => updateField("accepting_donations", e.target.checked)}
            />
            Currently accepting donations
          </label>

          <div className="field">
            <span>Dietary restrictions</span>
            <div className="checkbox-grid">
              {DIETARY_TAGS.map((tag) => (
                <label key={tag.value} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={form.dietary_restrictions.includes(tag.value)}
                    onChange={(e) => toggleDietaryTag(tag.value, e.target.checked)}
                  />
                  {tag.label}
                </label>
              ))}
            </div>
          </div>

          <div className="field">
            <span>Opening hours</span>
            <WeeklyHoursEditor value={form.opening_hours} onChange={(hours) => updateField("opening_hours", hours)} />
          </div>

          <label className="field">
            <span>Notes (for the agent and other staff)</span>
            <textarea rows={3} value={form.notes} onChange={(e) => updateField("notes", e.target.value)} />
          </label>

          {savedMessage && <p className="status status-good">{savedMessage}</p>}
          <button className="button" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </form>
      )}
    </AppShell>
  );
}
