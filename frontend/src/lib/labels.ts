/**
 * Turning the backend's stored vocabulary into words. Shared by the research
 * pages, which all store choices as lowercase keys (`youtube_shorts`,
 * `tamil nadu`, `possible_outlier`) and must show them as a person would.
 */

export interface LabelledOption {
  value: string;
  label: string;
}

/** `possible_outlier` → "Possible outlier". Keeps the rest as stored. */
export function humanize(value: string): string {
  const text = value.replaceAll("_", " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

/**
 * The label for a stored option value, whatever its case. `aliases` maps other
 * spellings of the same choice onto an option's value; an alias of "" means
 * the empty option. Anything unrecognised (free text from an older form) is
 * shown as it was typed.
 */
export function optionLabel(
  options: readonly LabelledOption[],
  value: unknown,
  empty: string,
  aliases: ReadonlyMap<string, string> = new Map(),
): string {
  const raw = String(value ?? "").trim();
  const key = raw.toLowerCase();
  const canonical = aliases.get(key) ?? key;
  if (!canonical) return empty;
  return options.find((option) => option.value === canonical)?.label ?? humanize(raw);
}
