// Shared by the Pantry profile (opening hours) and Driver profile (availability) —
// both store the same shape: { mon: ["09:00", "17:00"], ... }, missing day = closed.
const DAYS = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" },
];

const DEFAULT_TIMES = ["09:00", "17:00"];

/**
 * WeeklyHoursEditor — seven rows (Mon–Sun), each a checkbox plus an open/close time pair.
 * Unchecking a day removes it from `value` entirely (meaning "closed").
 *
 * @param {Record<string, [string, string]>} value
 * @param {(next: Record<string, [string, string]>) => void} onChange
 */
export default function WeeklyHoursEditor({ value, onChange }) {
  function toggleDay(dayKey, isOpen) {
    const next = { ...value };
    if (isOpen) {
      next[dayKey] = DEFAULT_TIMES;
    } else {
      delete next[dayKey];
    }
    onChange(next);
  }

  function setTime(dayKey, index, time) {
    const times = [...(value[dayKey] ?? DEFAULT_TIMES)];
    times[index] = time;
    onChange({ ...value, [dayKey]: times });
  }

  return (
    <div className="hours-editor">
      {DAYS.map((day) => {
        const isOpen = day.key in value;
        const [openTime, closeTime] = value[day.key] ?? DEFAULT_TIMES;
        return (
          <div className="hours-row" key={day.key}>
            <label className="hours-day">
              <input type="checkbox" checked={isOpen} onChange={(e) => toggleDay(day.key, e.target.checked)} />
              {day.label}
            </label>
            <input
              type="time"
              value={openTime}
              disabled={!isOpen}
              onChange={(e) => setTime(day.key, 0, e.target.value)}
            />
            <span className="muted">to</span>
            <input
              type="time"
              value={closeTime}
              disabled={!isOpen}
              onChange={(e) => setTime(day.key, 1, e.target.value)}
            />
          </div>
        );
      })}
    </div>
  );
}
