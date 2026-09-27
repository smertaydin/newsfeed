import { readData } from "@/lib/data";

// Tarayıcının yeni veri olup olmadığını yoklaması için; yalnızca bilinen dosyalar sunulur.
const ALLOWED = new Set(["feed.json", "brief.json", "markets.json", "stats.json"]);

export async function GET(_req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const file = (await params).path.join("/");
  if (!ALLOWED.has(file)) return new Response("Bulunamadı", { status: 404 });
  const body = await readData(file);
  if (!body) return new Response("Veri yok", { status: 503 });
  return new Response(body, {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, s-maxage=60, stale-while-revalidate=300" },
  });
}
