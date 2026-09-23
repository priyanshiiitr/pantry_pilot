import { Link, NavLink, useNavigate } from "react-router-dom";

import { apiGet } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { roleHomePath } from "../auth/roles.js";
import { usePolling } from "../hooks/usePolling.js";

// The sidebar's main navigation, per role. Every logged-in role gets the same
// shell; only these links differ.
const NAV_BY_ROLE = {
  admin: [
    { to: "/admin", label: "Overview", icon: "◎", end: true },
    { to: "/admin/offers", label: "Offers", icon: "▤" },
    { to: "/admin/users", label: "Network", icon: "⬡" },
    { to: "/admin/memory", label: "Agent memory", icon: "◈" },
    { to: "/admin/decisions", label: "Decisions", icon: "⚑", countKey: "pendingDecisions" },
    { to: "/admin/activity", label: "Activity", icon: "◷" },
  ],
  restaurant: [
    { to: "/restaurant", label: "My offers", icon: "▤", end: true },
    { to: "/restaurant/offers/new", label: "Post surplus", icon: "＋" },
    { to: "/restaurant/profile", label: "Profile", icon: "◇" },
  ],
  pantry: [
    { to: "/pantry", label: "Incoming food", icon: "▤", end: true },
    { to: "/pantry/profile", label: "Profile", icon: "◇" },
  ],
  driver: [
    { to: "/driver", label: "My pickups", icon: "▤", end: true },
    { to: "/driver/profile", label: "Profile", icon: "◇" },
  ],
};

// Roles an admin can preview from the sidebar. Admin is first so it reads as
// "back to my own view".
const SWITCHABLE_ROLES = [
  { role: "admin", label: "Admin", icon: "◎" },
  { role: "restaurant", label: "Restaurant", icon: "▦" },
  { role: "pantry", label: "Pantry", icon: "⌂" },
  { role: "driver", label: "Driver", icon: "⛟" },
];

function initialsOf(name) {
  return (name || "?")
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

/**
 * AppShell — the dark sidebar + top bar that wraps every logged-in page.
 *
 * The Decisions badge is polled here rather than passed in, so it stays correct
 * on every admin page without each one having to remember to fetch it.
 *
 * @param {string} [title] - optional page heading rendered above the content
 * @param {React.ReactNode} children - the page's own content
 */
export default function AppShell({ title, children }) {
  const { user, realUser, isViewingAs, viewAs, logout } = useAuth();
  const navigate = useNavigate();

  // Only an admin's own view may call the admin API — while previewing another
  // role, that endpoint correctly refuses, so we don't ask.
  const isAdminView = user?.role === "admin";
  const { data: decisions } = usePolling(
    () => (isAdminView ? apiGet("/api/admin/decisions") : Promise.resolve([])),
    8000,
    [isAdminView]
  );
  const pendingDecisions = decisions?.length ?? 0;

  if (!user) return null;

  const navLinks = NAV_BY_ROLE[user.role] ?? [];
  const counts = { pendingDecisions };

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  async function handleSwitch(role) {
    const nextUser = await viewAs(role);
    navigate(roleHomePath(nextUser.role));
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link className="sidebar-brand" to={roleHomePath(user.role)}>
          <span className="sidebar-brand-mark" aria-hidden="true">
            🥫
          </span>
          <span>
            <div className="sidebar-brand-name">PantryPilot</div>
            <div className="sidebar-brand-tagline">Good food. A brighter tomorrow.</div>
          </span>
        </Link>

        <nav className="sidebar-nav">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => (isActive ? "sidebar-link is-active" : "sidebar-link")}
            >
              <span className="sidebar-link-icon" aria-hidden="true">
                {link.icon}
              </span>
              {link.label}
              {counts[link.countKey] > 0 && <span className="sidebar-link-count">{counts[link.countKey]}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Only a real admin may preview other roles — the button is hidden for
            everyone else, and the backend enforces the same rule regardless. */}
        {realUser?.role === "admin" && (
          <div className="sidebar-switch">
            <div className="sidebar-heading">Switch view</div>
            {SWITCHABLE_ROLES.map((option) => (
              <button
                key={option.role}
                type="button"
                onClick={() => handleSwitch(option.role)}
                className={user.role === option.role ? "sidebar-link is-active" : "sidebar-link"}
              >
                <span className="sidebar-link-icon" aria-hidden="true">
                  {option.icon}
                </span>
                {option.label}
              </button>
            ))}
          </div>
        )}

        <div className="sidebar-spacer" />

        <div className="sidebar-note">Less food waste. Stronger communities.</div>

        <div className="sidebar-account">
          <span className="avatar">{initialsOf(user.display_name)}</span>
          <span style={{ minWidth: 0 }}>
            <div className="sidebar-account-name">{user.display_name}</div>
            <div className="sidebar-account-email">{user.email}</div>
          </span>
        </div>
      </aside>

      <div className="shell-main">
        {isViewingAs && (
          <div className="viewing-as-banner">
            <span>
              You are previewing PantryPilot as <strong>{user.display_name}</strong> ({user.role}). Signed in as{" "}
              {realUser.email}.
            </span>
            <button type="button" className="button-accent" onClick={() => handleSwitch("admin")}>
              Back to admin
            </button>
          </div>
        )}

        <header className="shell-topbar">
          <div className="shell-search">
            <span className="shell-search-icon" aria-hidden="true">
              ⌕
            </span>
            <input type="search" placeholder="Search offers, pantries, drivers…" aria-label="Search" />
          </div>
          <div className="shell-topbar-right">
            <button type="button" className="icon-button" aria-label="Notifications">
              ◔
              {pendingDecisions > 0 && <span className="icon-button-dot" />}
            </button>
            <span className="avatar avatar-light">{initialsOf(user.display_name)}</span>
            <button type="button" className="button button-small" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </header>

        <main className="shell-content">
          {title && <h1>{title}</h1>}
          {children}
        </main>
      </div>
    </div>
  );
}
