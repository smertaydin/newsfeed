import BriefBox from "@/components/BriefBox";
import Feed from "@/components/Feed";
import { getBrief, getFeed } from "@/lib/data";

export const revalidate = 60;

export default async function Home() {
  const [feed, brief] = await Promise.all([getFeed(), getBrief()]);
  return <Feed initial={feed} top={<BriefBox brief={brief} stories={feed.stories} />} />;
}
