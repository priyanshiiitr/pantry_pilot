/**
 * StatCard — one number tile for the admin overview, e.g. "4 Active offers".
 *
 * @param {string} label
 * @param {number|string} value
 * @param {"good"|"amber"} [accent] - highlight color when the number needs attention
 */
export default function StatCard({ label, value, accent }) {
  return (
    <div className={`stat-card${accent ? ` stat-card-${accent}` : ""}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
