import { useState } from "react";

/**
 * DeclineButton — click "Decline" to reveal a reason field, then confirm.
 * Used by both the pantry (declining a delivery) and the driver (declining a
 * pickup) — the reason always gets read by the agent when it re-plans.
 *
 * @param {(reason: string) => Promise<void>} onDecline
 */
export default function DeclineButton({ onDecline }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) {
    return (
      <button className="button button-danger button-small" onClick={() => setOpen(true)}>
        Decline
      </button>
    );
  }

  async function handleConfirm() {
    if (!reason.trim()) return;
    setSubmitting(true);
    try {
      await onDecline(reason);
    } finally {
      setSubmitting(false);
      setOpen(false);
      setReason("");
    }
  }

  return (
    <div className="decline-form">
      <input
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Why are you declining?"
        autoFocus
      />
      <button
        className="button button-danger button-small"
        onClick={handleConfirm}
        disabled={submitting || !reason.trim()}
      >
        Confirm decline
      </button>
      <button className="button button-secondary button-small" onClick={() => setOpen(false)} disabled={submitting}>
        Cancel
      </button>
    </div>
  );
}
