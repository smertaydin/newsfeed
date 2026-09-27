import Link from "next/link";
import SectionNav from "@/components/SectionNav";

export default function NotFound() {
  return (
    <>
      <SectionNav />
      <div className="wrap">
        <div className="prose">
          <h1>Bu haber artık akışta değil</h1>
          <p>
            Aradığınız sayfa bulunamadı ya da haber 30 günlük arşivden çıkmış olabilir. <Link href="/">Ana sayfaya dönün</Link>.
          </p>
        </div>
      </div>
    </>
  );
}
