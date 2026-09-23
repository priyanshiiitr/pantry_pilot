import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { apiGet, apiPost } from "../api.js";

// React Context is how a value (here: "who is logged in") can be read by any
// component in the tree without passing it down through every layer by hand.
const AuthContext = createContext(null);

/**
 * AuthProvider — wraps the whole app and keeps track of the logged-in user.
 *
 * On first load it asks the backend "who am I?" (the login cookie, if any, answers
 * that). Every page then reads the result with useAuth() instead of asking again.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // The account that actually logged in. Differs from `user` only while an admin
  // is previewing another role via the sidebar's "Switch view".
  const [realUser, setRealUser] = useState(null);
  const [loading, setLoading] = useState(true); // true until the first /me check finishes

  useEffect(() => {
    apiGet("/api/auth/me")
      .then((data) => {
        setUser(data.user);
        setRealUser(data.real_user ?? data.user);
      })
      .catch(() => {
        setUser(null);
        setRealUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const loggedInUser = await apiPost("/api/auth/login", { email, password });
    setUser(loggedInUser);
    setRealUser(loggedInUser);
    return loggedInUser;
  }, []);

  const signup = useCallback(async (fields) => {
    const newUser = await apiPost("/api/auth/signup", fields);
    setUser(newUser);
    setRealUser(newUser);
    return newUser;
  }, []);

  const logout = useCallback(async () => {
    await apiPost("/api/auth/logout");
    setUser(null);
    setRealUser(null);
  }, []);

  /** Admin only: preview another role's dashboard, or pass "admin" to return to your own. */
  const viewAs = useCallback(async (role) => {
    const data = await apiPost("/api/auth/view-as", { role });
    setUser(data.user);
    setRealUser(data.real_user);
    return data.user;
  }, []);

  const isViewingAs = Boolean(user && realUser && user.id !== realUser.id);

  return (
    <AuthContext.Provider value={{ user, realUser, isViewingAs, loading, login, signup, logout, viewAs }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Read the current auth state ({ user, loading, login, signup, logout }) from any component. */
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth() must be called inside <AuthProvider>.");
  }
  return context;
}
