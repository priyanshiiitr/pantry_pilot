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
  const [loading, setLoading] = useState(true); // true until the first /me check finishes

  useEffect(() => {
    apiGet("/api/auth/me")
      .then((data) => setUser(data.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const loggedInUser = await apiPost("/api/auth/login", { email, password });
    setUser(loggedInUser);
    return loggedInUser;
  }, []);

  const signup = useCallback(async (fields) => {
    const newUser = await apiPost("/api/auth/signup", fields);
    setUser(newUser);
    return newUser;
  }, []);

  const logout = useCallback(async () => {
    await apiPost("/api/auth/logout");
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, login, signup, logout }}>{children}</AuthContext.Provider>;
}

/** Read the current auth state ({ user, loading, login, signup, logout }) from any component. */
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth() must be called inside <AuthProvider>.");
  }
  return context;
}
