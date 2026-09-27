import Link from "next/link";
import { getMarkets, getStats } from "@/lib/data";
import { longDate, pct, price } from "@/lib/format";
import TimeAgo from "./TimeAgo";

export default async function Masthead() {
  const [markets, stats] = await Promise.all([getMarkets(), getStats()]);
  const updated = stats?.generatedAt;
  const stale = updated ? Date.now() - new Date(updated).getTime() > 45 * 60e3 : true;
  return (
    <header className="wrap masthead">
      <div className="masthead-top">
        <Link href="/" className="logo">
          Akış<small>Gündemin derlenmiş hâli</small>
        </Link>
        <div className="dateline">
          <div>{longDate(new Date())}</div>
          {updated && (
            <div className={stale ? "stale" : "live"} suppressHydrationWarning>
              <TimeAgo iso={updated} prefix="Güncellendi: " />
            </div>
          )}
        </div>
      </div>
      {markets.items && markets.items.length > 0 && (
        <div className="markets num" aria-label="Piyasalar">
          {markets.items.map((m) => (
            <span key={m.symbol}>
              <b>{m.label}</b>
              {m.unit === "$" ? "$" : ""}
              {price(m.price)}
              {m.unit === "₺" ? " ₺" : ""}{" "}
              <span className={m.change > 0 ? "up" : m.change < 0 ? "down" : "muted"}>{pct(m.change)}</span>
            </span>
          ))}
        </div>
      )}
    </header>
  );
}
