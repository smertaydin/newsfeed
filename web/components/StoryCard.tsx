import Link from "next/link";
import type { Story } from "@/lib/types";
import { sectionName } from "@/lib/types";
import { clock } from "@/lib/format";
import TimeAgo from "./TimeAgo";

export function isDeveloping(s: Story, now = Date.now()) {
  const last = s.timeline.at(-1);
  return s.sourceCount >= 3 && !!last && now - new Date(last.t).getTime() < 3 * 3600e3 && s.timeline.length > 1;
}

interface Props {
  story: Story;
  lead?: boolean;
  expanded?: boolean;
  focused?: boolean;
  read?: boolean;
  fresh?: boolean;
  standalone?: boolean;
  onToggle?: () => void;
  onOpen?: () => void;
}

export default function StoryCard({ story: s, lead, expanded, focused, read, fresh, standalone, onToggle, onOpen }: Props) {
  const full = s.kind === "full";
  const showDetail = standalone || expanded;
  const points = showDetail || lead ? s.points : s.points.slice(0, 3);
  const hidden = s.points.length - points.length;
  const cls = ["story", lead && "lead", focused && "focused", read && !focused && "read"].filter(Boolean).join(" ");
  const TitleTag = standalone ? "h1" : "h2";

  return (
    <article id={`s-${s.id}`} className={cls} data-section={s.section}>
      <div className="meta">
        <span className="sec">{sectionName(s.section)}</span>
        <span>
          <TimeAgo iso={s.updatedAt} />
        </span>
        {s.sourceCount > 1 && <span className="dot">{s.sourceCount} kaynak</span>}
        {isDeveloping(s) && <span className="tag-dev">Gelişiyor</span>}
        {fresh && !read && <span className="new-dot" title="Son ziyaretinizden sonra güncellendi" />}
      </div>

      <TitleTag className="story-title">
        {standalone ? s.title : <Link href={`/haber/${s.id}`} onClick={onOpen}>{s.title}</Link>}
      </TitleTag>
      <p className="summary">{s.summary}</p>

      {full && points.length > 0 && (
        <ul className="points">
          {points.map((p, i) => <li key={i}>{p}</li>)}
        </ul>
      )}

      {full && s.facts.length > 0 && (
        <dl className="facts">
          {s.facts.map((f, i) => (
            <div className="fact" key={i}>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {s.why && (showDetail || lead) && (
        <p className="why"><b>Neden önemli?</b> {s.why}</p>
      )}

      <div className="story-foot">
        {s.kind === "brief" ? (
          <span className="brief-note">
            Haberin tamamı:{" "}
            {s.sources.map((src, i) => (
              <span key={src.url}>
                {i > 0 && ", "}
                <a className="ext" href={src.url} target="_blank" rel="noopener">{src.name}</a>
              </span>
            ))}
          </span>
        ) : standalone && s.sources.length > 1 ? null : (
          <span className="sources-inline">
            {s.sources.slice(0, 4).map((src, i) => (
              <span key={src.url}>
                {i > 0 && ", "}
                <a href={src.url} target="_blank" rel="noopener">{src.name}</a>
              </span>
            ))}
            {s.sources.length > 4 && <span> ve {s.sources.length - 4} kaynak daha</span>}
          </span>
        )}
        {!standalone && onToggle && (full || s.sources.length > 1) && (
          <button className="more" onClick={onToggle} aria-expanded={expanded}>
            {expanded ? "Kapat" : hidden > 0 ? `+${hidden} ayrıntı, kaynaklar` : "Kaynaklar ve gelişmeler"}
          </button>
        )}
      </div>

      {showDetail && (s.sources.length > 1 || s.timeline.length > 1) && (
        <div className="detail">
          {s.timeline.length > 1 && (
            <div>
              <h4 className="kicker">Gelişmeler</h4>
              <ol className="timeline">
                {[...s.timeline].reverse().map((t, i) => (
                  <li key={i}>
                    <time dateTime={t.t}>{clock(t.t)}</time>
                    <span>{t.text}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div>
            <h4 className="kicker">Kaynaklar</h4>
            <ul className="src-list">
              {s.sources.map((src) => (
                <li key={src.url}>
                  <span className="name">{src.name}</span>
                  <a className="t ext" href={src.url} target="_blank" rel="noopener">{src.title}</a>{" "}
                  <span className="muted num">{clock(src.published)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </article>
  );
}
