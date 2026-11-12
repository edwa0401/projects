export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const diff = Math.round((now - new Date(iso).getTime()) / 1000);
  if (diff < 60) return "just now";
  const mins = Math.round(diff / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs} hr ago`;
  return `${Math.round(hrs / 24)} days ago`;
}

export function formatPercent(v: number | null | undefined): string {
  return v === null || v === undefined ? "No data" : `${Math.round(v * 1000) / 10}%`;
}

export function minutesLeft(expiresAtSec: number, now = Date.now()): number {
  return Math.max(0, Math.round((expiresAtSec * 1000 - now) / 60000));
}
