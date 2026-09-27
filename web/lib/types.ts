export type SectionKey = "gundem" | "ekonomi" | "dunya" | "teknoloji" | "spor";

export interface Source {
  name: string;
  url: string;
  title: string;
  published: string;
}

export interface Story {
  id: string;
  section: SectionKey;
  /** full: birden çok kaynaktan derlenmiş ayrıntılı kart; brief: kısa özet + kaynağa bağlantı */
  kind: "full" | "brief";
  importance: number;
  title: string;
  summary: string;
  points: string[];
  facts: { label: string; value: string }[];
  why: string;
  tags: string[];
  timeline: { t: string; text: string; n: number }[];
  sources: Source[];
  sourceCount: number;
  firstSeen: string;
  updatedAt: string;
  score: number;
}

export interface Feed {
  generatedAt: string;
  sections: Record<SectionKey, string>;
  stories: Story[];
}

export interface Brief {
  generated_at?: string;
  headline?: string;
  items?: { text: string; ids: string[] }[];
}

export interface Markets {
  updatedAt?: string;
  items?: { symbol: string; label: string; price: number; change: number; unit: string }[];
}

export interface SourceHealth {
  url: string;
  name: string;
  category: string;
  section: SectionKey;
  ok: boolean;
  lastOk: string | null;
  error: string | null;
  items: number;
}

export interface Stats {
  generatedAt: string;
  model: string;
  embedModel: string;
  cycleSeconds: number;
  newArticles: number;
  newStories: number;
  written: number;
  feeds: number;
  intervalMinutes: number;
  llm: { calls: number; seconds: number; in_tokens: number; out_tokens: number };
}

export const SECTIONS: { key: SectionKey; name: string }[] = [
  { key: "gundem", name: "Gündem" },
  { key: "ekonomi", name: "Ekonomi" },
  { key: "dunya", name: "Dünya" },
  { key: "teknoloji", name: "Teknoloji" },
  { key: "spor", name: "Spor" },
];

export const sectionName = (k: string) => SECTIONS.find((s) => s.key === k)?.name ?? k;
