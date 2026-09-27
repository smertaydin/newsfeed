import { rssResponse } from "@/lib/rss";
import { SECTIONS } from "@/lib/types";

export async function GET(req: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  const key = file.replace(/\.xml$/, "");
  if (!SECTIONS.some((s) => s.key === key)) return new Response("Bulunamadı", { status: 404 });
  return rssResponse(`rss/${key}.xml`, req);
}
