import { Navigate } from "react-router-dom";

import { useAuth } from "./AuthContext.jsx";
import { roleHomePath } from "./roles.js";

/**
 * RequireRole — wrap a page with this to keep out guests and the wrong role.
 *
 * Usage: <RequireRole roles={["admin"]}><AdminHome /></RequireRole>
 *
 * - Still checking login status -> show a loading message.
 * - Not logged in -> send to /login.
 * - Logged in but wrong role -> send to THEIR OWN home page (not an error page —
 *   they just typed a URL that isn't theirs).
 */
export default function RequireRole({ roles, children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <p className="status">Loading…</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!roles.includes(user.role)) {
    return <Navigate to={roleHomePath(user.role)} replace />;
  }
  return children;
}
