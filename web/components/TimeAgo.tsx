"use client";
import { useEffect, useState } from "react";
import { ago, stamp } from "@/lib/format";

/** Sunucuda saat damgası, tarayıcıda "5 dk önce" olarak görünür ve dakikada bir güncellenir. */
export default function TimeAgo({ iso, prefix }: { iso: string; prefix?: string }) {
  const [text, setText] = useState(() => stamp(iso));
  useEffect(() => {
    const tick = () => setText(ago(iso));
    tick();
    const t = setInterval(tick, 60_000);
    return () => clearInterval(t);
  }, [iso]);
  return (
    <time dateTime={iso} title={new Date(iso).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })} suppressHydrationWarning>
      {prefix}
      {text}
    </time>
  );
}
