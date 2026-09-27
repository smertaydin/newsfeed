import type { Metadata } from "next";
import SectionNav from "@/components/SectionNav";
import TimeAgo from "@/components/TimeAgo";
import { getStats } from "@/lib/data";

export const revalidate = 300;
export const metadata: Metadata = { title: "Nasıl çalışır" };

export default async function About() {
  const stats = await getStats();
  return (
    <>
      <SectionNav />
      <div className="wrap">
        <div className="prose">
          <h1>Nasıl çalışır</h1>
          <p>
            Akış, onlarca yayın organının RSS beslemelerini {stats?.intervalMinutes ?? 15} dakikada bir tarar. Aynı olayı anlatan
            haberler anlam benzerliğine göre bir araya getirilir; tek bir haber kartında, kaynakların ortak ve tamamlayıcı
            bilgileri birleştirilir. Farklı kaynaklar arasında çelişki varsa kartta belirtilir.
          </p>
          <h2>Kim yazıyor?</h2>
          <p>
            Özetler, tamamen yerel bir bilgisayarda çalışan açık kaynaklı bir yapay zekâ modeli tarafından yazılır
            {stats && <> (şu an: <code>{stats.model}</code>)</>}. Model yalnızca kaynak haberlerin metnini görür ve bu metinlerde
            olmayan bilgiyi eklememesi istenir. Yine de hata yapabilir; her kartın altındaki kaynak bağlantılarıyla doğrulayabilirsiniz.
          </p>
          <h2>Kaynağa saygı</h2>
          <p>
            Resmî açıklamalar, maç sonuçları, kazalar ya da veri açıklamaları gibi kamuya mal olmuş bilgiler kaynak gösterilerek
            ayrıntılı derlenir. Röportaj, özel haber, araştırma dosyası ya da köşe yazısı gibi bir yayın organına ait özgün
            içeriklerde yalnızca kısa bir özet verilir ve okur doğrudan yayın organına yönlendirilir.
          </p>
          <h2>Kartları okuma</h2>
          <ul>
            <li><b>N kaynak</b>: aynı olayı kaç farklı yayın organının haberleştirdiği.</li>
            <li><b>Gelişiyor</b>: son üç saatte habere yeni bilgi eklendi.</li>
            <li><b>Kısa kısa</b>: tek kaynaktan gelen, görece daha az önemli haberler; doğrudan kaynağa gider.</li>
            <li>Nokta işareti: son ziyaretinizden sonra güncellenen haber.</li>
          </ul>
          {stats && (
            <>
              <h2>Son tur</h2>
              <p className="num">
                <TimeAgo iso={stats.generatedAt} /> · {stats.feeds} besleme · {stats.newArticles} yeni haber · {stats.written} kart yazıldı ·
                model {Math.round(stats.llm.seconds)} sn çalıştı ({stats.llm.out_tokens.toLocaleString("tr-TR")} token üretti).
              </p>
            </>
          )}
          <h2>RSS</h2>
          <p>
            Tüm akış <a href="/rss.xml">/rss.xml</a> adresinden, bölümler <code>/rss/gundem.xml</code>, <code>/rss/ekonomi.xml</code>,
            <code> /rss/dunya.xml</code>, <code>/rss/teknoloji.xml</code>, <code>/rss/spor.xml</code> adreslerinden takip edilebilir.
          </p>
        </div>
      </div>
    </>
  );
}
