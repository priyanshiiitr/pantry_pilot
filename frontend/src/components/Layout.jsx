import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext.jsx";

/**
 * Layout — the shared shell for every logged-in page: a top bar with the app
 * name, the current user's name and role, and a Log out button.
 *
 * @param {string} [title] - page heading shown under the top bar
 * @param {React.ReactNode} children - the page's own content
 */
export default function Layout({ title, children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="topbar-brand">PantryPilot 🥫</span>
        {user && (
          <div className="topbar-user">
            <span className="topbar-name">{user.display_name}</span>
            <span className="badge">{user.role}</span>
            <button className="button button-small" onClick={handleLogout}>
              Log out
            </button>
          </div>
        )}
      </header>
      <main className="page-content">
        {title && <h1>{title}</h1>}
        {children}
      </main>
    </div>
  );
}
