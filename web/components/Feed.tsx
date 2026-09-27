"use client";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { Feed as FeedData, SectionKey, Story } from "@/lib/types";
import { sectionName } from "@/lib/types";
import { clock } from "@/lib/format";
import StoryCard from "./StoryCard";
import SectionNav from "./SectionNav";
import TimeAgo from "./TimeAgo";

const POLL_MS = 90_000;
const MAIN_LIMIT = 30;

function store<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

/** Ana sütunda gösterilecek mi, yoksa "Kısa kısa"ya mı düşecek */
const isMain = (s: Story) => s.kind === "full" || s.importance >= 4;

const fold = (t: string) => t.toLocaleLowerCase("tr-TR").normalize("NFKD").replace(/[̀-ͯ]/g, "");

export default function Feed({ initial, section, top }: { initial: FeedData; section?: SectionKey; top?: ReactNode }) {
  const [feed, setFeed] = useState(initial);
  const [pending, setPending] = useState<FeedData | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [focus, setFocus] = useState(-1);
  const [read, setRead] = useState<Record<string, string>>({});
  const [lastVisit, setLastVisit] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  // okunanlar ve son ziyaret yalnızca bu tarayıcıda tutulur
  useEffect(() => {
    setRead(store("akis:read", {}));
    const lv = store<string | null>("akis:lastVisit", null);
    setLastVisit(lv);
    const t = setTimeout(() => save("akis:lastVisit", new Date().toISOString()), 20_000);
    return () => clearTimeout(t);
  }, []);

  const markRead = useCallback((s: Story) => {
    setRead((r) => {
      const cutoff = Date.now() - 3 * 864e5;
      const next: Record<string, string> = { [s.id]: s.updatedAt };
      for (const [k, v] of Object.entries(r)) if (new Date(v).getTime() > cutoff && k !== s.id) next[k] = v;
      save("akis:read", next);
      return next;
    });
  }, []);

  // yeni veri var mı?
  useEffect(() => {
    const poll = async () => {
      if (document.hidden) return;
      try {
        const res = await fetch("/api/data/feed.json", { cache: "no-store" });
        if (!res.ok) return;
        const next = (await res.json()) as FeedData;
        if (!next.generatedAt || next.generatedAt === feed.generatedAt) return;
        const known = new Map(feed.stories.map((s) => [s.id, s.updatedAt]));
        const changed = next.stories.some((s) => known.get(s.id) !== s.updatedAt && (!section || s.section === section));
        // okurun gözünün önündeki listeyi yalnızca gerçekten yeni haber varsa ve okur isterse değiştir
        if (changed) setPending(next);
        else setFeed(next);
      } catch {}
    };
    const t = setInterval(poll, POLL_MS);
    document.addEventListener("visibilitychange", poll);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [feed, section]);

  const pool = useMemo(
    () => (section ? feed.stories.filter((s) => s.section === section) : feed.stories),
    [feed, section],
  );

  const searching = query.trim().length >= 2;
  const results = useMemo(() => {
    if (!searching) return [];
    const words = fold(query).split(/\s+/).filter(Boolean);
    return pool.filter((s) => {
      const hay = fold([s.title, s.summary, ...s.points, ...s.tags, ...s.sources.map((x) => x.name)].join(" "));
      return words.every((w) => hay.includes(w));
    });
  }, [pool, query, searching]);

  const main = useMemo(() => pool.filter(isMain), [pool]);
  const shorts = useMemo(
    () => pool.filter((s) => !isMain(s)).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
    [pool],
  );
  const visible = searching ? results : showAll ? main : main.slice(0, MAIN_LIMIT);

  const updates = useMemo(() => {
    const out: { story: Story; t: string; text: string }[] = [];
    for (const s of pool) for (const u of s.timeline.slice(1)) out.push({ story: s, t: u.t, text: u.text });
    return out.sort((a, b) => b.t.localeCompare(a.t)).slice(0, 8);
  }, [pool]);

  const newCount = useMemo(() => {
    if (!pending) return 0;
    const known = new Map(feed.stories.map((s) => [s.id, s.updatedAt]));
    return pending.stories.filter((s) => known.get(s.id) !== s.updatedAt && (!section || s.section === section)).length;
  }, [pending, feed, section]);

  const toggle = useCallback(
    (s: Story) => {
      setExpanded((e) => {
        const n = new Set(e);
        if (n.has(s.id)) n.delete(s.id);
        else n.add(s.id);
        return n;
      });
      markRead(s);
    },
    [markRead],
  );

  // klavye: j/k gezin, o/Enter aç, / ara, Esc temizle
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") {
        if (e.key === "Escape") {
          setQuery("");
          (target as HTMLInputElement).blur();
        }
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (e.key === "j" || e.key === "k") {
        setFocus((f) => {
          const n = Math.max(0, Math.min(visible.length - 1, f + (e.key === "j" ? 1 : -1)));
          document.getElementById(`s-${visible[n]?.id}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
          return n;
        });
      } else if ((e.key === "o" || e.key === "Enter") && visible[focus]) {
        toggle(visible[focus]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible, focus, toggle]);

  const card = (s: Story, i: number, lead = false) => (
    <StoryCard
      key={s.id}
      story={s}
      lead={lead}
      expanded={expanded.has(s.id)}
      focused={focus === i}
      read={read[s.id] === s.updatedAt}
      fresh={!!lastVisit && new Date(s.updatedAt) > new Date(lastVisit)}
      onToggle={() => toggle(s)}
      onOpen={() => markRead(s)}
    />
  );

  return (
    <>
      <SectionNav>
        <label className="search" htmlFor="q">
          <span className="sr">Haberlerde ara</span>
          <input
            id="q"
            ref={searchRef}
            type="search"
            placeholder="Ara"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setFocus(-1);
            }}
            autoComplete="off"
          />
          <kbd>/</kbd>
        </label>
      </SectionNav>

      {pending && (
        <div className="new-pill">
          <button
            onClick={() => {
              setFeed(pending);
              setPending(null);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            {newCount} haber güncellendi · göster
          </button>
        </div>
      )}

      <div className="wrap">
      {top}
      <div className="layout">
        <main>
          {searching ? (
            <div className="section-head">
              <span className="kicker">&ldquo;{query.trim()}&rdquo; için {results.length} sonuç</span>
            </div>
          ) : null}
          {visible.length === 0 && (
            <p className="empty">{searching ? "Eşleşen haber yok." : "Henüz haber yok. Motor ilk turunu tamamladığında burada görünecek."}</p>
          )}
          {visible.map((s, i) => card(s, i, !searching && i === 0))}
          {!searching && !showAll && main.length > MAIN_LIMIT && (
            <p style={{ textAlign: "center", padding: "18px 0" }}>
              <button className="more" onClick={() => setShowAll(true)}>
                {main.length - MAIN_LIMIT} haber daha göster
              </button>
            </p>
          )}
        </main>

        <aside className="rail">
          {updates.length > 0 && (
            <section className="rail-block">
              <h3 className="kicker">Son gelişmeler</h3>
              <ul className="shorts">
                {updates.map((u, i) => (
                  <li key={i}>
                    <time className="num">{clock(u.t)}</time>
                    <Link href={`/haber/${u.story.id}`}>{u.text}</Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section className="rail-block">
            <h3 className="kicker">Kısa kısa</h3>
            {shorts.length === 0 && <p className="muted">—</p>}
            <ul className="shorts">
              {shorts.slice(0, showAll ? 120 : 40).map((s) => (
                <li key={s.id} data-section={s.section}>
                  <time className="num">{clock(s.updatedAt)}</time>
                  {!section && (
                    <span className="sec-dot" style={{ background: `var(--s-${s.section})` }} title={sectionName(s.section)} />
                  )}
                  <a href={s.sources[0]?.url} target="_blank" rel="noopener" title={s.summary}>
                    {s.title}
                  </a>{" "}
                  <span className="s">{s.sources[0]?.name}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className="rail-block muted" style={{ fontSize: 12.5 }}>
            Kısayollar: <span className="kbd">j</span> <span className="kbd">k</span> gezin ·{" "}
            <span className="kbd">o</span> aç · <span className="kbd">/</span> ara
            <br />
            Veri <TimeAgo iso={feed.generatedAt || new Date().toISOString()} /> güncellendi.
          </section>
        </aside>
      </div>
      </div>
    </>
  );
}
