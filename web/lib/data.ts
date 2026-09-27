import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { Brief, Feed, Markets, SourceHealth, Stats, Story } from "./types";

/** Sayfaların ve veri isteklerinin yenilenme sıklığı (saniye). Motor 15 dakikada bir yazar. */
export const REVALIDATE = 60;

const BASE = process.env.DATA_BASE_URL?.replace(/\/$/, "");
const DIR = process.env.DATA_DIR;

export async function readData(file: string): Promise<string | null> {
  if (DIR) {
    try {
      return await readFile(path.join(/* turbopackIgnore: true */ process.cwd(), DIR, file), "utf8");
    } catch {
      return null;
    }
  }
  if (!BASE) return null;
  try {
    const res = await fetch(`${BASE}/${file}`, { next: { revalidate: REVALIDATE } });
    return res.ok ? await res.text() : null;
  } catch {
    return null;
  }
}

async function json<T>(file: string, fallback: T): Promise<T> {
  const raw = await readData(file);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

const EMPTY_FEED: Feed = { generatedAt: "", sections: {} as Feed["sections"], stories: [] };

export const getFeed = () => json<Feed>("feed.json", EMPTY_FEED);
export const getBrief = () => json<Brief>("brief.json", {});
export const getMarkets = () => json<Markets>("markets.json", {});
export const getStats = () => json<Stats | null>("stats.json", null);
export const getSources = () => json<{ generatedAt: string; feeds: SourceHealth[] }>("sources.json", { generatedAt: "", feeds: [] });

/** Önce güncel akışta, yoksa hikâyenin tarihine ait arşiv dosyasında arar. */
export async function getStory(id: string): Promise<Story | null> {
  if (!/^\d{8}-[0-9a-f]{8}$/.test(id)) return null;
  const feed = await getFeed();
  const live = feed.stories.find((s) => s.id === id);
  if (live) return live;
  const day = await json<{ stories: Story[] }>(`archive/${id.slice(0, 8)}.json`, { stories: [] });
  return day.stories.find((s) => s.id === id) ?? null;
}
