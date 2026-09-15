import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext.jsx";
import { roleHomePath } from "../../auth/roles.js";

// Admin accounts aren't offered here on purpose — see scripts/seed_demo.py.
const ROLE_OPTIONS = [
  { value: "restaurant", label: "Restaurant / Donor" },
  { value: "pantry", label: "Pantry / Recipient" },
  { value: "driver", label: "Driver (volunteer)" },
];

/** Signup — create an account as a restaurant, pantry or driver. */
export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(ROLE_OPTIONS[0].value);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const newUser = await signup({ display_name: displayName, email, password, role });
      navigate(roleHomePath(newUser.role));
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page">
      <section className="card">
        <h1>Sign up</h1>
        <form className="form" onSubmit={handleSubmit}>
          <label className="field">
            <span>I am a…</span>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Name</span>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Golden Crust Bakery"
              required
              autoFocus
            />
          </label>
          <label className="field">
            <span>Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
            <span className="hint">At least 8 characters.</span>
          </label>
          {error && <p className="error-text">{error}</p>}
          <button className="button" type="submit" disabled={submitting}>
            {submitting ? "Creating account…" : "Sign up"}
          </button>
        </form>
        <p className="muted">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </section>
    </main>
  );
}
