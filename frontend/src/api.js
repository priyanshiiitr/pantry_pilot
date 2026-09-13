/**
 * api.js — the ONE place the frontend talks to the backend.
 *
 * Pages call these helpers instead of using fetch() directly, so error handling
 * and cookie settings live in a single spot. More helpers (apiPost, ...) arrive in Step 3.
 */

/**
 * Send a GET request to the backend and return the parsed JSON.
 * Throws an Error if the backend answers with an error status.
 *
 * @param {string} path - backend URL starting with /api, e.g. "/api/health"
 * @returns {Promise<any>} the JSON body
 */
export async function apiGet(path) {
  // credentials: "include" sends the login cookie along with the request.
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) {
    throw new Error(`backend answered ${response.status} for ${path}`);
  }
  return response.json();
}
