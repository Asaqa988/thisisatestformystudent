// Small display helpers. They are called only while rendering loaded data in
// the browser, never during the server prerender.

const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "now", "4m", "3h", "2d", then a short date. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 45) return "now";
  if (seconds < HOUR) return `${Math.round(seconds / MINUTE)}m`;
  if (seconds < DAY) return `${Math.round(seconds / HOUR)}h`;
  if (seconds < 7 * DAY) return `${Math.round(seconds / DAY)}d`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** "14:05" */
export function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** "Today", "Yesterday" or "Tue, Nov 10" for the separators in a thread. */
export function dayLabel(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOf(today) - startOf(date)) / (DAY * 1000));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** A stable hue per name, so each customer keeps the same avatar colour. */
export function hueFor(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) % 360;
  return hash;
}

const CHANNEL_LABELS: Record<string, string> = {
  api: "API channel",
  web_widget: "Website chat",
  email: "Email",
  whatsapp: "WhatsApp",
  telegram: "Telegram",
  sms: "SMS",
  facebook: "Messenger",
  instagram: "Instagram",
};

export function channelLabel(channel: string): string {
  return CHANNEL_LABELS[channel] ?? channel.replace(/_/g, " ");
}

/** "message_created" -> "Message created" */
export function eventLabel(eventType: string): string {
  const text = eventType.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
