const TZ = "Europe/Istanbul";

const hm = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
const dayFmt = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "long", timeZone: TZ });
const longFmt = new Intl.DateTimeFormat("tr-TR", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: TZ });
const dayKey = new Intl.DateTimeFormat("en-CA", { timeZone: TZ });

export const clock = (iso: string) => hm.format(new Date(iso));
export const longDate = (d: Date) => longFmt.format(d);

/** Bugünse "14:05", dünse "Dün 14:05", daha eskiyse "25 Eylül 14:05" */
export function stamp(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const k = dayKey.format(d);
  if (k === dayKey.format(now)) return hm.format(d);
  if (k === dayKey.format(new Date(now.getTime() - 864e5))) return `Dün ${hm.format(d)}`;
  return `${dayFmt.format(d)} ${hm.format(d)}`;
}

export function ago(iso: string, now = Date.now()): string {
  const m = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (m < 1) return "az önce";
  if (m < 60) return `${m} dk önce`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} sa önce`;
  return stamp(iso);
}

const nf = (digits: number) => new Intl.NumberFormat("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const price = (v: number) => nf(v >= 1000 ? 0 : 2).format(v);
export const pct = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}%${nf(2).format(Math.abs(v))}`;
