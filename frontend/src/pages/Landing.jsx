import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext.jsx";
import { roleHomePath } from "../auth/roles.js";
import BackendStatus from "../components/BackendStatus.jsx";

/** Landing — the "/" page. Explains PantryPilot and points guests to login/signup. */
export default function Landing() {
  const { user, loading } = useAuth();

  return (
    <main className="page">
      <section className="card">
        <h1>
          PantryPilot <span aria-hidden="true">🥫</span>
        </h1>
        <p className="muted">
          An AI agent team that routes surplus food from restaurants to food pantries — and only asks a
          human when there is a real decision to make.
        </p>
        <BackendStatus />
        <div className="actions">
          {loading ? null : user ? (
            <Link className="button" to={roleHomePath(user.role)}>
              Go to your dashboard
            </Link>
          ) : (
            <>
              <Link className="button" to="/login">
                Log in
              </Link>
              <Link className="button button-secondary" to="/signup">
                Sign up
              </Link>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
