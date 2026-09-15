// Keep these in sync with OfferStatus in pantrypilot/models/offers.py.
const STATUS_LABELS = {
  posted: "Posted",
  agent_working: "Agent working…",
  needs_human: "Needs human",
  driver_requested: "Driver requested",
  driver_assigned: "Driver assigned",
  picked_up: "Picked up",
  delivered: "Delivered",
  expired: "Expired",
  cancelled: "Cancelled",
};

// Colour groups: grey = waiting, blue = agent/driver working it, amber = needs a
// human, green = finished well, red = didn't work out.
const STATUS_COLORS = {
  posted: "grey",
  agent_working: "blue",
  needs_human: "amber",
  driver_requested: "blue",
  driver_assigned: "blue",
  picked_up: "blue",
  delivered: "good",
  expired: "bad",
  cancelled: "bad",
};

/** StatusBadge — a small coloured pill showing an offer's status in plain English. */
export default function StatusBadge({ status }) {
  const color = STATUS_COLORS[status] ?? "grey";
  return <span className={`status-badge status-${color}`}>{STATUS_LABELS[status] ?? status}</span>;
}
