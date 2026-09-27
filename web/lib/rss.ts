import "server-only";
import { readData } from "./data";

/** Motorun ürettiği RSS'teki site adresini isteğin geldiği adresle değiştirir. */
export async function rssResponse(file: string, req: Request) {
  const xml = await readData(file);
  if (!xml) return new Response("Bulunamadı", { status: 404 });
  const site = xml.match(/<link>([^<]+)<\/link>/)?.[1];
  const origin = new URL(req.url).origin;
  const body = site ? xml.split(site.replace(/\/$/, "")).join(origin) : xml;
  return new Response(body, {
    headers: {
      "content-type": "application/rss+xml; charset=utf-8",
      "cache-control": "public, s-maxage=120, stale-while-revalidate=600",
    },
  });
}
