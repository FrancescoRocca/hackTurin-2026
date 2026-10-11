/**
 * Number and time formatting. Network figures are tabular digits: how they are
 * written is decided once here, and no component formats them on its own.
 */

const LOCALE = "en-GB";

const intFmt = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const dec1Fmt = new Intl.NumberFormat(LOCALE, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function num(n: number): string {
  return intFmt.format(Math.round(n));
}

/** A per-minute rate: anything under one pass a minute reads "<1", never a bare zero. */
export function perMinute(n: number): string {
  return n < 1 ? "<1" : num(n);
}

export function dec1(n: number): string {
  return dec1Fmt.format(n);
}

/** Percentage of a whole, one decimal. */
export function share(part: number, whole: number): string {
  if (whole <= 0) return "—";
  return `${dec1Fmt.format((part / whole) * 100)}%`;
}

/** Signed percentage, with a typographic minus. */
export function signedShare(n: number): string {
  if (Math.abs(n) < 0.05) return "0.0%";
  return `${n > 0 ? "+" : "−"}${dec1Fmt.format(Math.abs(n))}%`;
}

export function hhmm(ts: number): string {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function hhmmss(ts: number): string {
  return `${hhmm(ts)}:${String(new Date(ts).getSeconds()).padStart(2, "0")}`;
}

/** Time elapsed since `ts`, in words and without a suffix: "41 min", "2 h 5 min". */
export function elapsed(ts: number, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - ts) / 1000));
  if (s < 60) return `${s} s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  if (h < 24) return rest === 0 ? `${h} h` : `${h} h ${rest} min`;
  return `${Math.floor(h / 24)} d`;
}

/** How long ago, in words: "just now", "41 min ago". */
export function since(ts: number, now = Date.now()): string {
  if (Math.round((now - ts) / 1000) < 5) return "just now";
  return `${elapsed(ts, now)} ago`;
}

export function duration(ms: number): string {
  const d = Math.floor(ms / 86_400_000);
  const h = Math.floor((ms % 86_400_000) / 3_600_000);
  return d > 0 ? `${d} d ${h} h` : `${h} h`;
}

/** Distance as a survey would write it. */
export function meters(m: number): string {
  if (m < 1000) return `${num(m)} m`;
  return `${(m / 1000).toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} km`;
}
