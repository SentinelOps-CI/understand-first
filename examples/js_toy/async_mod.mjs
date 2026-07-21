/** Async ESM fixture for Wave 16 JS adapter hardening. */
export async function fetchLabel(id) {
  const raw = await loadRaw(id);
  if (!raw) {
    return "missing";
  }
  return formatLabel(raw);
}

export async function loadRaw(id) {
  return String(id);
}

export function formatLabel(raw) {
  return `label:${raw}`;
}
