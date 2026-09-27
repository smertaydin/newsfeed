import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Feed from "@/components/Feed";
import { getFeed } from "@/lib/data";
import { SECTIONS, type SectionKey } from "@/lib/types";

export const revalidate = 60;
export const dynamicParams = false;

export function generateStaticParams() {
  return SECTIONS.map((s) => ({ section: s.key }));
}

export async function generateMetadata({ params }: { params: Promise<{ section: string }> }): Promise<Metadata> {
  const { section } = await params;
  const s = SECTIONS.find((x) => x.key === section);
  return {
    title: s?.name,
    alternates: { types: { "application/rss+xml": [{ url: `/rss/${section}.xml`, title: `Akış · ${s?.name}` }] } },
  };
}

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const s = SECTIONS.find((x) => x.key === section);
  if (!s) notFound();
  const feed = await getFeed();
  return (
    <Feed
      initial={feed}
      section={section as SectionKey}
      top={
        <div className="section-head" style={{ ["--accent" as string]: `var(--s-${s.key})` }}>
          <h1>{s.name}</h1>
          <a className="muted" href={`/rss/${s.key}.xml`} style={{ fontSize: 13 }}>RSS</a>
        </div>
      }
    />
  );
}
