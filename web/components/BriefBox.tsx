import type { Brief, Story } from "@/lib/types";
import TimeAgo from "./TimeAgo";

/** Sayfanın en üstündeki "Şu an" özeti: günün tablosu 4-6 maddede */
export default function BriefBox({ brief, stories }: { brief: Brief; stories: Story[] }) {
  if (!brief.items?.length) return null;
  const known = new Set(stories.map((s) => s.id));
  return (
    <section className="brief" aria-labelledby="brief-h">
      <span className="kicker">
        Şu an{brief.generated_at && <> · <TimeAgo iso={brief.generated_at} /></>}
      </span>
      <h2 id="brief-h">{brief.headline}</h2>
      <ol>
        {brief.items.map((it, i) => {
          const id = it.ids.find((x) => known.has(x));
          return <li key={i}>{id ? <a href={`#s-${id}`}>{it.text}</a> : it.text}</li>;
        })}
      </ol>
    </section>
  );
}
