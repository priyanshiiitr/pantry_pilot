import { useEffect, useState } from "react";

import { apiGet, apiPut } from "../api.js";

/**
 * useProfileForm — shared load/edit/save logic for the three profile pages
 * (restaurant, pantry, driver). Each page still writes its own form fields;
 * this hook only handles "fetch it, track edits, save it, report success/error".
 *
 * @param {string} profilePath - e.g. "/api/pantry/profile"
 * @returns {{
 *   form: object | null,           // null while the initial GET is loading
 *   updateField: (field: string, value: any) => void,
 *   save: (event: React.FormEvent) => Promise<void>,
 *   error: string | null,
 *   saving: boolean,
 *   savedMessage: string | null,
 * }}
 */
export function useProfileForm(profilePath) {
  const [form, setForm] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState(null);

  useEffect(() => {
    apiGet(profilePath)
      .then(setForm)
      .catch((err) => setError(err.message));
  }, [profilePath]);

  function updateField(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }));
    setSavedMessage(null); // editing again should hide the old "Saved." message
  }

  async function save(event) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const updated = await apiPut(profilePath, form);
      setForm(updated);
      setSavedMessage("Saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return { form, updateField, save, error, saving, savedMessage };
}
