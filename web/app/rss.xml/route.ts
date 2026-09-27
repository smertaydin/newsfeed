import { rssResponse } from "@/lib/rss";

export const revalidate = 120;

export function GET(req: Request) {
  return rssResponse("rss.xml", req);
}
