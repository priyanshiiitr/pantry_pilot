/** Which URL is "home" for each role — used after login/signup and by route guards. */
const ROLE_HOME_PATHS = {
  restaurant: "/restaurant",
  pantry: "/pantry",
  driver: "/driver",
  admin: "/admin",
};

/** @param {string} role @returns {string} the dashboard path for that role */
export function roleHomePath(role) {
  return ROLE_HOME_PATHS[role] ?? "/";
}
