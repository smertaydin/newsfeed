import Link from "next/link";
import { SECTIONS } from "@/lib/types";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="wrap footer-inner">
        <div>
          Akış, haberleri açık kaynaklardan toplayıp yerel bir yapay zekâ modeliyle derler. Her haberin kaynağı belirtilir;
          özgün içerikler için yayın organına yönlendirilirsiniz.
        </div>
        <nav aria-label="Alt bağlantılar">
          <Link href="/hakkinda">Nasıl çalışır</Link>
          <Link href="/kaynaklar">Kaynaklar</Link>
          <a href="/rss.xml">RSS</a>
          {SECTIONS.map((s) => (
            <a key={s.key} href={`/rss/${s.key}.xml`}>
              {s.name} RSS
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
