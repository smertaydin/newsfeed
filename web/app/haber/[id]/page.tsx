import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import SectionNav from "@/components/SectionNav";
import StoryCard from "@/components/StoryCard";
import { getFeed, getStory } from "@/lib/data";
import { sectionName } from "@/lib/types";

export const revalidate = 60;

export function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const story = await getStory((await params).id);
  if (!story) return {};
  return {
    title: story.title,
    description: story.summary,
    openGraph: { title: story.title, description: story.summary, type: "article", publishedTime: story.firstSeen },
  };
}

export default async function StoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const story = await getStory(id);
  if (!story) notFound();
  const feed = await getFeed();
  // aynı bölümden, ortak etiketi olan diğer haberler
  const tags = new Set(story.tags.map((t) => t.toLocaleLowerCase("tr-TR")));
  const related = feed.stories
    .filter((s) => s.id !== id && s.tags.some((t) => tags.has(t.toLocaleLowerCase("tr-TR"))))
    .slice(0, 5);

  return (
    <>
      <SectionNav />
      <div className="wrap">
        <div className="article">
          <Link href={`/${story.section}`} className="back">
            ← {sectionName(story.section)}
          </Link>
          <StoryCard story={story} standalone />
          {related.length > 0 && (
            <section className="rail-block" style={{ borderTop: "1px solid var(--rule-strong)" }}>
              <h3 className="kicker">İlgili haberler</h3>
              <ul className="shorts">
                {related.map((s) => (
                  <li key={s.id}>
                    <Link href={`/haber/${s.id}`}>{s.title}</Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
