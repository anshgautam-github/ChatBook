/** Truncate long text for compact list display. */
export function truncate(text, maxLength = 120) {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trimEnd()}…`;
}
