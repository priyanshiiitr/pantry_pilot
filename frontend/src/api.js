/**
 * api.js — the ONE place the frontend talks to the backend.
 *
 * Pages call apiGet/apiPost instead of using fetch() directly, so cookie settings
 * and error handling live in a single spot.
 */

/**
 * Send a request to the backend and return the parsed JSON body.
 * Throws an Error (with the backend's message, if it sent one) on a non-2xx response.
 *
 * @param {"GET"|"POST"|"PUT"} method
 * @param {string} path - backend URL starting with /api, e.g. "/api/auth/login"
 * @param {object} [body] - request body; sent as JSON if given
 * @returns {Promise<any>}
 */
async function request(method, path, body) {
  const response = await fetch(path, {
    method,
    // Sends the login cookie along with the request, and accepts one back.
    credentials: "include",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  // FastAPI sends JSON for both successes and errors; a couple of endpoints send nothing.
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    // FastAPI error bodies look like {"detail": "message"} or, for validation
    // errors, {"detail": [{"msg": "message", ...}, ...]}.
    const detail = data && data.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg : null;
    throw new Error(message || `Request failed (${response.status}).`);
  }

  return data;
}

/** GET request. See request() above. */
export function apiGet(path) {
  return request("GET", path);
}

/** POST request with a JSON body. See request() above. */
export function apiPost(path, body) {
  return request("POST", path, body);
}

/** PUT request with a JSON body (used to save profile edits). See request() above. */
export function apiPut(path, body) {
  return request("PUT", path, body);
}
