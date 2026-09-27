import type { Metadata } from "next";
import SectionNav from "@/components/SectionNav";
import TimeAgo from "@/components/TimeAgo";
import { getSources } from "@/lib/data";
import { sectionName } from "@/lib/types";

export const revalidate = 300;
export const metadata: Metadata = { title: "Kaynaklar" };

export default async function SourcesPage() {
  const { feeds, generatedAt } = await getSources();
  const ok = feeds.filter((f) => f.ok).length;
  return (
    <>
      <SectionNav />
      <div className="wrap">
        <div className="prose" style={{ maxWidth: 980 }}>
          <h1>Kaynaklar</h1>
          <p>
            Akış {feeds.length} RSS beslemesini izliyor; şu anda {ok} tanesi sorunsuz yanıt veriyor.
            {generatedAt && <> Durum <TimeAgo iso={generatedAt} /> kontrol edildi.</>} Liste kaynak dosyasından düzenli olarak
            yeniden okunur; yeni eklenen beslemeler kendiliğinden devreye girer.
          </p>
          <table className="health">
            <thead>
              <tr>
                <th>Yayın</th>
                <th>Kategori</th>
                <th>Bölüm</th>
                <th>Durum</th>
                <th>Besleme</th>
              </tr>
            </thead>
            <tbody>
              {feeds.map((f) => (
                <tr key={f.url}>
                  <td>{f.name}</td>
                  <td>{f.category}</td>
                  <td>{sectionName(f.section)}</td>
                  <td className={f.ok ? "ok" : "bad"} title={f.error ?? undefined}>
                    {f.ok ? `${f.items} haber` : "Yanıt yok"}
                  </td>
                  <td className="url">{f.url}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
